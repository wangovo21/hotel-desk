from __future__ import annotations

from pathlib import Path

from app.db import connect


def probe(db_path: Path | str) -> dict:
    """只读健康探测，**不会凭空空建库**。

    为什么单独一个文件：启动横幅、/api/health、测试脚手架都要问"库到底在不在、
    表齐不齐"，如果三处各写一遍 SQL，schema 改一次就要改三处。
    先把"文件不存在"挡掉再 connect —— 否则 connect 会顺手建一个空库，
    把一个"还没初始化"的问题伪装成"库是好的、只是表都没有"。
    """
    path = Path(db_path)
    if not path.is_file():
        return {
            "ok": False,
            "detail": "数据库文件不存在，请先执行 python -m app.db.init_db --demo",
            "schema_version": 0,
            "tables": 0,
            "missing": [],
        }

    # 延迟导入：init_db 依赖 config / db，probe 被 main.py 在模块级 import，
    # 放在函数里可以避免 import 顺序上的死结。
    from app.db.init_db import EXPECTED_TABLES, SCHEMA_VERSION

    conn = connect(path)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()

    present = {r["name"] for r in rows}
    missing = [t for t in EXPECTED_TABLES if t not in present]

    if missing:
        detail = f"缺少 {len(missing)} 张表（{', '.join(missing[:3])}{'…' if len(missing) > 3 else ''}）"
        ok = False
    elif version != SCHEMA_VERSION:
        detail = f"schema 版本不符（库内 v{version}，代码要求 v{SCHEMA_VERSION}），请重建库"
        ok = False
    else:
        detail = "连接正常"
        ok = True

    return {
        "ok": ok,
        "detail": detail,
        "schema_version": version,
        "tables": len([t for t in EXPECTED_TABLES if t in present]),
        "missing": missing,
    }
