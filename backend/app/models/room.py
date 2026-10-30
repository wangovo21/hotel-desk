from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOM_STATUS = Literal["VACANT", "OCCUPIED", "CLEANING", "MAINTENANCE"]
ROOM_TYPE_STATUS = Literal["ON", "OFF"]

CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,8}$")
ROOM_NO_PATTERN = re.compile(r"^[0-9A-Z-]{1,12}$")


def _clean_text(value: str, field: str, max_len: int) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field}不能为空")  # dev-error: 校验器只能抛 ValueError，抛 AppError 会变 500
    if len(value) > max_len:
        raise ValueError(f"{field}不能超过 {max_len} 个字符")
    return value


# ---------------------------------------------------------------------------
# 房型
# ---------------------------------------------------------------------------
class RoomTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="房型代码，大写字母/数字，如 STD、SUITE")
    name: str = Field(..., min_length=1, max_length=24, description="房型名称")
    price: str = Field(..., description="挂牌价（元，字符串，最多两位小数）")
    capacity: int = Field(2, ge=1, le=10, description="可住人数")
    bed_type: str | None = Field(None, max_length=32)
    status: ROOM_TYPE_STATUS = "ON"
    sort_order: int = Field(0, ge=0, le=999)

    @field_validator("code")
    @classmethod
    def _v_code(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not CODE_PATTERN.match(v):
            raise ValueError("房型代码只能是 2~8 位大写字母或数字")
        return v

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _clean_text(v, "房型名称", 24)


class RoomTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=24)
    price: str | None = None
    capacity: int | None = Field(None, ge=1, le=10)
    bed_type: str | None = Field(None, max_length=32)
    status: ROOM_TYPE_STATUS | None = None
    sort_order: int | None = Field(None, ge=0, le=999)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str | None) -> str | None:
        return None if v is None else _clean_text(v, "房型名称", 24)

    @model_validator(mode="after")
    def _check_provided(self) -> "RoomTypeUpdate":
        provided = set(self.model_fields_set)
        if not provided:
            raise ValueError("没有要修改的字段")  # dev-error: 校验器只认 ValueError
        nulls = sorted(k for k in provided if getattr(self, k) is None and k != "bed_type")
        if nulls:
            raise ValueError(f"字段不能为 null：{'、'.join(nulls)}")  # dev-error: 同上
        return self


class RoomTypeOut(BaseModel):
    id: int
    code: str
    name: str
    base_price_cents: int
    base_price_display: str
    capacity: int
    bed_type: str | None
    status: ROOM_TYPE_STATUS
    status_label: str
    sort_order: int
    room_count: int = Field(..., description="该房型下的房间数（删除前的判断依据）")


# ---------------------------------------------------------------------------
# 房间
# ---------------------------------------------------------------------------
class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_no: str = Field(..., description="房号，如 8301")
    room_type_id: int = Field(..., ge=1)
    floor: int = Field(..., ge=-5, le=200)
    note: str | None = Field(None, max_length=64)

    @field_validator("room_no")
    @classmethod
    def _v_room_no(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not ROOM_NO_PATTERN.match(v):
            raise ValueError("房号只能是 1~12 位数字/字母/短横线")
        return v


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_type_id: int | None = Field(None, ge=1)
    floor: int | None = Field(None, ge=-5, le=200)
    note: str | None = Field(None, max_length=64)

    @model_validator(mode="after")
    def _check_provided(self) -> "RoomUpdate":
        provided = set(self.model_fields_set)
        if not provided:
            raise ValueError("没有要修改的字段")  # dev-error: 校验器只认 ValueError
        nulls = sorted(k for k in provided if getattr(self, k) is None and k != "note")
        if nulls:
            raise ValueError(f"字段不能为 null：{'、'.join(nulls)}")  # dev-error: 同上
        return self


class RoomStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["VACANT", "MAINTENANCE", "CLEANING"] = Field(
        ...,
        description="目标房态。OCCUPIED 只能由入住动作产生，不接受手工设置；"
        "入住中若要停用房间，请先换房或退房",
    )
    note: str | None = Field(None, max_length=64)


class RoomOut(BaseModel):
    id: int
    room_no: str
    floor: int
    status: ROOM_STATUS
    status_label: str
    room_type_id: int
    room_type_code: str
    room_type_name: str
    base_price_cents: int
    base_price_display: str
    capacity: int
    note: str | None
    current_stay: "StayBrief | None" = Field(
        None, description="在住单摘要：房卡上直接显示客人姓名与离店日，前台不用再点进去"
    )


class RoomFloorGroup(BaseModel):
    floor: int
    rooms: list[RoomOut]


class RoomBoard(BaseModel):
    """房态看板：一次请求拿到"按楼层分组的全部房间 + 汇总数字"。

    刻意不在前端聚合：前台大厅的屏幕刷新频率高，让它发 1 个请求而不是
    1 + N 个，掉线的概率也跟着降。
    """

    hotel_name: str
    total_rooms: int
    counts: dict[str, int]
    floors: list[RoomFloorGroup]
    generated_at: str


# 循环引用：RoomOut 引用 StayBrief，StayBrief 又引用房间号，这里做前向解析
from app.models.stay import StayBrief  # noqa: E402  (放到文件末尾避免循环 import)

RoomOut.model_rebuild()
