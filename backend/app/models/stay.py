from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.guest import GuestCreate

CHARGE_CATEGORY = Literal["ROOM", "FOOD", "LAUNDRY", "MINIBAR", "EXTRA_BED", "DAMAGE", "OTHER"]
STAY_STATUS = Literal["IN_HOUSE", "CHECKED_OUT", "CANCELLED"]


# ---------------------------------------------------------------------------
# 入住登记（本系统的主入口）
# ---------------------------------------------------------------------------
class CheckinCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_id: int | None = Field(None, ge=1, description="老客：直接传客人档案 id")
    guest: GuestCreate | None = Field(None, description="新客：现场录入的客人信息")

    room_id: int = Field(..., ge=1)
    checkin_at: str | None = Field(
        None, description="入住时刻，'YYYY-MM-DD HH:MM'；不传 = 当前时间（补录时用）"
    )
    expected_checkout_date: str = Field(..., description="预计离店日 YYYY-MM-DD，必须晚于入住日")
    room_rate: str | None = Field(
        None, description="房价（元/晚）；不传 = 取房型挂牌价。团队价/协议价在这里覆盖"
    )
    deposit: str | None = Field(None, description="押金（元）；不传 = 取参数 DEFAULT_DEPOSIT_CENTS")
    adults: int = Field(1, ge=1, le=10)
    children: int = Field(0, ge=0, le=10)
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def _guest_required(self) -> "CheckinCreate":
        has_id = self.guest_id is not None
        has_new = self.guest is not None
        if has_id == has_new:
            raise ValueError("客人信息二选一：要么传 guest_id（老客），要么传 guest（新客）")
        return self


class ExtendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_checkout_date: str = Field(..., description="新的预计离店日，必须晚于当前值")
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)


class ChangeRoomIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: int = Field(..., ge=1, description="目标房间 id，必须为空房")
    room_rate: str | None = Field(
        None, description="换房后的房价（元/晚）；不传 = 沿用原房价（不传给房型价，避免悄悄涨价）"
    )
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)


class ChargeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: CHARGE_CATEGORY = "OTHER"
    name: str = Field(..., min_length=1, max_length=32, description="费用名称，如「客房送餐」")
    amount: str = Field(..., description="单价（元），最多两位小数")
    quantity: int = Field(1, ge=1, le=99)
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nights: int | None = Field(
        None,
        ge=1,
        le=365,
        description="结算间夜数。不传 = 按实际退房日与入住日的自然日差（最小 1）。"
        "提前退房想按原预订夜数收费时显式传。",
    )
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)


# ---------------------------------------------------------------------------
# 房卡（USB 键盘仿真读写器：刷卡 = 往输入框敲卡号并以回车结尾）
# ---------------------------------------------------------------------------
class CardIssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_no: str = Field(..., min_length=1, max_length=32, description="卡号，刷卡器整串读出")
    operator: str | None = Field(None, max_length=32)
    remark: str | None = Field(None, max_length=200)


class CardRevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: str | None = Field(None, max_length=32)
    reason: str | None = Field(None, max_length=200, description="如「客人退卡」「卡损坏补卡」")


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
class ChargeOut(BaseModel):
    id: int
    category: CHARGE_CATEGORY
    category_label: str
    name: str
    amount_cents: int
    amount_display: str
    quantity: int
    subtotal_cents: int
    subtotal_display: str
    operator: str | None
    remark: str | None
    created_at: str


class StayEventOut(BaseModel):
    id: int
    type: str
    type_label: str
    from_value: str | None
    to_value: str | None
    amount_cents: int
    amount_display: str
    operator: str | None
    remark: str | None
    created_at: str


class BillOut(BaseModel):
    """结账口径，只在这里算一次。

    应收 = 房费(nights × room_rate) + 杂费合计
    差额 = 应收 - 押金   → >0 还需向客人收款；<0 需退给客人
    """

    nights: int
    room_fee_cents: int
    room_fee_display: str
    charges_total_cents: int
    charges_total_display: str
    total_cents: int
    total_display: str
    deposit_cents: int
    deposit_display: str
    balance_cents: int
    balance_display: str
    settlement: Literal["DUE", "REFUND", "EVEN"]
    settlement_label: str


class StayBrief(BaseModel):
    id: int
    stay_no: str
    guest_id: int
    guest_name: str
    guest_phone: str | None
    id_no_masked: str
    room_id: int
    room_no: str
    room_type_name: str
    room_rate_cents: int
    room_rate_display: str
    checkin_at: str
    expected_checkout_date: str
    checkout_at: str | None
    nights: int
    deposit_cents: int
    deposit_display: str
    adults: int
    children: int
    status: STAY_STATUS
    status_label: str
    overdue: bool = Field(..., description="在住且今天已超过预计离店日 —— 前台需要主动催一下")


class CardOut(BaseModel):
    id: int
    stay_id: int
    card_no: str
    room_no: str
    status: Literal["ACTIVE", "REVOKED"]
    status_label: str
    issued_at: str
    issued_by: str | None
    revoked_at: str | None
    revoked_by: str | None
    revoke_reason: str | None


class StayDetail(StayBrief):
    remark: str | None
    operator: str | None
    created_at: str
    updated_at: str
    charges: list[ChargeOut] = Field(default_factory=list)
    events: list[StayEventOut] = Field(default_factory=list)
    cards: list[CardOut] = Field(default_factory=list)
    bill: BillOut


class StayPage(BaseModel):
    items: list[StayBrief]
    total: int
    page: int
    page_size: int
