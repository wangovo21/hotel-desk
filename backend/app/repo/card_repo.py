"""房卡的数据访问。**只写 SQL**，规则（能不能发、要不要收回）在 card_service。

退卡是逻辑回收：行永远不删，`status='REVOKED'` + 退卡时刻/经手人/原因，
前台有纠纷时能回答"这张卡几点发出去、几点收回来"。
"""
from __future__ import annotations

import sqlite3

from app.core.dates import now_str

CARD_SELECT = "SELECT * FROM room_cards"


def insert_card(
    conn: sqlite3.Connection,
    *,
    stay_id: int,
    card_no: str,
    room_no: str,
    issued_by: str | None,
) -> int:
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO room_cards
               (stay_id, card_no, room_no, status, issued_at, issued_by, created_at, updated_at)
           VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?)""",
        (stay_id, card_no, room_no, ts, issued_by, ts, ts),
    )
    return int(cur.lastrowid)


def get_card(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row | None:
    return conn.execute(CARD_SELECT + " WHERE id = ?", (card_id,)).fetchone()


def find_active_by_no(conn: sqlite3.Connection, card_no: str) -> sqlite3.Row | None:
    return conn.execute(
        CARD_SELECT + " WHERE card_no = ? AND status = 'ACTIVE'", (card_no,)
    ).fetchone()


def list_by_stay(conn: sqlite3.Connection, stay_id: int) -> list[sqlite3.Row]:
    """在用的排前面，同状态按发卡时间倒序 —— 最新动作一眼可见。"""
    return conn.execute(
        CARD_SELECT
        + " WHERE stay_id = ? ORDER BY CASE status WHEN 'ACTIVE' THEN 0 ELSE 1 END, id DESC",
        (stay_id,),
    ).fetchall()


def count_active_by_stay(conn: sqlite3.Connection, stay_id: int) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM room_cards WHERE stay_id = ? AND status = 'ACTIVE'",
            (stay_id,),
        ).fetchone()[0]
    )


def revoke_card(
    conn: sqlite3.Connection,
    card_id: int,
    *,
    revoked_by: str | None,
    reason: str | None,
) -> None:
    conn.execute(
        """UPDATE room_cards
              SET status = 'REVOKED', revoked_at = ?, revoked_by = ?,
                  revoke_reason = ?, updated_at = ?
            WHERE id = ?""",
        (now_str(), revoked_by, reason, now_str(), card_id),
    )


def revoke_all_for_stay(conn: sqlite3.Connection, stay_id: int, *, reason: str) -> int:
    """整单回收（退房/撤销时用）。返回收回的张数，供留痕写 remark。"""
    cur = conn.execute(
        """UPDATE room_cards
              SET status = 'REVOKED', revoked_at = ?, revoke_reason = ?, updated_at = ?
            WHERE stay_id = ? AND status = 'ACTIVE'""",
        (now_str(), reason, now_str(), stay_id),
    )
    return cur.rowcount if cur.rowcount > 0 else 0


def active_cards_of_stay(conn: sqlite3.Connection, stay_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        CARD_SELECT + " WHERE stay_id = ? AND status = 'ACTIVE' ORDER BY id",
        (stay_id,),
    ).fetchall()
