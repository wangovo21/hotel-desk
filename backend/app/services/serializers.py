"""行对象 → 接口出参。

为什么单独一个文件而不是各 service 自己拼 dict：同一张入住单会从
`/stays`、`/stays/{id}`、`/rooms` 看板、`/stats/dashboard` 四个地方返回，
四处各拼一遍，早晚出现"看板上的离店日和详情页不一样"这种鬼故事。
"""
from __future__ import annotations

import sqlite3

from app.core.dates import today as today_fn
from app.core.dates import date_str
from app.core.labels import (
    CARD_STATUS_LABELS,
    CHARGE_CATEGORY_LABELS,
    STAY_EVENT_LABELS,
    STAY_STATUS_LABELS,
    label,
)
from app.core.money import format_cents


def mask_id_no(id_no: str) -> str:
    """证件号脱敏：保留前 4 后 4，中间打星。

    列表页、房卡上只显示脱敏号；要看全号就点进客人详情 —— 前台大厅的屏幕
    是给所有路过的人看的，证件号不该整串挂在那儿。
    """
    value = (id_no or "").strip()
    if len(value) <= 8:
        # 模拟系统的 6 位虚拟号本身没有隐私含量，遮中段即可，列表里还能认人
        return value[:2] + "*" * max(0, len(value) - 4) + value[4:]
    keep_head, keep_tail = 4, 4
    return f"{value[:keep_head]}{'*' * (len(value) - keep_head - keep_tail)}{value[-keep_tail:]}"


def stay_brief(row: sqlite3.Row, *, today: str | None = None) -> dict:
    """入住单摘要。`overdue` 是给前台的提醒：在住 + 已过预计离店日。"""
    day = today or date_str(today_fn())
    status = row["status"]
    overdue = status == "IN_HOUSE" and str(row["expected_checkout_date"]) < day
    return {
        "id": row["id"],
        "stay_no": row["stay_no"],
        "guest_id": row["guest_id"],
        "guest_name": row["guest_name"],
        "guest_phone": row["guest_phone"],
        "id_no_masked": mask_id_no(row["guest_id_no"]),
        "room_id": row["room_id"],
        "room_no": row["room_no"],
        "room_type_name": row["room_type_name"],
        "room_rate_cents": row["room_rate_cents"],
        "room_rate_display": format_cents(row["room_rate_cents"]),
        "checkin_at": row["checkin_at"],
        "expected_checkout_date": row["expected_checkout_date"],
        "checkout_at": row["checkout_at"],
        "nights": row["nights"],
        "deposit_cents": row["deposit_cents"],
        "deposit_display": format_cents(row["deposit_cents"]),
        "adults": row["adults"],
        "children": row["children"],
        "status": status,
        "status_label": label(STAY_STATUS_LABELS, status),
        "overdue": overdue,
    }


def charge_out(row: sqlite3.Row) -> dict:
    subtotal = int(row["amount_cents"]) * int(row["quantity"])
    return {
        "id": row["id"],
        "category": row["category"],
        "category_label": label(CHARGE_CATEGORY_LABELS, row["category"]),
        "name": row["name"],
        "amount_cents": row["amount_cents"],
        "amount_display": format_cents(row["amount_cents"]),
        "quantity": row["quantity"],
        "subtotal_cents": subtotal,
        "subtotal_display": format_cents(subtotal),
        "operator": row["operator"],
        "remark": row["remark"],
        "created_at": row["created_at"],
    }


def event_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "type_label": label(STAY_EVENT_LABELS, row["type"]),
        "from_value": row["from_value"],
        "to_value": row["to_value"],
        "amount_cents": row["amount_cents"],
        "amount_display": format_cents(row["amount_cents"]),
        "operator": row["operator"],
        "remark": row["remark"],
        "created_at": row["created_at"],
    }


def card_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "stay_id": row["stay_id"],
        "card_no": row["card_no"],
        "room_no": row["room_no"],
        "status": row["status"],
        "status_label": label(CARD_STATUS_LABELS, row["status"]),
        "issued_at": row["issued_at"],
        "issued_by": row["issued_by"],
        "revoked_at": row["revoked_at"],
        "revoked_by": row["revoked_by"],
        "revoke_reason": row["revoke_reason"],
    }


def bill_of(row: sqlite3.Row, *, nights: int, charges: list[sqlite3.Row]) -> dict:
    """账单：房费 + 杂费 - 押金。

    `charges` 里在退房后**包含**那条 ROOM 房费行，而 room_fee 又按
    rate × nights 算了一遍 —— 两者相等，所以不冲突：这条 ROOM 行就是
    房费在账单里的"明细投影"，让账单可以逐项读。为了不重复计费，
    这里只把**非 ROOM** 的杂费计入 charges_total。
    """
    room_fee = int(row["room_rate_cents"]) * int(nights)
    charges_total = sum(
        int(c["amount_cents"]) * int(c["quantity"]) for c in charges if c["category"] != "ROOM"
    )
    total = room_fee + charges_total
    deposit = int(row["deposit_cents"])
    balance = total - deposit

    if balance > 0:
        settlement, settlement_label = "DUE", "还需收款"
    elif balance < 0:
        settlement, settlement_label = "REFUND", "需退客人"
    else:
        settlement, settlement_label = "EVEN", "已结清"

    return {
        "nights": nights,
        "room_fee_cents": room_fee,
        "room_fee_display": format_cents(room_fee),
        "charges_total_cents": charges_total,
        "charges_total_display": format_cents(charges_total),
        "total_cents": total,
        "total_display": format_cents(total),
        "deposit_cents": deposit,
        "deposit_display": format_cents(deposit),
        "balance_cents": balance,
        "balance_display": format_cents(abs(balance)),
        "settlement": settlement,
        "settlement_label": settlement_label,
    }
