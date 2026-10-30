from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import AdminGuard, get_db
from app.models.room import RoomBoard, RoomCreate, RoomOut, RoomStatusUpdate, RoomUpdate
from app.services import room_service

router = APIRouter(prefix="/rooms", tags=["房间"])

RoomStatusFilter = Literal["VACANT", "OCCUPIED", "CLEANING", "MAINTENANCE"]


@router.get("/board", response_model=RoomBoard, summary="房态看板（按楼层分组）")
def room_board(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """★ 前台默认页的数据源：一次拿全。

    放在 `/rooms/{room_id}` 之前定义，否则 "board" 会被当成 room_id 去解析
    （FastAPI 按注册顺序匹配，这是最常见的踩坑点）。
    """
    return room_service.board(conn)


@router.get("", response_model=list[RoomOut], summary="房间列表（可筛选）")
def list_rooms(
    conn: sqlite3.Connection = Depends(get_db),
    status: RoomStatusFilter | None = Query(None, description="房态"),
    floor: int | None = Query(None, ge=-5, le=200, description="楼层"),
    room_type_id: int | None = Query(None, ge=1, description="房型 id"),
    keyword: str | None = Query(None, max_length=32, description="房号/房型名模糊搜索"),
) -> list[dict]:
    keyword = (keyword or "").strip() or None
    return room_service.list_rooms(
        conn, status=status, floor=floor, room_type_id=room_type_id, keyword=keyword
    )


@router.get("/{room_id}", response_model=RoomOut, summary="房间详情")
def get_room(room_id: int = Path(..., ge=1), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return room_service.get_room(conn, room_id)


@router.post("", response_model=RoomOut, dependencies=[AdminGuard], summary="新增房间")
def create_room(body: RoomCreate, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return room_service.create_room(conn, body)


@router.put(
    "/{room_id}", response_model=RoomOut, dependencies=[AdminGuard], summary="修改房间"
)
def update_room(
    body: RoomUpdate,
    room_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return room_service.update_room(conn, room_id, body)


@router.put(
    "/{room_id}/status",
    response_model=RoomOut,
    dependencies=[AdminGuard],
    summary="切换房态（空闲 / 待清扫 / 维修）",
)
def set_room_status(
    body: RoomStatusUpdate,
    room_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return room_service.set_status(conn, room_id, body)


@router.delete(
    "/{room_id}", dependencies=[AdminGuard], summary="删除房间（无任何入住历史时才允许）"
)
def delete_room(room_id: int = Path(..., ge=1), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    room_service.delete_room(conn, room_id)
    return {"ok": True}
