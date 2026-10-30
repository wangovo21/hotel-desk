from __future__ import annotations

import sqlite3
from datetime import timedelta

from app.core.dates import date_str, now_str, today as today_fn
from app.core.money import format_cents
from app.repo import room_repo, settings_repo, stay_repo
from app.services import serializers

TREND_DAYS = 7


def dashboard(conn: sqlite3.Connection) -> dict:
    day = date_str(today_fn())
    counts = room_repo.status_counts(conn)
    total = sum(counts.values())

    # ★ 出租率的分母是"可售房"（总房 − 维修房），不是总房。
    #   把维修房算进分母，会让一间房常年在修的分店永远达不到 100%，
    #   店长看到的数字失去意义。
    sellable = total - counts.get("MAINTENANCE", 0)
    occupied = counts.get("OCCUPIED", 0)
    occupancy = round(occupied * 100 / sellable, 1) if sellable > 0 else 0.0

    today_checkins = stay_repo.count_checkins_on(conn, day)
    today_checkouts = stay_repo.count_checkouts_on(conn, day)
    revenue = stay_repo.revenue_on(conn, day)

    due_out = stay_repo.due_out_on(conn, day)
    overdue = stay_repo.overdue_on(conn, day)
    recent = stay_repo.recent_checkouts(conn, 5)

    usage = []
    for row in stay_repo.usage_by_type(conn):
        t_total = int(row["total"])
        t_occupied = int(row["occupied"])
        usage.append(
            {
                "room_type_id": row["id"],
                "name": row["name"],
                "total": t_total,
                "occupied": t_occupied,
                "occupancy_percent": round(t_occupied * 100 / t_total, 1) if t_total else 0.0,
            }
        )

    start = today_fn() - timedelta(days=TREND_DAYS - 1)
    checkins = stay_repo.checkins_grouped(conn, date_str(start), day)
    checkouts = stay_repo.checkouts_grouped(conn, date_str(start), day)
    revenues = stay_repo.revenue_grouped(conn, date_str(start), day)
    trend = []
    for i in range(TREND_DAYS):
        d = date_str(start + timedelta(days=i))
        trend.append(
            {
                "date": d,
                "checkins": checkins.get(d, 0),
                "checkouts": checkouts.get(d, 0),
                "revenue_cents": revenues.get(d, 0),
                "revenue_display": format_cents(revenues.get(d, 0)),
            }
        )

    return {
        "hotel_name": settings_repo.hotel_name(conn),
        "today": day,
        "generated_at": now_str(),
        "total_rooms": total,
        "in_house_count": occupied,
        "vacant_count": counts.get("VACANT", 0),
        "cleaning_count": counts.get("CLEANING", 0),
        "maintenance_count": counts.get("MAINTENANCE", 0),
        "occupancy_percent": occupancy,
        "guests_in_house": stay_repo.guests_in_house(conn),
        "today_checkins": today_checkins,
        "today_checkouts": today_checkouts,
        "today_revenue_cents": revenue,
        "today_revenue_display": format_cents(revenue),
        "in_house_deposit_cents": stay_repo.deposits_in_house(conn),
        "in_house_deposit_display": format_cents(stay_repo.deposits_in_house(conn)),
        "due_out_today": [serializers.stay_brief(r, today=day) for r in due_out],
        "overdue_stays": [serializers.stay_brief(r, today=day) for r in overdue],
        "recent_checkouts": [serializers.stay_brief(r, today=day) for r in recent],
        "room_type_usage": usage,
        "trend": trend,
    }
