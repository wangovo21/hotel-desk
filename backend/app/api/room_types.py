from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Path

from app.api.deps import AdminGuard, get_db
from app.models.room import RoomTypeCreate, RoomTypeOut, RoomTypeUpdate
from app.services import room_service

router = APIRouter(prefix="/room-types", tags=["房型"])


@router.get("", response_model=list[RoomTypeOut], summary="房型列表")
def list_room_types(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    return room_service.list_types(conn)


@router.post("", response_model=RoomTypeOut, dependencies=[AdminGuard], summary="新增房型")
def create_room_type(
    body: RoomTypeCreate, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    return room_service.create_type(conn, body)


@router.put(
    "/{type_id}", response_model=RoomTypeOut, dependencies=[AdminGuard], summary="修改房型"
)
def update_room_type(
    body: RoomTypeUpdate,
    type_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return room_service.update_type(conn, type_id, body)
