from __future__ import annotations

import re
import sqlite3

from app.core.errors import AppError
from app.db import write_tx
from app.models.setting import SettingUpdate
from app.repo import settings_repo

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _positive_int(value: str, *, field: str) -> str:
    try:
        n = int(value.strip())
    except ValueError:
        raise AppError("INVALID_PARAM", f"{field}必须是整数") from None
    if n <= 0:
        raise AppError("INVALID_PARAM", f"{field}必须大于 0")
    return str(n)


def _non_negative_int(value: str, *, field: str) -> str:
    try:
        n = int(value.strip())
    except ValueError:
        raise AppError("INVALID_PARAM", f"{field}必须是整数") from None
    if n < 0:
        raise AppError("INVALID_PARAM", f"{field}不能为负数")
    return str(n)


def _hotel_name(value: str) -> str:
    v = value.strip()
    if not (1 <= len(v) <= 32):
        raise AppError("INVALID_PARAM", "酒店名称长度应在 1~32 字之间")
    return v


def _time_of_day(value: str) -> str:
    v = value.strip()
    if not TIME_PATTERN.match(v):
        raise AppError("INVALID_PARAM", "退房时限格式应为 HH:MM，如 12:00")
    return v


# 白名单：不在册的 key 一律拒绝。
# 参数表能被任意写，就等于给了一个"改任何业务规则"的后门；
# 这里把每个 key 的校验函数钉死，写错了在入口就报错，不会带着脏值跑业务。
REGISTRY: dict[str, tuple[str, object]] = {
    "HOTEL_NAME": ("酒店名称", _hotel_name),
    "DEFAULT_DEPOSIT_CENTS": ("默认押金", lambda v: _non_negative_int(v, field="默认押金")),
    "MAX_ROOM_RATE_CENTS": ("房价上限", lambda v: _positive_int(v, field="房价上限")),
    "CHECKOUT_TIME": ("退房时限", _time_of_day),
    "MAX_CHARGE_CENTS": ("杂费上限", lambda v: _positive_int(v, field="杂费上限")),
}


def list_settings(conn: sqlite3.Connection) -> list[dict]:
    return [
        {
            "key": row["key"],
            "value": row["value"],
            "description": row["description"],
            "updated_at": row["updated_at"],
        }
        for row in settings_repo.list_all(conn)
    ]


def update_setting(conn: sqlite3.Connection, body: SettingUpdate) -> dict:
    entry = REGISTRY.get(body.key)
    if entry is None:
        raise AppError(
            "INVALID_PARAM",
            f"参数 {body.key} 不在可修改清单里（可改：{'、'.join(REGISTRY)}）",
        )
    validator = entry[1]
    normalized = validator(body.value)  # type: ignore[operator]

    with write_tx(conn):
        settings_repo.set_value(conn, body.key, normalized)

    for row in settings_repo.list_all(conn):
        if row["key"] == body.key:
            return {
                "key": row["key"],
                "value": row["value"],
                "description": row["description"],
                "updated_at": row["updated_at"],
            }
    raise AppError("INTERNAL_ERROR")
