"""日期与间夜计算。

全系统的日期口径只有两条，写在这里，别在各 service 里各算一遍：

  1. **日期一律存字符串** `YYYY-MM-DD`（入住日/离店日），
     时间一律存 `YYYY-MM-DD HH:MM:SS`（入住时刻/退房时刻）。
     SQLite 里字符串比较即时间比较，不需要时区库。

  2. **间夜数 = 离店日 - 入住日**，最小 1。
     当天入住当天退房也算 1 个间夜（钟点房不在本系统范围内）。
     这条规则贯穿：预订间夜、续住、退房结算都用同一个函数，
     否则"预计住 2 晚、实际住了 1 晚"这类账永远对不上。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.errors import AppError

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def today() -> date:
    return date.today()


def date_str(d: date) -> str:
    return d.strftime(DATE_FMT)


def datetime_str(d: date, hhmm: str = "14:00") -> str:
    """把日期补成一个时刻字符串。演示数据与"补录入住"用。"""
    return f"{d.strftime(DATE_FMT)} {hhmm}"


def parse_date(value: str, *, field: str = "日期") -> date:
    """严格解析 YYYY-MM-DD。

    不接受 "2026/10/23"、"2026-10-23T00:00" 这些变体：前端用 <input type="date">
    输出的就是标准格式，放宽解析只会让"到底是哪一天"在跨端时悄悄错位。
    """
    text = (value or "").strip()
    try:
        return datetime.strptime(text, DATE_FMT).date()
    except ValueError:
        raise AppError("INVALID_DATE", f"{field}格式不合法，应为 YYYY-MM-DD") from None


def parse_date_opt(value: str | None, *, field: str = "日期") -> date | None:
    if value is None or not str(value).strip():
        return None
    return parse_date(str(value), field=field)


def nights_between(checkin: date, checkout: date) -> int:
    """间夜数。离店日必须晚于入住日，否则报错（不做"最小 1"的兜底）。"""
    days = (checkout - checkin).days
    if days < 1:
        raise AppError(
            "INVALID_DATE_RANGE",
            "离店日期必须晚于入住日期（当天入住当天退房按 1 个间夜计，离店日请填次日）",
        )
    return days


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)


def actual_nights(checkin_at: str, checkout_at: str) -> int:
    """按**实际退房时刻**算间夜：入住日到退房日的自然日差，最小 1。

    只看日期不看钟点：14:00 入住、次日 12:00 退房是 1 晚；
    凌晨 02:00 入住、当天 12:00 退房也算 1 晚（前台不会为这种单子扯皮）。
    """
    try:
        start = datetime.strptime(checkin_at, DATETIME_FMT).date()
        end = datetime.strptime(checkout_at, DATETIME_FMT).date()
    except ValueError:
        raise AppError("INVALID_DATE", "入住/退房时间格式不合法") from None
    return max(1, (end - start).days)
