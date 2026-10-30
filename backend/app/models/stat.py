from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.stay import StayBrief


class RoomTypeUsage(BaseModel):
    room_type_id: int
    name: str
    total: int
    occupied: int
    occupancy_percent: float


class DayPoint(BaseModel):
    date: str
    checkins: int
    checkouts: int
    revenue_cents: int
    revenue_display: str


class Dashboard(BaseModel):
    hotel_name: str
    today: str
    generated_at: str

    total_rooms: int
    in_house_count: int = Field(..., description="在住房间数")
    vacant_count: int
    cleaning_count: int
    maintenance_count: int
    occupancy_percent: float = Field(..., description="在住 / 可售房（扣除维修房），保留 1 位小数")
    guests_in_house: int = Field(..., description="在住人数（成人 + 儿童）")

    today_checkins: int
    today_checkouts: int
    today_revenue_cents: int
    today_revenue_display: str
    in_house_deposit_cents: int
    in_house_deposit_display: str

    due_out_today: list[StayBrief] = Field(default_factory=list, description="预计今日离店但还没退")
    overdue_stays: list[StayBrief] = Field(default_factory=list, description="已超过预计离店日")
    recent_checkouts: list[StayBrief] = Field(default_factory=list, description="最近 5 笔退房")

    room_type_usage: list[RoomTypeUsage] = Field(default_factory=list)
    trend: list[DayPoint] = Field(default_factory=list, description="近 7 天入住/退房/营收")
