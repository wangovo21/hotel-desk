from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def connect(db_path: Path | str) -> sqlite3.Connection:
    """统一的连接工厂。三个 PRAGMA 都别删：

    · foreign_keys=ON   —— 默认是关的，关着的时候外键约束只是装饰
    · journal_mode=WAL  —— 读不挡写，前台多人同时查房态才不会互相排队
    · busy_timeout=5000 —— 写锁竞争时不立刻报 "database is locked"
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        path,
        timeout=5.0,
        isolation_level=None,  # 事务由 write_tx 显式管，sqlite3 的隐式事务不要插一脚
        check_same_thread=False,
    )
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def write_tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """写事务。用 BEGIN IMMEDIATE 而不是默认的 DEFERRED：

    DEFERRED 会在第一次写时才拿写锁，于是"先读后写"的逻辑（读房态 → 判空 → 改房态）
    在并发下可能读到旧值再写，出现两张在住单。IMMEDIATE 一开始就拿写锁，
    把这段逻辑变成串行的。这也是 uq_stays_room_in_house 索引之外的第二道保险。
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
