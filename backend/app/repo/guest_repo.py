from __future__ import annotations

import sqlite3

from app.core.dates import now_str

# 列表里把住史指标一起算出来（住过几次、最近一次入住）：
# 前台在名单上就能看出"熟客还是新客"，不用逐个点开。
GUEST_SELECT = """
SELECT g.*,
       (SELECT COUNT(*) FROM stays s WHERE s.guest_id = g.id) AS stay_count,
       (SELECT MAX(s.created_at) FROM stays s WHERE s.guest_id = g.id) AS last_checkin_at
  FROM guests g
"""


def list_guests(
    conn: sqlite3.Connection,
    *,
    keyword: str | None,
    blacklisted_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], int]:
    where = " WHERE 1 = 1"
    params: list = []
    if keyword:
        where += " AND (g.name LIKE ? OR g.phone LIKE ? OR g.id_no LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like])
    if blacklisted_only:
        where += " AND g.blacklisted = 1"

    total = int(conn.execute(f"SELECT COUNT(*) FROM guests g{where}", params).fetchone()[0])
    rows = conn.execute(
        GUEST_SELECT + where + " ORDER BY g.id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return rows, total


def get_guest(conn: sqlite3.Connection, guest_id: int) -> sqlite3.Row | None:
    return conn.execute(GUEST_SELECT + " WHERE g.id = ?", (guest_id,)).fetchone()


def find_by_identity(conn: sqlite3.Connection, id_type: str, id_no: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM guests WHERE id_type = ? AND id_no = ?", (id_type, id_no)
    ).fetchone()


def insert_guest(
    conn: sqlite3.Connection,
    *,
    name: str,
    id_type: str,
    id_no: str,
    phone: str | None,
    gender: str,
    remark: str | None = None,
) -> int:
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO guests (name, id_type, id_no, phone, gender, remark, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, id_type, id_no, phone, gender, remark, ts, ts),
    )
    return int(cur.lastrowid)


def update_guest(conn: sqlite3.Connection, guest_id: int, fields: dict) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": now_str()}
    assignments = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE guests SET {assignments} WHERE id = ?", (*fields.values(), guest_id))


def stay_history(conn: sqlite3.Connection, guest_id: int, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT s.id AS stay_id, s.stay_no, r.room_no, s.checkin_at, s.checkout_at,
                  s.nights, s.status
             FROM stays s JOIN rooms r ON r.id = s.room_id
            WHERE s.guest_id = ?
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ?""",
        (guest_id, limit),
    ).fetchall()
