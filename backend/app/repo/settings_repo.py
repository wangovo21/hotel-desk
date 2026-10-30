from __future__ import annotations

import sqlite3

from app.core.dates import now_str


def list_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM settings ORDER BY key").fetchall()


def get_value(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_int(conn: sqlite3.Connection, key: str, default: int) -> int:
    """读整数参数。脏值不许把服务弄崩：解析失败退回默认值。

    为什么容错而不是抛错：这些值可能被运维在数据库里手改过，
    前台正在办入住时因为一个参数写错就 500，比按默认值继续办更糟。
    """
    raw = get_value(conn, key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (key, value, now_str()),
    )


def hotel_name(conn: sqlite3.Connection) -> str:
    return get_value(conn, "HOTEL_NAME", "酒店") or "酒店"
