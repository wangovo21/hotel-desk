"""路由注册表。`main.py` 只认这个列表，加模块不用改 main。"""
from __future__ import annotations

from app.api import cards, guests, health, room_types, rooms, settings, stats, stays

ROUTERS = [
    health.router,
    room_types.router,
    rooms.router,
    guests.router,
    stays.router,
    cards.router,
    stats.router,
    settings.router,
]
