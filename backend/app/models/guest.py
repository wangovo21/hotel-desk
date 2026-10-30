from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ID_TYPE = Literal["ID_CARD", "PASSPORT", "HK_MACAO", "TAIWAN", "OTHER"]
GENDER = Literal["MALE", "FEMALE", "UNKNOWN"]

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
# 本系统是演示/演练用的模拟系统，证件号一律 **6 位虚拟号**，不追求跟真实身份证一致。
# 真实酒店的 18 位 + 校验位在这里没有意义：只会拖慢录入、还会在演练时把人挡在外面。
# 证件类型保留（身份证/护照/港澳/台胞/其他），只有"身份证"这一类用统一的 6 位虚拟号。
ID_CARD_PATTERN = re.compile(r"^\d{6}$")


def _clean_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("客人姓名不能为空")  # dev-error: 校验器只认 ValueError
    if len(value) > 32:
        raise ValueError("客人姓名不能超过 32 个字符")  # dev-error: 同上
    return value


def _clean_phone(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not PHONE_PATTERN.match(value):
        raise ValueError("手机号格式不正确（应为 11 位数字，1 开头）")  # dev-error: 同上
    return value


def _clean_id_no(value: str, id_type: str) -> str:
    value = (value or "").strip().upper()
    if not value:
        raise ValueError("证件号不能为空")  # dev-error: 同上
    if len(value) > 32:
        raise ValueError("证件号不能超过 32 个字符")  # dev-error: 同上
    if id_type == "ID_CARD" and not ID_CARD_PATTERN.match(value):
        raise ValueError("证件号应为 6 位数字（模拟系统的虚拟号）")  # dev-error: 同上
    return value


class GuestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=32)
    id_type: ID_TYPE = "ID_CARD"
    id_no: str = Field(..., description="证件号；身份证为 6 位虚拟号，护照等按实际填写")
    phone: str | None = None
    gender: GENDER = "UNKNOWN"
    remark: str | None = Field(None, max_length=200)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str | None) -> str | None:
        return _clean_phone(v)

    @field_validator("id_no")
    @classmethod
    def _v_id_no(cls, v: str) -> str:
        # id_type 的校验顺序由 pydantic 保证（同层字段已解析），这里只做基础清洗，
        # 身份证长度在 model_validator 里带 id_type 一起判。
        value = (v or "").strip().upper()
        if not value:
            raise ValueError("证件号不能为空")  # dev-error: 同上
        return value

    @model_validator(mode="after")
    def _check_id_no(self) -> "GuestCreate":
        self.id_no = _clean_id_no(self.id_no, self.id_type)
        return self


class GuestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=32)
    phone: str | None = None
    gender: GENDER | None = None
    remark: str | None = Field(None, max_length=200)
    blacklisted: bool | None = Field(None, description="true = 列入黑名单，入住时拦截")

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str | None) -> str | None:
        return None if v is None else _clean_name(v)

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str | None) -> str | None:
        return _clean_phone(v)

    @model_validator(mode="after")
    def _check_provided(self) -> "GuestUpdate":
        provided = set(self.model_fields_set)
        if not provided:
            raise ValueError("没有要修改的字段")  # dev-error: 校验器只认 ValueError
        nulls = sorted(
            k for k in provided if getattr(self, k) is None and k not in ("phone", "remark")
        )
        if nulls:
            raise ValueError(f"字段不能为 null：{'、'.join(nulls)}")  # dev-error: 同上
        return self


class GuestBrief(BaseModel):
    id: int
    name: str
    id_type: ID_TYPE
    id_type_label: str
    id_no: str
    id_no_masked: str = Field(..., description="脱敏证件号，列表页展示用")
    phone: str | None
    gender: GENDER
    gender_label: str
    blacklisted: bool
    stay_count: int = 0
    last_checkin_at: str | None = None
    created_at: str


class GuestStayItem(BaseModel):
    stay_id: int
    stay_no: str
    room_no: str
    checkin_at: str
    checkout_at: str | None
    nights: int
    status: str
    status_label: str


class GuestDetail(GuestBrief):
    remark: str | None
    updated_at: str
    stays: list[GuestStayItem] = Field(default_factory=list, description="最近 20 条住史")


class GuestPage(BaseModel):
    items: list[GuestBrief]
    total: int
    page: int
    page_size: int


class GuestPick(BaseModel):
    """入住登记时的"客人二选一"输入。

    · 老客：只传 `guest_id`
    · 新客：只传 `guest` 对象
    两个都传或都不传都由 CheckinCreate 判错 —— 这是整个系统最容易被前端
    误用的入口，宁可在这里多写十行也不要在 service 里猜。
    """

    guest_id: int | None = Field(None, ge=1)
    guest: GuestCreate | None = None
