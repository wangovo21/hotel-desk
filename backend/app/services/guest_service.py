from __future__ import annotations

import sqlite3

from app.core.errors import AppError
from app.core.labels import GENDER_LABELS, ID_TYPE_LABELS, STAY_STATUS_LABELS, label
from app.db import write_tx
from app.models.guest import GuestCreate, GuestUpdate
from app.repo import guest_repo
from app.services import serializers


def to_brief(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "id_type": row["id_type"],
        "id_type_label": label(ID_TYPE_LABELS, row["id_type"]),
        "id_no": row["id_no"],
        "id_no_masked": serializers.mask_id_no(row["id_no"]),
        "phone": row["phone"],
        "gender": row["gender"],
        "gender_label": label(GENDER_LABELS, row["gender"]),
        "blacklisted": bool(row["blacklisted"]),
        "stay_count": int(row["stay_count"]) if "stay_count" in row.keys() else 0,
        "last_checkin_at": row["last_checkin_at"] if "last_checkin_at" in row.keys() else None,
        "created_at": row["created_at"],
    }


def list_guests(
    conn: sqlite3.Connection,
    *,
    keyword: str | None,
    blacklisted_only: bool,
    limit: int,
    offset: int,
    page: int,
    page_size: int,
) -> dict:
    rows, total = guest_repo.list_guests(
        conn, keyword=keyword, blacklisted_only=blacklisted_only, limit=limit, offset=offset
    )
    return {
        "items": [to_brief(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_guest(conn: sqlite3.Connection, guest_id: int) -> dict:
    row = guest_repo.get_guest(conn, guest_id)
    if row is None:
        raise AppError("GUEST_NOT_FOUND")

    detail = to_brief(row)
    detail.update(
        {
            "remark": row["remark"],
            "updated_at": row["updated_at"],
            "stays": [
                {
                    "stay_id": s["stay_id"],
                    "stay_no": s["stay_no"],
                    "room_no": s["room_no"],
                    "checkin_at": s["checkin_at"],
                    "checkout_at": s["checkout_at"],
                    "nights": s["nights"],
                    "status": s["status"],
                    "status_label": label(STAY_STATUS_LABELS, s["status"]),
                }
                for s in guest_repo.stay_history(conn, guest_id)
            ],
        }
    )
    return detail


def create_guest(conn: sqlite3.Connection, body: GuestCreate) -> dict:
    if guest_repo.find_by_identity(conn, body.id_type, body.id_no) is not None:
        raise AppError("GUEST_ID_EXISTS")

    with write_tx(conn):
        guest_id = guest_repo.insert_guest(
            conn,
            name=body.name,
            id_type=body.id_type,
            id_no=body.id_no,
            phone=body.phone,
            gender=body.gender,
            remark=body.remark,
        )
    return get_guest(conn, guest_id)


def update_guest(conn: sqlite3.Connection, guest_id: int, body: GuestUpdate) -> dict:
    if guest_repo.get_guest(conn, guest_id) is None:
        raise AppError("GUEST_NOT_FOUND")

    fields: dict = {}
    if "name" in body.model_fields_set:
        fields["name"] = body.name
    if "phone" in body.model_fields_set:
        fields["phone"] = body.phone
    if "gender" in body.model_fields_set:
        fields["gender"] = body.gender
    if "remark" in body.model_fields_set:
        fields["remark"] = body.remark
    if "blacklisted" in body.model_fields_set:
        fields["blacklisted"] = 1 if body.blacklisted else 0

    with write_tx(conn):
        guest_repo.update_guest(conn, guest_id, fields)
    return get_guest(conn, guest_id)


def resolve_for_checkin(conn: sqlite3.Connection, guest_id: int) -> sqlite3.Row:
    """入住时按 id 取客人，并做黑名单拦截。"""
    row = guest_repo.get_guest(conn, guest_id)
    if row is None:
        raise AppError("GUEST_NOT_FOUND")
    if row["blacklisted"]:
        raise AppError("GUEST_BLACKLISTED", f"客人「{row['name']}」已被列入黑名单")
    return row


def upsert_for_checkin(conn: sqlite3.Connection, body: GuestCreate) -> int:
    """新客录入：证件号已存在就复用档案，不报错。

    为什么复用而不是报 GUEST_ID_EXISTS：前台最常见的场景就是老客回来住，
    收银员顺手把身份证再录一遍。这时候跳一个红框说"该证件已登记"，
    等于强迫他退出去搜一遍老客 —— 而搜索结果和刚录的信息是同一份。
    复用后只补空字段（比如上次没留手机号），不覆盖已有值。
    """
    existing = guest_repo.find_by_identity(conn, body.id_type, body.id_no)
    if existing is None:
        return guest_repo.insert_guest(
            conn,
            name=body.name,
            id_type=body.id_type,
            id_no=body.id_no,
            phone=body.phone,
            gender=body.gender,
            remark=body.remark,
        )

    if existing["blacklisted"]:
        raise AppError("GUEST_BLACKLISTED", f"客人「{existing['name']}」已被列入黑名单")

    patch: dict = {}
    if not existing["phone"] and body.phone:
        patch["phone"] = body.phone
    if existing["gender"] == "UNKNOWN" and body.gender != "UNKNOWN":
        patch["gender"] = body.gender
    if patch:
        guest_repo.update_guest(conn, int(existing["id"]), patch)
    return int(existing["id"])
