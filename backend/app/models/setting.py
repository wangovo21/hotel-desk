from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SettingOut(BaseModel):
    key: str
    value: str
    description: str | None
    updated_at: str


class SettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., max_length=64)

    @model_validator(mode="after")
    def _v_value(self) -> "SettingUpdate":
        if not self.value.strip():
            raise ValueError("参数值不能为空")  # dev-error: 校验器只认 ValueError
        return self
