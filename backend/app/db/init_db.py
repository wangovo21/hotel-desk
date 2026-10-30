from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import DB_PATH
from app.core.dates import datetime_str, date_str, now_str, today
from app.db import connect, write_tx

SCHEMA_VERSION = 2

EXPECTED_TABLES = [
    "room_types",
    "rooms",
    "guests",
    "stays",
    "stay_charges",
    "stay_events",
    "room_cards",
    "settings",
]

# ---- 基础数据：房型 ---------------------------------------------------------
SEED_ROOM_TYPES = [
    # code, name, base_price_cents, capacity, bed_type, sort_order
    ("STD",   "标准大床房",  28_900, 2, "1.8m 大床",     1),
    ("TWN",   "标准双床房",  30_900, 2, "1.2m 双床 ×2",  2),
    ("FAM",   "家庭房",      45_900, 3, "1.5m + 1.2m",   3),
    ("SUITE", "行政套房",    89_900, 4, "2.0m 大床 + 客厅", 4),
]

# ---- 基础数据：房间 ---------------------------------------------------------
# 20 间房，8/9 楼标准层，10 楼家庭房与套房
SEED_ROOMS = [
    *[(f"83{i:02d}", "STD", 8, "VACANT", None) for i in range(1, 7)],
    ("8307", "TWN", 8, "VACANT", None),
    ("8308", "TWN", 8, "VACANT", None),
    *[(f"93{i:02d}", "STD", 9, "VACANT", None) for i in range(1, 7)],
    ("9307", "TWN", 9, "VACANT", None),
    ("9308", "TWN", 9, "VACANT", None),
    ("10301", "FAM", 10, "VACANT", None),
    ("10302", "FAM", 10, "VACANT", None),
    ("10303", "SUITE", 10, "VACANT", None),
    ("10304", "SUITE", 10, "MAINTENANCE", "空调检修"),
]

# ---- 业务参数 ---------------------------------------------------------------
SEED_SETTINGS = [
    ("HOTEL_NAME", "云栖酒店", "显示在页面标题与入住单抬头"),
    ("DEFAULT_DEPOSIT_CENTS", "30000", "入住默认押金（分）＝ 300 元，前台可改"),
    ("MAX_ROOM_RATE_CENTS", "500000", "单间夜房价上限（分）＝ 5000 元，防误输入"),
    ("CHECKOUT_TIME", "12:00", "退房时限（仅用于前台提示，本系统不自动加收半日房费）"),
    ("MAX_CHARGE_CENTS", "100000", "单笔杂费上限（分）＝ 1000 元"),
]

# ---- 演示数据 ---------------------------------------------------------------
SEED_DEMO_GUESTS = [
    # name, id_type, id_no, phone, gender（证件号是本模拟系统的 6 位虚拟号）
    ("张伟", "ID_CARD",  "100001", "13800000001", "MALE"),
    ("李娜", "ID_CARD",  "100002", "13800000002", "FEMALE"),
    ("陈明", "PASSPORT", "600003", "13800000003", "MALE"),
    ("王芳", "ID_CARD",  "100004", "13800000004", "FEMALE"),
]


