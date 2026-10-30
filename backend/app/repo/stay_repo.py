from __future__ import annotations

import sqlite3

from app.core.dates import now_str

STAY_SELECT = """
SELECT s.*,
       g.name      AS guest_name,
       g.phone     AS guest_phone,
       g.id_no     AS guest_id_no,
       g.id_type   AS guest_id_type,
       g.blacklisted AS guest_blacklisted,
       r.room_no   AS room_no,
       r.floor     AS floor,
       t.name      AS room_type_name
  FROM stays s
  JOIN guests g     ON g.id = s.guest_id
  JOIN rooms r      ON r.id = s.room_id
  JOIN room_types t ON t.id = r.room_type_id
"""


# ---------------------------------------------------------------------------
# 入住单
# ---------------------------------------------------------------------------
def next_stay_no(conn: sqlite3.Connection, day: str) -> str:
    """单号 RS20261023-001：按天连号。

    用 MAX(尾号)+1 而不是 COUNT+1：万一有人手工删过单据，COUNT 会重号。
    """
    prefix = f"RS{day}-"
    row = conn.execute(
        "SELECT MAX(CAST(substr(stay_no, ?) AS INTEGER)) AS n FROM stays WHERE stay_no LIKE ?",
        (len(prefix) + 1, f"{prefix}%"),
    ).fetchone()
    seq = int(row["n"] or 0) + 1
    return f"{prefix}{seq:03d}"


def insert_stay(
    conn: sqlite3.Connection,
    *,
    stay_no: str,
    guest_id: int,
    room_id: int,
    room_rate_cents: int,
    checkin_at: str,
    expected_checkout_date: str,
    nights: int,
    deposit_cents: int,
    adults: int,
    children: int,
    operator: str | None,
    remark: str | None,
) -> int:
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO stays
               (stay_no, guest_id, room_id, room_rate_cents, checkin_at,
                expected_checkout_date, nights, deposit_cents, adults, children,
                status, operator, remark, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_HOUSE', ?, ?, ?, ?)""",
        (
            stay_no, guest_id, room_id, room_rate_cents, checkin_at,
            expected_checkout_date, nights, deposit_cents, adults, children,
            operator, remark, ts, ts,
        ),
    )
    return int(cur.lastrowid)


def get_stay(conn: sqlite3.Connection, stay_id: int) -> sqlite3.Row | None:
    return conn.execute(STAY_SELECT + " WHERE s.id = ?", (stay_id,)).fetchone()


def get_in_house_by_room(conn: sqlite3.Connection, room_id: int) -> sqlite3.Row | None:
    return conn.execute(
        STAY_SELECT + " WHERE s.room_id = ? AND s.status = 'IN_HOUSE'", (room_id,)
    ).fetchone()


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
) -> tuple[list[sqlite3.Row], int]:
    where = " WHERE 1 = 1"
    params: list = []
    if status:
        where += " AND s.status = ?"
        params.append(status)
    if keyword:
        where += " AND (g.name LIKE ? OR g.phone LIKE ? OR s.stay_no LIKE ? OR r.room_no LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like, like])
    if date_from:
        where += " AND date(s.checkin_at) >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date(s.checkin_at) <= ?"
        params.append(date_to)
    if room_id is not None:
        where += " AND s.room_id = ?"
        params.append(room_id)

    total = int(
        conn.execute(
            """SELECT COUNT(*) FROM stays s
                 JOIN guests g ON g.id = s.guest_id
                 JOIN rooms r  ON r.id = s.room_id""" + where,
            params,
        ).fetchone()[0]
    )
    rows = conn.execute(
        STAY_SELECT + where + " ORDER BY s.created_at DESC, s.id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return rows, total


def list_in_house(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        STAY_SELECT + " WHERE s.status = 'IN_HOUSE' ORDER BY s.expected_checkout_date, s.id"
    ).fetchall()


def update_expected(conn: sqlite3.Connection, stay_id: int, date: str, nights: int) -> None:
    conn.execute(
        """UPDATE stays SET expected_checkout_date = ?, nights = ?, updated_at = ?
            WHERE id = ?""",
        (date, nights, now_str(), stay_id),
    )


def update_room(conn: sqlite3.Connection, stay_id: int, room_id: int, rate_cents: int) -> None:
    conn.execute(
        "UPDATE stays SET room_id = ?, room_rate_cents = ?, updated_at = ? WHERE id = ?",
        (room_id, rate_cents, now_str(), stay_id),
    )


def mark_checked_out(
    conn: sqlite3.Connection,
    stay_id: int,
    *,
    checkout_at: str,
    nights: int,
    remark: str | None,
) -> None:
    conn.execute(
        """UPDATE stays
              SET status = 'CHECKED_OUT', checkout_at = ?, nights = ?,
                  remark = COALESCE(?, remark), updated_at = ?
            WHERE id = ?""",
        (checkout_at, nights, remark, now_str(), stay_id),
    )


def mark_cancelled(conn: sqlite3.Connection, stay_id: int, *, checkout_at: str, remark: str | None) -> None:
    conn.execute(
        """UPDATE stays
              SET status = 'CANCELLED', checkout_at = ?,
                  remark = COALESCE(?, remark), updated_at = ?
            WHERE id = ?""",
        (checkout_at, remark, now_str(), stay_id),
    )


# ---------------------------------------------------------------------------
# 杂费
# ---------------------------------------------------------------------------
def insert_charge(
    conn: sqlite3.Connection,
    *,
    stay_id: int,
    category: str,
    name: str,
    amount_cents: int,
    quantity: int,
    operator: str | None,
    remark: str | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO stay_charges
               (stay_id, category, name, amount_cents, quantity, operator, remark, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (stay_id, category, name, amount_cents, quantity, operator, remark, now_str()),
    )
    return int(cur.lastrowid)


def list_charges(conn: sqlite3.Connection, stay_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stay_charges WHERE stay_id = ? ORDER BY id", (stay_id,)
    ).fetchall()


def charges_total(conn: sqlite3.Connection, stay_id: int) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(amount_cents * quantity), 0) FROM stay_charges WHERE stay_id = ?",
            (stay_id,),
        ).fetchone()[0]
    )


