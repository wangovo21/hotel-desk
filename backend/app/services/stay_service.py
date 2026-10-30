"""入住单的完整生命周期：登记 → 续住 / 换房 / 加费 → 退房结账（或撤销）。

**这个文件是账目的唯一入口。** 别的地方不许直接改 stays 或往 stay_charges 写钱。
理由和原项目的"积分只能走 points_service"一样：钱的路只留一条，
对账时就不需要问"这笔费是谁写进来的"。
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from app.core.dates import (
    DATE_FMT,
    DATETIME_FMT,
    actual_nights,
    date_str,
    datetime_str,
    nights_between,
    now_str,
    parse_date,
    today as today_fn,
)
from app.core.errors import AppError
from app.core.labels import ROOM_STATUS_LABELS, label
from app.core.money import format_cents, parse_amount
from app.db import write_tx
from app.models.stay import ChargeIn, CheckinCreate, CheckoutIn, ChangeRoomIn, ExtendIn
from app.repo import room_repo, settings_repo, stay_repo
from app.services import card_service, guest_service, serializers

logger = logging.getLogger("hotel_desk")

DEFAULT_MAX_RATE_CENTS = 500_000
DEFAULT_MAX_CHARGE_CENTS = 100_000
DEFAULT_DEPOSIT_CENTS = 30_000


# ---------------------------------------------------------------------------
# 入参归一化
# ---------------------------------------------------------------------------
def _normalize_checkin_at(value: str | None) -> str:
    """把 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD HH:MM:SS' 统一成后者。

    只给日期时按 14:00 记 —— 这是行业默认入住时间，也比 00:00 更接近事实
    （凌晨 00:00 记进去，退房算间夜时永远是 1 晚，看着对但时间线是假的）。
    """
    if value is None or not str(value).strip():
        return now_str()

    text = str(value).strip().replace("T", " ")
    parts = text.split()
    day = parse_date(parts[0], field="入住日期")
    if len(parts) == 1:
        return datetime_str(day, "14:00")

    clock = parts[1]
    if clock.count(":") == 1:
        clock = f"{clock}:00"
    try:
        datetime.strptime(f"{day.strftime(DATE_FMT)} {clock}", DATETIME_FMT)
    except ValueError:
        raise AppError("INVALID_DATE", "入住时刻不合法，应为 HH:MM") from None
    return f"{day.strftime(DATE_FMT)} {clock}"


def _require_in_house(conn: sqlite3.Connection, stay_id: int) -> sqlite3.Row:
    row = stay_repo.get_stay(conn, stay_id)
    if row is None:
        raise AppError("STAY_NOT_FOUND")
    if row["status"] != "IN_HOUSE":
        raise AppError(
            "STAY_NOT_IN_HOUSE",
            f"入住单 {row['stay_no']} 已{label({'CHECKED_OUT': '退房', 'CANCELLED': '撤销'}, row['status'])}，不能再操作",
        )
    return row


# ---------------------------------------------------------------------------
# 输出组装
# ---------------------------------------------------------------------------
def _detail(conn: sqlite3.Connection, stay_id: int) -> dict:
    row = stay_repo.get_stay(conn, stay_id)
    if row is None:
        raise AppError("STAY_NOT_FOUND")

    charges = stay_repo.list_charges(conn, stay_id)
    events = stay_repo.list_events(conn, stay_id)
    detail = serializers.stay_brief(row)
    detail.update(
        {
            "remark": row["remark"],
            "operator": row["operator"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "charges": [serializers.charge_out(c) for c in charges],
            "events": [serializers.event_out(e) for e in events],
            "cards": card_service.detail(conn, stay_id),
            "bill": serializers.bill_of(row, nights=int(row["nights"]), charges=charges),
        }
    )
    return detail


# ---------------------------------------------------------------------------
# 入住登记
# ---------------------------------------------------------------------------
def checkin(conn: sqlite3.Connection, body: CheckinCreate) -> dict:
    max_rate = settings_repo.get_int(conn, "MAX_ROOM_RATE_CENTS", DEFAULT_MAX_RATE_CENTS)
    default_deposit = settings_repo.get_int(conn, "DEFAULT_DEPOSIT_CENTS", DEFAULT_DEPOSIT_CENTS)

    checkin_at = _normalize_checkin_at(body.checkin_at)
    checkin_date = parse_date(checkin_at[:10], field="入住日期")
    expected = parse_date(body.expected_checkout_date, field="预计离店日期")
    nights = nights_between(checkin_date, expected)

    with write_tx(conn):
        room = room_repo.get_room(conn, body.room_id)
        if room is None:
            raise AppError("ROOM_NOT_FOUND")

        # 先看有没有在住单，再看房态：脏数据里"房态空闲但挂着在住单"是可能的，
        # 那种情况下报"房间有客人在住"比报"不是空房"更贴事实。
        if stay_repo.get_in_house_by_room(conn, body.room_id) is not None:
            raise AppError("ROOM_OCCUPIED", f"房间 {room['room_no']} 已有客人在住")
        if room["status"] == "MAINTENANCE":
            raise AppError("ROOM_UNDER_MAINTENANCE", f"房间 {room['room_no']} 正在维修")
        if room["status"] != "VACANT":
            raise AppError(
                "ROOM_NOT_VACANT",
                f"房间 {room['room_no']} 当前是「{label(ROOM_STATUS_LABELS, room['status'])}」，"
                "请先标记为空闲再办入住",
            )

        room_type = room_repo.get_type(conn, int(room["room_type_id"]))
        if room_type is None:
            raise AppError("ROOM_TYPE_NOT_FOUND")
        if room_type["status"] != "ON":
            raise AppError("ROOM_TYPE_OFF", f"房型「{room_type['name']}」已停用，不能安排入住")

        if body.adults + body.children > int(room_type["capacity"]):
            raise AppError(
                "INVALID_PARAM",
                f"房型「{room_type['name']}」最多住 {room_type['capacity']} 人，"
                f"当前登记 {body.adults} 成人 + {body.children} 儿童",
            )

        rate_cents = (
            parse_amount(body.room_rate, max_cents=max_rate, field="房价")
            if body.room_rate not in (None, "")
            else int(room_type["base_price_cents"])
        )
        deposit_cents = (
            parse_amount(body.deposit, max_cents=max_rate, allow_zero=True, field="押金")
            if body.deposit not in (None, "")
            else default_deposit
        )

        if body.guest_id is not None:
            guest = guest_service.resolve_for_checkin(conn, body.guest_id)
            guest_id = int(guest["id"])
        else:
            assert body.guest is not None  # CheckinCreate 的 model_validator 已保证
            guest_id = guest_service.upsert_for_checkin(conn, body.guest)

        stay_no = stay_repo.next_stay_no(conn, checkin_date.strftime("%Y%m%d"))
        stay_id = stay_repo.insert_stay(
            conn,
            stay_no=stay_no,
            guest_id=guest_id,
            room_id=body.room_id,
            room_rate_cents=rate_cents,
            checkin_at=checkin_at,
            expected_checkout_date=date_str(expected),
            nights=nights,
            deposit_cents=deposit_cents,
            adults=body.adults,
            children=body.children,
            operator=body.operator,
            remark=body.remark,
        )

        room_repo.set_status(conn, body.room_id, "OCCUPIED")
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="CHECKIN",
            to_value=room["room_no"],
            amount_cents=deposit_cents,
            operator=body.operator,
            remark=f"{nights} 间夜 · 押金 {format_cents(deposit_cents)} 元",
        )

    logger.info("入住登记 %s：房间 %s，%s 间夜", stay_no, room["room_no"], nights)
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 续住
# ---------------------------------------------------------------------------
def extend(conn: sqlite3.Connection, stay_id: int, body: ExtendIn) -> dict:
    row = _require_in_house(conn, stay_id)
    current_expected = parse_date(row["expected_checkout_date"], field="当前预计离店日")
    new_expected = parse_date(body.expected_checkout_date, field="新的预计离店日")

    if new_expected <= current_expected:
        raise AppError("STAY_ALREADY_EXTENDED_TO")
    nights = nights_between(parse_date(row["checkin_at"][:10], field="入住日期"), new_expected)

    with write_tx(conn):
        stay_repo.update_expected(conn, stay_id, date_str(new_expected), nights)
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="EXTEND",
            from_value=row["expected_checkout_date"],
            to_value=date_str(new_expected),
            operator=body.operator,
            remark=body.remark or f"续住至 {date_str(new_expected)}，共 {nights} 间夜",
        )
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 换房
# ---------------------------------------------------------------------------
def change_room(conn: sqlite3.Connection, stay_id: int, body: ChangeRoomIn) -> dict:
    row = _require_in_house(conn, stay_id)
    max_rate = settings_repo.get_int(conn, "MAX_ROOM_RATE_CENTS", DEFAULT_MAX_RATE_CENTS)

    if int(body.room_id) == int(row["room_id"]):
        raise AppError("STAY_ROOM_UNCHANGED")

    with write_tx(conn):
        target = room_repo.get_room(conn, body.room_id)
        if target is None:
            raise AppError("ROOM_NOT_FOUND")
        if stay_repo.get_in_house_by_room(conn, body.room_id) is not None:
            raise AppError("ROOM_OCCUPIED", f"房间 {target['room_no']} 已有客人在住")
        if target["status"] == "MAINTENANCE":
            raise AppError("ROOM_UNDER_MAINTENANCE", f"房间 {target['room_no']} 正在维修")
        if target["status"] != "VACANT":
            raise AppError(
                "ROOM_NOT_VACANT",
                f"房间 {target['room_no']} 当前是「{label(ROOM_STATUS_LABELS, target['status'])}」",
            )

        room_type = room_repo.get_type(conn, int(target["room_type_id"]))
        if room_type is not None and int(row["adults"]) + int(row["children"]) > int(room_type["capacity"]):
            raise AppError(
                "INVALID_PARAM",
                f"房型「{room_type['name']}」最多住 {room_type['capacity']} 人，"
                f"当前登记 {row['adults']} 成人 + {row['children']} 儿童",
            )

        # 不给新房价就沿用原房价 —— 换房不该悄悄变成涨价
        rate_cents = (
            parse_amount(body.room_rate, max_cents=max_rate, field="房价")
            if body.room_rate not in (None, "")
            else int(row["room_rate_cents"])
        )

        room_repo.set_status(conn, int(row["room_id"]), "CLEANING")
        room_repo.set_status(conn, body.room_id, "OCCUPIED")
        stay_repo.update_room(conn, stay_id, body.room_id, rate_cents)
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="CHANGE_ROOM",
            from_value=row["room_no"],
            to_value=target["room_no"],
            operator=body.operator,
            remark=body.remark or f"{row['room_no']} → {target['room_no']}",
        )
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 加收费用
# ---------------------------------------------------------------------------
def add_charge(conn: sqlite3.Connection, stay_id: int, body: ChargeIn) -> dict:
    _require_in_house(conn, stay_id)
    max_charge = settings_repo.get_int(conn, "MAX_CHARGE_CENTS", DEFAULT_MAX_CHARGE_CENTS)
    unit_cents = parse_amount(body.amount, max_cents=max_charge, field="杂费金额")

    with write_tx(conn):
        stay_repo.insert_charge(
            conn,
            stay_id=stay_id,
            category=body.category,
            name=body.name.strip(),
            amount_cents=unit_cents,
            quantity=body.quantity,
            operator=body.operator,
            remark=body.remark,
        )
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="ADD_CHARGE",
            to_value=body.name.strip(),
            amount_cents=unit_cents * body.quantity,
            operator=body.operator,
            remark=body.remark,
        )
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 退房结账
# ---------------------------------------------------------------------------
def checkout(conn: sqlite3.Connection, stay_id: int, body: CheckoutIn) -> dict:
    row = _require_in_house(conn, stay_id)
    checkout_at = now_str()

    if body.nights is not None:
        nights = int(body.nights)
        # 显式传了夜数就按客人的意愿收，但不能超过"入住日到退房日 + 1"这种明显异常
        if nights < 1:
            raise AppError("INVALID_NIGHTS")
    else:
        nights = actual_nights(row["checkin_at"], checkout_at)

    with write_tx(conn):
        # 再取一次：并发下可能已经被别的窗口退掉了
        fresh = stay_repo.get_stay(conn, stay_id)
        if fresh is None:
            raise AppError("STAY_NOT_FOUND")
        if fresh["status"] != "IN_HOUSE":
            raise AppError("STAY_ALREADY_CHECKED_OUT")

        room_fee = int(fresh["room_rate_cents"]) * nights
        stay_repo.insert_charge(
            conn,
            stay_id=stay_id,
            category="ROOM",
            name=f"房费（{nights} 间夜 × {format_cents(int(fresh['room_rate_cents']))}）",
            amount_cents=room_fee,
            quantity=1,
            operator=body.operator,
            remark=None,
        )

        stay_repo.mark_checked_out(
            conn, stay_id, checkout_at=checkout_at, nights=nights, remark=body.remark
        )
        room_repo.set_status(conn, int(fresh["room_id"]), "CLEANING")

        # 退房自动收回全部在用房卡 —— 漏收卡是真实酒店的高频事故，
        # 与其指望前台记得，不如让系统兜底（留痕里能看到收回了几张）
        card_service.revoke_all_for_stay(
            conn,
            stay_id,
            operator=body.operator,
            reason=f"退房结账自动收回（{nights} 间夜）",
        )

        # 房费行已经落库，此刻 charges_total 就是"房费 + 杂费"的总额，
        # 不再另外加一遍 room_fee（加了就是双计，实测会让账单翻倍）
        total = stay_repo.charges_total(conn, stay_id)
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="CHECKOUT",
            from_value=fresh["expected_checkout_date"],
            to_value=date_str(parse_date(checkout_at[:10])),
            amount_cents=total,
            operator=body.operator,
            remark=body.remark or f"结算 {nights} 间夜，应收 {format_cents(total)} 元",
        )

    logger.info("退房 %s：%s 间夜", row["stay_no"], nights)
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 撤销入住（登记错了，且还没产生任何消费）
# ---------------------------------------------------------------------------
def cancel(conn: sqlite3.Connection, stay_id: int, *, operator: str | None, remark: str | None) -> dict:
    row = _require_in_house(conn, stay_id)
    if stay_repo.count_non_room_charges(conn, stay_id) > 0:
        raise AppError("STAY_HAS_CHARGES")

    with write_tx(conn):
        stay_repo.mark_cancelled(conn, stay_id, checkout_at=now_str(), remark=remark)
        room_repo.set_status(conn, int(row["room_id"]), "VACANT")
        card_service.revoke_all_for_stay(
            conn, stay_id, operator=operator, reason="撤销入住自动收回"
        )
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="CANCEL",
            from_value=row["room_no"],
            amount_cents=0,
            operator=operator,
            remark=remark or "撤销入住，房间恢复空闲",
        )
    return _detail(conn, stay_id)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
def get_stay(conn: sqlite3.Connection, stay_id: int) -> dict:
    return _detail(conn, stay_id)


def list_stays(
    conn: sqlite3.Connection,
    *,
    status: str | None,
    keyword: str | None,
    date_from: str | None,
    date_to: str | None,
    room_id: int | None,
    limit: int,
    offset: int,
    page: int,
    page_size: int,
) -> dict:
    rows, total = stay_repo.list_stays(
        conn,
        status=status,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        room_id=room_id,
        limit=limit,
        offset=offset,
    )
    day = date_str(today_fn())
    return {
        "items": [serializers.stay_brief(r, today=day) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_in_house(conn: sqlite3.Connection) -> list[dict]:
    day = date_str(today_fn())
    return [serializers.stay_brief(r, today=day) for r in stay_repo.list_in_house(conn)]
