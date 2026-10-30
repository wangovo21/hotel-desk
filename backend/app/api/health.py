from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app import config
from app.api.deps import get_db
from app.core.dates import date_str, today as today_fn
from app.db.probe import probe
from app.repo import settings_repo

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="服务与数据库健康状态")
def health(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """★ 恒返回 200。

    原项目在这种情况下返回 503 —— 那对 k8s 探针是对的，但这套系统的
    "客户端"是前台的浏览器外壳，它要读 body 才能告诉收银员"数据库没建"。
    一个 503 + 空 body 只会显示成"后端不可用"，把真正的原因藏起来。
    所以状态放在 body 的 `db.ok` 里，HTTP 层保持可达。
    """
    db = probe(config.DB_PATH)

    hotel_name = ""
    if db["ok"]:
        try:
            hotel_name = settings_repo.hotel_name(conn)
        except sqlite3.Error:
            hotel_name = ""

    return {
        "app_name": config.APP_NAME,
        "app_version": config.APP_VERSION,
        "app_env": config.APP_ENV,
        "today": date_str(today_fn()),
        "db": db,
        "admin_api_enabled": bool(config.ADMIN_TOKEN),
        "docs_enabled": config.DOCS_ENABLED,
        "hotel_name": hotel_name,
    }
