from __future__ import annotations

import sqlite3

from app.core.dates import now_str, today as today_fn
from app.core.dates import date_str
from app.core.errors import AppError
from app.core.labels import ROOM_STATUS_LABELS, label
from app.core.money import format_cents, parse_amount
from app.db import write_tx
from app.models.room import RoomCreate, RoomStatusUpdate, RoomTypeCreate, RoomTypeUpdate, RoomUpdate
from app.repo import room_repo, settings_repo, stay_repo
from app.services import serializers

# 手工能做的房态流转。OCCUPIED 不在任何一条边上 —— 它是入住动作的产物，
# 允许手工设成"在住"就等于允许凭空造出一间有客人的房，账和房态立刻就散了。
MANUAL_TRANSITIONS: dict[str, set[str]] = {
    "VACANT": {"MAINTENANCE", "CLEANING"},
    "CLEANING": {"VACANT", "MAINTENANCE"},
    "MAINTENANCE": {"VACANT"},
    "OCCUPIED": set(),
}


def _max_rate(conn: sqlite3.Connection) -> int:
    return settings_repo.get_int(conn, "MAX_ROOM_RATE_CENTS", 500_000)


# ---------------------------------------------------------------------------
# 房型
# ---------------------------------------------------------------------------
def to_type_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "base_price_cents": row["base_price_cents"],
        "base_price_display": format_cents(row["base_price_cents"]),
        "capacity": row["capacity"],
        "bed_type": row["bed_type"],
        "status": row["status"],
        "status_label": "启用" if row["status"] == "ON" else "停用",
        "sort_order": row["sort_order"],
        "room_count": int(row["room_count"]) if "room_count" in row.keys() else 0,
    }


def list_types(conn: sqlite3.Connection) -> list[dict]:
    return [to_type_out(r) for r in room_repo.list_types(conn)]


def create_type(conn: sqlite3.Connection, body: RoomTypeCreate) -> dict:
    price_cents = parse_amount(body.price, max_cents=_max_rate(conn), field="挂牌价")
    if room_repo.get_type_by_code(conn, body.code) is not None:
        raise AppError("ROOM_TYPE_CODE_EXISTS")

    with write_tx(conn):
        type_id = room_repo.insert_type(
            conn,
            code=body.code,
            name=body.name,
            base_price_cents=price_cents,
            capacity=body.capacity,
            bed_type=body.bed_type,
            status=body.status,
            sort_order=body.sort_order,
        )
    row = room_repo.get_type(conn, type_id)
    if row is None:  # 刚插进去就查不到，只可能是库被换掉了
        raise AppError("INTERNAL_ERROR")
    return to_type_out({**dict(row), "room_count": 0})


def update_type(conn: sqlite3.Connection, type_id: int, body: RoomTypeUpdate) -> dict:
    if room_repo.get_type(conn, type_id) is None:
        raise AppError("ROOM_TYPE_NOT_FOUND")

    fields: dict = {}
    if "name" in body.model_fields_set:
        fields["name"] = body.name
    if "price" in body.model_fields_set:
        fields["base_price_cents"] = parse_amount(
            body.price, max_cents=_max_rate(conn), field="挂牌价"
        )
    if "capacity" in body.model_fields_set:
        fields["capacity"] = body.capacity
    if "bed_type" in body.model_fields_set:
        fields["bed_type"] = body.bed_type
    if "status" in body.model_fields_set:
        fields["status"] = body.status
    if "sort_order" in body.model_fields_set:
        fields["sort_order"] = body.sort_order

    with write_tx(conn):
        room_repo.update_type(conn, type_id, fields)

    rows = {r["id"]: r for r in room_repo.list_types(conn)}
    return to_type_out(rows[type_id])


# ---------------------------------------------------------------------------
# 房间
# ---------------------------------------------------------------------------
def to_room_out(row: sqlite3.Row, stay: sqlite3.Row | None, *, today: str | None = None) -> dict:
    return {
        "id": row["id"],
        "room_no": row["room_no"],
        "floor": row["floor"],
        "status": row["status"],
        "status_label": label(ROOM_STATUS_LABELS, row["status"]),
        "room_type_id": row["room_type_id"],
        "room_type_code": row["room_type_code"],
        "room_type_name": row["room_type_name"],
        "base_price_cents": row["base_price_cents"],
        "base_price_display": format_cents(row["base_price_cents"]),
        "capacity": row["capacity"],
        "note": row["note"],
        "current_stay": serializers.stay_brief(stay, today=today) if stay is not None else None,
    }


def require_room(conn: sqlite3.Connection, room_id: int) -> sqlite3.Row:
    row = room_repo.get_room(conn, room_id)
    if row is None:
        raise AppError("ROOM_NOT_FOUND")
    return row


