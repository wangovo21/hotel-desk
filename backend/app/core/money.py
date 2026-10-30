from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.errors import AppError

CENTS_PER_YUAN = 100

# 单笔金额的兜底上限（分）＝ 100 万。真实上限由 settings.MAX_ROOM_RATE_CENTS 决定，
# 这里只是防止一个 print 错误把房价打成 99999999 之后一路进数据库。
DEFAULT_MAX_AMOUNT_CENTS = 100_000_000


def _to_decimal(value: Any, field: str = "金额") -> Decimal:
    if isinstance(value, bool):  # bool 是 int 的子类，不挡住会变成 1/0 元
        raise AppError("INVALID_AMOUNT", f"{field}不合法")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise AppError("INVALID_AMOUNT", f"{field}不合法")
        try:
            d = Decimal(text)
        except InvalidOperation:
            raise AppError("INVALID_AMOUNT", f"{field}必须是数字") from None
    elif isinstance(value, float):
        # ★ 只接受字符串/整数形式的精确值；float 走 str() 保精度，不直接进 Decimal(float)
        d = Decimal(str(value))
    else:
        raise AppError("INVALID_AMOUNT", f"{field}必须是数字")

    if not d.is_finite():
        raise AppError("INVALID_AMOUNT", f"{field}必须是有限数字")
    return d


def to_cents(value: Any, *, field: str = "金额") -> int:
    """元 → 分。多于两位小数直接拒绝，不做四舍五入（钱不能悄悄少一分）。"""
    d = _to_decimal(value, field)
    scaled = d.scaleb(2)
    if scaled != scaled.to_integral_value():
        raise AppError("INVALID_AMOUNT", f"{field}最多只能有 2 位小数")
    return int(scaled)


def format_cents(cents: int) -> str:
    """分 → '1234.50' 这样的字符串，供前端直接显示（前端不再做除法）。"""
    sign = "-" if cents < 0 else ""
    yuan, fen = divmod(abs(int(cents)), CENTS_PER_YUAN)
    return f"{sign}{yuan}.{fen:02d}"


def parse_amount(
    value: Any,
    *,
    max_cents: int | None = None,
    allow_zero: bool = False,
    field: str = "金额",
) -> int:
    """金额入参的唯一解析入口：元 → 分 + 上下限校验 + 全系统同一套报错。"""
    cents = to_cents(value, field=field)
    limit = DEFAULT_MAX_AMOUNT_CENTS if max_cents is None else max_cents

    if cents == 0 and not allow_zero:
        raise AppError("INVALID_AMOUNT", f"{field}必须大于 0")
    if cents < 0:
        raise AppError("INVALID_AMOUNT", f"{field}不能为负数")
    if cents > limit:
        raise AppError("INVALID_AMOUNT", f"{field}不能超过 {format_cents(limit)} 元")
    return cents