def count_non_room_charges(conn: sqlite3.Connection, stay_id: int) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM stay_charges WHERE stay_id = ? AND category <> 'ROOM'",
            (stay_id,),
        ).fetchone()[0]
    )


# ---------------------------------------------------------------------------
# 操作留痕
# ---------------------------------------------------------------------------
def insert_event(
    conn: sqlite3.Connection,
    *,
    stay_id: int,
    type_: str,
    from_value: str | None = None,
    to_value: str | None = None,
    amount_cents: int = 0,
    operator: str | None = None,
    remark: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO stay_events
               (stay_id, type, from_value, to_value, amount_cents, operator, remark, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (stay_id, type_, from_value, to_value, amount_cents, operator, remark, now_str()),
    )
    return int(cur.lastrowid)


def list_events(conn: sqlite3.Connection, stay_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stay_events WHERE stay_id = ? ORDER BY id", (stay_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# 看板用的聚合（全部在 SQL 里算，别把全表拉到 Python 再数）
# ---------------------------------------------------------------------------
def count_checkins_on(conn: sqlite3.Connection, day: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM stays WHERE date(checkin_at) = ? AND status <> 'CANCELLED'",
            (day,),
        ).fetchone()[0]
    )


def count_checkouts_on(conn: sqlite3.Connection, day: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM stays WHERE date(checkout_at) = ? AND status = 'CHECKED_OUT'",
            (day,),
        ).fetchone()[0]
    )


def revenue_on(conn: sqlite3.Connection, day: str) -> int:
    """当日营收 = 当日退房的单据上全部费用（房费 + 杂费）。

    口径写死在这里：营收按**结账日**归集，不按入住日分摊 —— 前台的日报
    跟收银机的钱箱对得上，比会计口径的权责发生制更重要。
    """
    return int(
        conn.execute(
            """SELECT COALESCE(SUM(c.amount_cents * c.quantity), 0)
                 FROM stay_charges c
                 JOIN stays s ON s.id = c.stay_id
                WHERE s.status = 'CHECKED_OUT' AND date(s.checkout_at) = ?""",
            (day,),
        ).fetchone()[0]
    )


def deposits_in_house(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(deposit_cents), 0) FROM stays WHERE status = 'IN_HOUSE'"
        ).fetchone()[0]
    )


def guests_in_house(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(adults + children), 0) FROM stays WHERE status = 'IN_HOUSE'"
        ).fetchone()[0]
    )


def due_out_on(conn: sqlite3.Connection, day: str) -> list[sqlite3.Row]:
    return conn.execute(
        STAY_SELECT
        + " WHERE s.status = 'IN_HOUSE' AND s.expected_checkout_date = ?"
          " ORDER BY s.id",
        (day,),
    ).fetchall()


def overdue_on(conn: sqlite3.Connection, day: str) -> list[sqlite3.Row]:
    return conn.execute(
        STAY_SELECT
        + " WHERE s.status = 'IN_HOUSE' AND s.expected_checkout_date < ?"
          " ORDER BY s.expected_checkout_date",
        (day,),
    ).fetchall()


def recent_checkouts(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        STAY_SELECT
        + " WHERE s.status = 'CHECKED_OUT' ORDER BY s.checkout_at DESC, s.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def checkins_grouped(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT date(checkin_at) AS d, COUNT(*) AS n FROM stays
            WHERE status <> 'CANCELLED' AND date(checkin_at) BETWEEN ? AND ?
            GROUP BY d""",
        (date_from, date_to),
    ).fetchall()
    return {r["d"]: int(r["n"]) for r in rows}


def checkouts_grouped(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT date(checkout_at) AS d, COUNT(*) AS n FROM stays
            WHERE status = 'CHECKED_OUT' AND date(checkout_at) BETWEEN ? AND ?
            GROUP BY d""",
        (date_from, date_to),
    ).fetchall()
    return {r["d"]: int(r["n"]) for r in rows}


def revenue_grouped(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT date(s.checkout_at) AS d, SUM(c.amount_cents * c.quantity) AS cents
             FROM stay_charges c JOIN stays s ON s.id = c.stay_id
            WHERE s.status = 'CHECKED_OUT' AND date(s.checkout_at) BETWEEN ? AND ?
            GROUP BY d""",
        (date_from, date_to),
    ).fetchall()
    return {r["d"]: int(r["cents"] or 0) for r in rows}


def usage_by_type(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.id, t.name,
                  COUNT(r.id) AS total,
                  COALESCE(SUM(CASE WHEN r.status = 'OCCUPIED' THEN 1 ELSE 0 END), 0) AS occupied
             FROM room_types t LEFT JOIN rooms r ON r.room_type_id = t.id
            GROUP BY t.id
            ORDER BY t.sort_order, t.id"""
    ).fetchall()
