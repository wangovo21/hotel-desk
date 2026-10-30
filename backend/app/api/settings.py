from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.api.deps import AdminGuard, get_db
from app.models.setting import SettingOut, SettingUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["业务参数"])


@router.get("", response_model=list[SettingOut], summary="参数列表")
def list_settings(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    return settings_service.list_settings(conn)


@router.put(
    "",
    response_model=SettingOut,
    dependencies=[AdminGuard],
    summary="修改一个参数（key 必须在册）",
)
def update_setting(body: SettingUpdate, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return settings_service.update_setting(conn, body)