def schema_sql() -> str:
    return (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(schema_sql())


def _is_empty(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] == 0


def seed_reference_data(conn: sqlite3.Connection) -> None:
    """房型 / 房间 / 参数。幂等：已有数据就跳过，不覆盖运营改过的值。"""
    with write_tx(conn):
        ts = now_str()
        if _is_empty(conn, "room_types"):
            conn.executemany(
                """INSERT INTO room_types
                       (code, name, base_price_cents, capacity, bed_type, sort_order,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(c, n, p, cap, bed, sort, ts, ts)
                 for c, n, p, cap, bed, sort in SEED_ROOM_TYPES],
            )

        if _is_empty(conn, "rooms"):
            type_ids = {
                row["code"]: row["id"]
                for row in conn.execute("SELECT id, code FROM room_types").fetchall()
            }
            conn.executemany(
                """INSERT INTO rooms
                       (room_no, room_type_id, floor, status, note, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(no, type_ids[code], floor, status, note, ts, ts)
                 for no, code, floor, status, note in SEED_ROOMS],
            )

        if _is_empty(conn, "settings"):
            conn.executemany(
                "INSERT INTO settings (key, value, description, updated_at) VALUES (?, ?, ?, ?)",
                [(k, v, d, ts) for k, v, d in SEED_SETTINGS],
            )


def seed_demo(conn: sqlite3.Connection) -> None:
    """演示数据：4 位客人 + 1 张历史单 + 2 张在住单 + 房态。

    刻意覆盖四种房态和三种单据状态，这样打开界面第一眼就能看到
    "空房/在住/待清扫/维修"和"在住/已退房"的样式，不用自己先造数据。
    """
    with write_tx(conn):
        ts = now_str()
        for name, id_type, id_no, phone, gender in SEED_DEMO_GUESTS:
            exists = conn.execute(
                "SELECT id FROM guests WHERE id_type = ? AND id_no = ?", (id_type, id_no)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO guests (name, id_type, id_no, phone, gender, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, id_type, id_no, phone, gender, ts, ts),
            )

        if not _is_empty(conn, "stays"):
            return

        def gid(id_no: str) -> int:
            return int(conn.execute("SELECT id FROM guests WHERE id_no = ?", (id_no,)).fetchone()[0])

        def room_of(room_no: str) -> sqlite3.Row:
            return conn.execute(
                """SELECT r.id, r.room_no, t.base_price_cents
                   FROM rooms r JOIN room_types t ON t.id = r.room_type_id
                   WHERE r.room_no = ?""",
                (room_no,),
            ).fetchone()

        def insert_stay(
            *,
            seq: int,
            guest_no: str,
            room_no: str,
            day_offset: int,
            nights: int,
            deposit: int,
            status: str,
            rate: int | None = None,
        ) -> int:
            room = room_of(room_no)
            checkin_day = today() + timedelta(days=day_offset)
            stay_no = f"RS{checkin_day.strftime('%Y%m%d')}-{seq:03d}"
            checkout_at = (
                datetime_str(checkin_day + timedelta(days=nights), "12:05") if status != "IN_HOUSE" else None
            )
            cur = conn.execute(
                """INSERT INTO stays
                       (stay_no, guest_id, room_id, room_rate_cents, checkin_at,
                        expected_checkout_date, checkout_at, nights, deposit_cents,
                        adults, children, status, operator, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stay_no,
                    gid(guest_no),
                    int(room["id"]),
                    rate or int(room["base_price_cents"]),
                    datetime_str(checkin_day, "14:10"),
                    date_str(checkin_day + timedelta(days=nights)),
                    checkout_at,
                    nights,
                    deposit,
                    1,
                    0,
                    status,
                    "演示",
                    ts,
                    ts,
                ),
            )
            stay_id = int(cur.lastrowid)

            conn.execute(
                """INSERT INTO stay_events
                       (stay_id, type, from_value, to_value, amount_cents, operator, remark, created_at)
                   VALUES (?, 'CHECKIN', NULL, ?, 0, '演示', '演示数据', ?)""",
                (stay_id, room_no, ts),
            )

            if status == "CHECKED_OUT":
                room_fee = (rate or int(room["base_price_cents"])) * nights
                conn.execute(
                    """INSERT INTO stay_charges
                           (stay_id, category, name, amount_cents, quantity, operator, created_at)
                       VALUES (?, 'ROOM', ?, ?, ?, '演示', ?)""",
                    (stay_id, f"房费（{nights} 间夜）", room_fee, nights, ts),
                )
                conn.execute(
                    """INSERT INTO stay_events
                           (stay_id, type, from_value, to_value, amount_cents, operator, remark, created_at)
                       VALUES (?, 'CHECKOUT', ?, NULL, ?, '演示', '演示数据', ?)""",
                    (stay_id, date_str(checkin_day + timedelta(days=nights)), room_fee, ts),
                )
            return stay_id

        # 历史已退房单：陈明，3 天前入住 1 晚，房间现在待清扫
        insert_stay(seq=1, guest_no="600003", room_no="8303",
                    day_offset=-3, nights=1, deposit=30_000, status="CHECKED_OUT")
        # 在住单 1：张伟，今天 14:10 入住，明天离店
        insert_stay(seq=2, guest_no="100001", room_no="8301",
                    day_offset=0, nights=1, deposit=30_000, status="IN_HOUSE")
        # 在住单 2：李娜，昨天入住 2 晚，今天加过一笔餐饮杂费
        stay2 = insert_stay(seq=3, guest_no="100002", room_no="8302",
                            day_offset=-1, nights=2, deposit=50_000, status="IN_HOUSE")
        conn.execute(
            """INSERT INTO stay_charges
                   (stay_id, category, name, amount_cents, quantity, operator, remark, created_at)
               VALUES (?, 'FOOD', '客房送餐', 8800, 1, '演示', '晚餐两份', ?)""",
            (stay2, ts),
        )
        conn.execute(
            """INSERT INTO stay_events
                   (stay_id, type, from_value, to_value, amount_cents, operator, remark, created_at)
               VALUES (?, 'ADD_CHARGE', NULL, '客房送餐', 8800, '演示', NULL, ?)""",
            (stay2, ts),
        )

        # 演示房卡：张伟在住单发一张在用卡，让"房卡"区块开箱就有内容
        stay1_row = conn.execute(
            """SELECT s.id, r.room_no FROM stays s JOIN rooms r ON r.id = s.room_id
                WHERE r.room_no = '8301' AND s.status = 'IN_HOUSE'"""
        ).fetchone()
        if stay1_row is not None:
            conn.execute(
                """INSERT INTO room_cards
                       (stay_id, card_no, room_no, status, issued_at, issued_by,
                        created_at, updated_at)
                   VALUES (?, 'NF-0001', ?, 'ACTIVE', ?, '演示', ?, ?)""",
                (int(stay1_row["id"]), stay1_row["room_no"], ts, ts, ts),
            )
            conn.execute(
                """INSERT INTO stay_events
                       (stay_id, type, from_value, to_value, amount_cents, operator, remark, created_at)
                   VALUES (?, 'ISSUE_CARD', NULL, 'NF-0001', 0, '演示', '演示数据', ?)""",
                (int(stay1_row["id"]), ts),
            )

        conn.execute(
            "UPDATE rooms SET status = 'OCCUPIED', updated_at = ? WHERE room_no IN ('8301','8302')",
            (ts,),
        )
        conn.execute(
            "UPDATE rooms SET status = 'CLEANING', updated_at = ? WHERE room_no = '8303'",
            (ts,),
        )


def self_check(conn: sqlite3.Connection) -> list[str]:
    """建库后自检：把"建了但其实不可用"的情况在初始化阶段就暴露出来。

    第二项（CHECK 是否真的生效）要真插一条非法数据才算数 —— 只看 sqlite_master
    里的 DDL 文本会被"字符串里有 CHECK 但拼错了列名"骗过去。
    整段包在事务里最后 rollback，探针数据不会留下。
    """
    problems: list[str] = []
    for table in EXPECTED_TABLES:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if row is None:
            problems.append(f"缺少表 {table}")

    if problems:  # 表都不齐，后面的约束探针没有意义
        return problems

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT id FROM room_types LIMIT 1").fetchone()
        if row is not None:
            type_id = int(row["id"])
        else:
            type_id = int(
                conn.execute(
                    """INSERT INTO room_types
                           (code, name, base_price_cents, capacity, created_at, updated_at)
                       VALUES ('__probe__', '探针房型', 1, 1, '', '')"""
                ).lastrowid
            )
        try:
            conn.execute(
                """INSERT INTO rooms (room_no, room_type_id, floor, status, created_at, updated_at)
                   VALUES ('__probe__', ?, 1, 'INVALID', '', '')""",
                (type_id,),
            )
        except sqlite3.IntegrityError:
            pass  # 期望被 CHECK 挡住
        else:
            problems.append("rooms.status 的 CHECK 约束没有生效")
    finally:
        conn.rollback()

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="建库 / 灌演示数据 / 自检")
    parser.add_argument("--demo", action="store_true", help="灌入演示数据（房型+20 间房+演示入住单）")
    parser.add_argument("--force", action="store_true", help="删除已存在的库文件后重建（会丢数据！）")
    parser.add_argument("--check", action="store_true", help="只做自检，不建表")
    parser.add_argument("--db", default=str(DB_PATH), help=f"库文件路径，默认 {DB_PATH}")
    args = parser.parse_args(argv)

    path = Path(args.db)
    if args.force and path.exists():
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
        print(f"[重置] 已删除 {path}")

    conn = connect(path)
    try:
        if args.check:
            problems = self_check(conn)
            print("[自检] 通过" if not problems else "[自检] 发现问题：\n  " + "\n  ".join(problems))
            return 0 if not problems else 1

        apply_schema(conn)
        seed_reference_data(conn)
        if args.demo:
            seed_demo(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

        problems = self_check(conn)
        if problems:
            print("[失败] 自检未通过：\n  " + "\n  ".join(problems))
            return 1

        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("room_types", "rooms", "guests", "stays")
        }
        print(f"[完成] {path}")
        print(f"       房型 {counts['room_types']} / 房间 {counts['rooms']} / "
              f"客人 {counts['guests']} / 入住单 {counts['stays']}")
        print(f"       schema v{SCHEMA_VERSION}，{len(EXPECTED_TABLES)} 张表")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
