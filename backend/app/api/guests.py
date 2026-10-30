from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import AdminGuard, Page, get_db, pagination
from app.models.guest import GuestCreate, GuestDetail, GuestPage, GuestUpdate
from app.services import guest_service

router = APIRouter(prefix="/guests", tags=["客人档案"])


@router.get("", response_model=GuestPage, summary="客人列表")
def list_guests(
    conn: sqlite3.Connection = Depends(get_db),
    page: Page = Depends(pagination),
    keyword: str | None = Query(None, max_length=32, description="姓名/手机号/证件号"),
    blacklisted: bool = Query(False, description="只看黑名单"),
) -> dict:
    keyword = (keyword or "").strip() or None
    return guest_service.list_guests(
        conn,
        keyword=keyword,
        blacklisted_only=blacklisted,
        limit=page.limit,
        offset=page.offset,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{guest_id}", response_model=GuestDetail, summary="客人详情（含最近住史）")
def get_guest(
    guest_id: int = Path(..., ge=1), conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return guest_service.get_guest(conn, guest_id)


@router.post("", response_model=GuestDetail, dependencies=[AdminGuard], summary="新增客人档案")
def create_guest(body: GuestCreate, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return guest_service.create_guest(conn, body)


@router.put(
    "/{guest_id}",
    response_model=GuestDetail,
    dependencies=[AdminGuard],
    summary="修改客人信息 / 拉黑",
)
def update_guest(
    body: GuestUpdate,
    guest_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return guest_service.update_guest(conn, guest_id, body)
