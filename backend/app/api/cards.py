"""房卡（退卡入口）。

发卡挂在 `/stays/{id}/cards`（动作属于某张入住单），退卡按卡记录 id 走
`/cards/{id}/revoke` —— 前台退卡时手里只有卡，不关心它挂在哪张单上。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Path

from app.api.deps import get_db
from app.models.stay import CardOut, CardRevokeIn
from app.services import card_service

router = APIRouter(prefix="/cards", tags=["房卡"])


@router.post("/{card_id}/revoke", response_model=list[CardOut], summary="收回房卡（退卡）")
def revoke_card(
    body: CardRevokeIn,
    card_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    return card_service.revoke(conn, card_id, body)
