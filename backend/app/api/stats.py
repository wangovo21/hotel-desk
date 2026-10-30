from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.models.stat import Dashboard
from app.services import stat_service

router = APIRouter(prefix="/stats", tags=["看板"])


@router.get("/dashboard", response_model=Dashboard, summary="经营看板")
def dashboard(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return stat_service.dashboard(conn)
