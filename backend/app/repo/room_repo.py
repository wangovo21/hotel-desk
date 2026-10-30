from __future__ import annotations

import sqlite3

from app.core.dates import now_str

# 房间的读取一律带上房型信息：房态卡上要显示"标准大床房 ¥289"，
# 前端不该为了显示一个房型名再发一次请求。
ROOM_SELECT = """
SELECT r.id, r.room_no, r.floor, r.status, r.note,
       r.created_at, r.updated_at,
       t.id               AS room_type_id,
       t.code             AS room_type_code,
       t.name             AS room_type_name,
       t.base_price_cents AS base_price_cents,
       t.capacity         AS capacity
  FROM rooms r
  JOIN room_types t ON t.id = r.room_type_id
"""


# ---------------------------------------------------------------------------
# 房型
# ---------------------------------------------------------------------------
def list_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, (SELECT COUNT(*) FROM rooms r WHERE r.room_type_id = t.id) AS room_count
             FROM room_types t
            ORDER BY t.sort_order, t.id"""
    ).fetchall()


def get_type(conn: sqlite3.Connection, type_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM room_types WHERE id = ?", (type_id,)).fetchone()


def get_type_by_code(conn: sqlite3.Connection, code: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM room_types WHERE code = ?", (code,)).fetchone()


def insert_type(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    base_price_cents: int,
    capacity: int,
    bed_type: str | None,
    status: str,
    sort_order: int,
) -> int:
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO room_types
               (code, name, base_price_cents, capacity, bed_type, status, sort_order,
                created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, name, base_price_cents, capacity, bed_type, status, sort_order, ts, ts),
    )
    return int(cur.lastrowid)


def update_type(conn: sqlite3.Connection, type_id: int, fields: dict) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": now_str()}
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE room_types SET {assignments} WHERE id = ?",
        (*fields.values(), type_id),
    )


def count_rooms_of_type(conn: sqlite3.Connection, type_id: int) -> int:
    return int(
        conn.execute("SELECT COUNT(*) FROM rooms WHERE room_type_id = ?", (type_id,)).fetchone()[0]
    )


# ---------------------------------------------------------------------------
# 房间
# ---------------------------------------------------------------------------
def list_rooms(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    floor: int | None = None,
    room_type_id: int | None = None,
    keyword: str | None = None,
) -> list[sqlite3.Row]:
    sql = ROOM_SELECT + " WHERE 1 = 1"
    params: list = []
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if floor is not None:
        sql += " AND r.floor = ?"
        params.append(floor)
    if room_type_id is not None:
        sql += " AND r.room_type_id = ?"
        params.append(room_type_id)
    if keyword:
        sql += " AND (r.room_no LIKE ? OR t.name LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])
    sql += " ORDER BY r.floor, r.room_no"
    return conn.execute(sql, params).fetchall()


def get_room(conn: sqlite3.Connection, room_id: int) -> sqlite3.Row | None:
    return conn.execute(ROOM_SELECT + " WHERE r.id = ?", (room_id,)).fetchone()


def get_room_by_no(conn: sqlite3.Connection, room_no: str) -> sqlite3.Row | None:
    return conn.execute(ROOM_SELECT + " WHERE r.room_no = ?", (room_no,)).fetchone()


def insert_room(
    conn: sqlite3.Connection,
    *,
    room_no: str,
    room_type_id: int,
    floor: int,
    note: str | None,
) -> int:
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO rooms (room_no, room_type_id, floor, status, note, created_at, updated_at)
           VALUES (?, ?, ?, 'VACANT', ?, ?, ?)""",
        (room_no, room_type_id, floor, note, ts, ts),
    )
    return int(cur.lastrowid)


def update_room(conn: sqlite3.Connection, room_id: int, fields: dict) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": now_str()}
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE rooms SET {assignments} WHERE id = ?",
        (*fields.values(), room_id),
    )


def set_status(conn: sqlite3.Connection, room_id: int, status: str, note: str | None = None) -> None:
    fields: dict = {"status": status, "updated_at": now_str()}
    if note is not None:
        fields["note"] = note
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE rooms SET {assignments} WHERE id = ?", (*fields.values(), room_id))


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM rooms GROUP BY status").fetchall()
    counts = {"VACANT": 0, "OCCUPIED": 0, "CLEANING": 0, "MAINTENANCE": 0}
    for row in rows:
        counts[row["status"]] = int(row["n"])
    return counts


def list_floors(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute("SELECT DISTINCT floor FROM rooms ORDER BY floor").fetchall()
    return [int(r["floor"]) for r in rows]


def delete_room(conn: sqlite3.Connection, room_id: int) -> None:
    conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