def board(conn: sqlite3.Connection) -> dict:
    """房态看板：一次查询 + 一次在住单查询，在内存里分组。

    房间数在几百这个量级，全员拉回来分组比按楼层发 N 个请求快得多；
    真到了几千间房，改成按楼层分页即可，接口形状不用变。
    """
    rooms = room_repo.list_rooms(conn)
    in_house = {int(s["room_id"]): s for s in stay_repo.list_in_house(conn)}
    day = date_str(today_fn())

    by_floor: dict[int, list[dict]] = {}
    for row in rooms:
        stay = in_house.get(int(row["id"]))
        by_floor.setdefault(int(row["floor"]), []).append(
            to_room_out(row, stay, today=day)
        )

    counts = room_repo.status_counts(conn)
    return {
        "hotel_name": settings_repo.hotel_name(conn),
        "total_rooms": len(rooms),
        "counts": counts,
        "floors": [
            {"floor": floor, "rooms": by_floor[floor]} for floor in sorted(by_floor)
        ],
        "generated_at": now_str(),
    }


def list_rooms(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    floor: int | None = None,
    room_type_id: int | None = None,
    keyword: str | None = None,
) -> list[dict]:
    rooms = room_repo.list_rooms(
        conn, status=status, floor=floor, room_type_id=room_type_id, keyword=keyword
    )
    in_house = {int(s["room_id"]): s for s in stay_repo.list_in_house(conn)}
    day = date_str(today_fn())
    return [to_room_out(r, in_house.get(int(r["id"])), today=day) for r in rooms]


def get_room(conn: sqlite3.Connection, room_id: int) -> dict:
    row = require_room(conn, room_id)
    stay = stay_repo.get_in_house_by_room(conn, room_id)
    return to_room_out(row, stay)


def create_room(conn: sqlite3.Connection, body: RoomCreate) -> dict:
    if room_repo.get_room_by_no(conn, body.room_no) is not None:
        raise AppError("ROOM_NO_EXISTS")
    room_type = room_repo.get_type(conn, body.room_type_id)
    if room_type is None:
        raise AppError("ROOM_TYPE_NOT_FOUND")
    if room_type["status"] != "ON":
        raise AppError("ROOM_TYPE_OFF", "该房型已停用，请先启用房型再新增房间")

    with write_tx(conn):
        room_id = room_repo.insert_room(
            conn,
            room_no=body.room_no,
            room_type_id=body.room_type_id,
            floor=body.floor,
            note=body.note,
        )
    return get_room(conn, room_id)


def update_room(conn: sqlite3.Connection, room_id: int, body: RoomUpdate) -> dict:
    require_room(conn, room_id)

    fields: dict = {}
    if "room_type_id" in body.model_fields_set:
        room_type = room_repo.get_type(conn, body.room_type_id)
        if room_type is None:
            raise AppError("ROOM_TYPE_NOT_FOUND")
        fields["room_type_id"] = body.room_type_id
    if "floor" in body.model_fields_set:
        fields["floor"] = body.floor
    if "note" in body.model_fields_set:
        fields["note"] = body.note

    with write_tx(conn):
        room_repo.update_room(conn, room_id, fields)
    return get_room(conn, room_id)


def set_status(conn: sqlite3.Connection, room_id: int, body: RoomStatusUpdate) -> dict:
    row = require_room(conn, room_id)
    current = row["status"]
    target = body.status

    if current == "OCCUPIED":
        raise AppError(
            "ROOM_HAS_ACTIVE_STAY",
            "该房间有客人在住，房态由入住单决定；请先办理退房或换房",
        )
    if target not in MANUAL_TRANSITIONS.get(current, set()):
        raise AppError(
            "ROOM_STATUS_INVALID",
            f"不能把房态从「{label(ROOM_STATUS_LABELS, current)}」直接改成"
            f"「{label(ROOM_STATUS_LABELS, target)}」",
        )

    with write_tx(conn):
        room_repo.set_status(conn, room_id, target, body.note)
    return get_room(conn, room_id)


def delete_room(conn: sqlite3.Connection, room_id: int) -> None:
    require_room(conn, room_id)
    if stay_repo.get_in_house_by_room(conn, room_id) is not None:
        raise AppError("ROOM_HAS_ACTIVE_STAY")

    history = conn.execute("SELECT COUNT(*) FROM stays WHERE room_id = ?", (room_id,)).fetchone()[0]
    if int(history) > 0:
        # 房间是历史单据的外键，删掉会让住史失去房间号。改维修/停用即可。
        raise AppError("ROOM_HAS_HISTORY")

    with write_tx(conn):
        room_repo.delete_room(conn, room_id)
