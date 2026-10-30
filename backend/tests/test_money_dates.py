from __future__ import annotations

import unittest
from datetime import date

from app.core.dates import actual_nights, nights_between, parse_date
from app.core.errors import AppError
from app.core.money import format_cents, parse_amount, to_cents


class MoneyTest(unittest.TestCase):
    def test_to_cents_exact(self):
        self.assertEqual(to_cents("289"), 28900)
        self.assertEqual(to_cents("289.5"), 28950)
        self.assertEqual(to_cents("289.05"), 28905)
        self.assertEqual(to_cents(100), 10000)

    def test_to_cents_rejects_three_decimals(self):
        # 钱不能悄悄四舍五入：0.005 元如果被"修正"成 0.01，一万单就差 50 块
        with self.assertRaises(AppError) as ctx:
            to_cents("1.005")
        self.assertEqual(ctx.exception.code, "INVALID_AMOUNT")

    def test_to_cents_rejects_garbage(self):
        for bad in ("abc", "", None, True, "1e3x"):
            with self.assertRaises(AppError):
                to_cents(bad)

    def test_format_cents(self):
        self.assertEqual(format_cents(0), "0.00")
        self.assertEqual(format_cents(28900), "289.00")
        self.assertEqual(format_cents(5), "0.05")
        self.assertEqual(format_cents(-1100), "-11.00")

    def test_parse_amount_bounds(self):
        self.assertEqual(parse_amount("289", max_cents=500_000), 28900)
        with self.assertRaises(AppError):
            parse_amount("0")
        with self.assertRaises(AppError):
            parse_amount("-1")
        with self.assertRaises(AppError):
            parse_amount("6000", max_cents=500_000)

    def test_parse_amount_allow_zero(self):
        self.assertEqual(parse_amount("0", allow_zero=True), 0)


class DatesTest(unittest.TestCase):
    def test_nights_between(self):
        self.assertEqual(nights_between(date(2026, 10, 23), date(2026, 10, 24)), 1)
        self.assertEqual(nights_between(date(2026, 10, 23), date(2026, 10, 26)), 3)

    def test_nights_between_same_day_rejected(self):
        # 当天来当天走按 1 个间夜算，但表单必须填次日 —— 这条规则由报错教会前台
        with self.assertRaises(AppError) as ctx:
            nights_between(date(2026, 10, 23), date(2026, 10, 23))
        self.assertEqual(ctx.exception.code, "INVALID_DATE_RANGE")

    def test_parse_date_strict(self):
        self.assertEqual(parse_date("2026-10-23"), date(2026, 10, 23))
        for bad in ("2026/10/23", "2026-10-23T00:00", "20261023", ""):
            with self.assertRaises(AppError) as ctx:
                parse_date(bad)
            self.assertEqual(ctx.exception.code, "INVALID_DATE")

    def test_actual_nights_min_one(self):
        self.assertEqual(actual_nights("2026-10-23 14:10:00", "2026-10-24 12:05:00"), 1)
        # 凌晨入住当天退房也算 1 晚，前台不为这种单子扯皮
        self.assertEqual(actual_nights("2026-10-23 02:00:00", "2026-10-23 12:00:00"), 1)
        self.assertEqual(actual_nights("2026-10-20 14:00:00", "2026-10-23 12:00:00"), 3)


if __name__ == "__main__":
    unittest.main()
