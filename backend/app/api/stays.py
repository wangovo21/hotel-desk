from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import Page, get_db, pagination
from app.models.stay import (
    CardIssueIn,
    CardOut,
    ChargeIn,
    CheckinCreate,
    CheckoutIn,
    ChangeRoomIn,
    ExtendIn,
    StayBrief,
    StayDetail,
    StayPage,
)
from app.services import card_service, stay_service

router = APIRouter(prefix="/stays", tags=["入住单"])

# ★ 这里的写接口**都不挂 AdminGuard**。
#   入住、续住、换房、加费、退房是收银员每分钟都在做的事，要求带口令等于
#   把口令贴在显示器上。真正的约束在业务规则里（房态、单据状态、金额上限），
#   不在这一层。后台改配置的接口（房型/房间/客人/参数）才需要口令。


@router.post("", response_model=StayDetail, summary="入住登记")
def checkin(body: CheckinCreate, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return stay_service.checkin(conn, body)


@router.get("/in-house", response_model=list[StayBrief], summary="在住客人列表")
def in_house(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    return stay_service.list_in_house(conn)


@router.get("", response_model=StayPage, summary="入住记录（可筛选）")
def list_stays(
    conn: sqlite3.Connection = Depends(get_db),
    page: Page = Depends(pagination),
    status: Literal["IN_HOUSE", "CHECKED_OUT", "CANCELLED"] | None = Query(None),
    keyword: str | None = Query(None, max_length=32, description="客人姓名/手机号/单号/房号"),
    date_from: str | None = Query(None, description="入住日期起 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="入住日期止 YYYY-MM-DD"),
    room_id: int | None = Query(None, ge=1),
) -> dict:
    return stay_service.list_stays(
        conn,
        status=status,
        keyword=(keyword or "").strip() or None,
        date_from=(date_from or "").strip() or None,
        date_to=(date_to or "").strip() or None,
        room_id=room_id,
        limit=page.limit,
        offset=page.offset,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{stay_id}", response_model=StayDetail, summary="入住单详情（账单 + 操作留痕）")
def get_stay(stay_id: int = Path(..., ge=1), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return stay_service.get_stay(conn, stay_id)


@router.post("/{stay_id}/extend", response_model=StayDetail, summary="续住")
def extend(
    body: ExtendIn,
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return stay_service.extend(conn, stay_id, body)


@router.post("/{stay_id}/change-room", response_model=StayDetail, summary="换房")
def change_room(
    body: ChangeRoomIn,
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return stay_service.change_room(conn, stay_id, body)


@router.post("/{stay_id}/charges", response_model=StayDetail, summary="加收费用")
def add_charge(
    body: ChargeIn,
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return stay_service.add_charge(conn, stay_id, body)


@router.post("/{stay_id}/checkout", response_model=StayDetail, summary="退房结账")
def checkout(
    body: CheckoutIn,
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return stay_service.checkout(conn, stay_id, body)


@router.post("/{stay_id}/cancel", response_model=StayDetail, summary="撤销入住（未产生杂费时）")
def cancel(
    stay_id: int = Path(..., ge=1),
    operator: str | None = Query(None, max_length=32),
    remark: str | None = Query(None, max_length=200),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return stay_service.cancel(conn, stay_id, operator=operator, remark=remark)


@router.get("/{stay_id}/cards", response_model=list[CardOut], summary="入住单的房卡记录")
def list_cards(
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    stay = stay_service.get_stay(conn, stay_id)  # 顺便校验单据存在
    assert stay is not None
    return card_service.detail(conn, stay_id)


@router.post("/{stay_id}/cards", response_model=list[CardOut], summary="发放房卡（刷卡器回车即发）")
def issue_card(
    body: CardIssueIn,
    stay_id: int = Path(..., ge=1),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    return card_service.issue(conn, stay_id, body)
