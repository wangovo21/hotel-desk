"""拒绝路径。

一个前台系统值不值得信，不看它顺利的时候多顺，看它**该拦的时候拦不拦得住**。
这个文件把每条业务底线都打进一次"坏输入"，确保拦截发生在 service 层、
报的是能读懂的话、并且数据库状态没有被改脏。
"""
from __future__ import annotations

from datetime import timedelta

from app.core.dates import date_str, today as today_fn
from tests.base import (
    ADMIN_HEADERS,
    ROOM_10_01,
    ROOM_10_04,
    ROOM_83_01,
    ROOM_83_03,
    ROOM_83_04,
    ApiTestBase,
)


class CheckinRulesTest(ApiTestBase):
    def test_occupied_room_rejected(self):
        resp = self.checkin(room_no=ROOM_83_01, guest=self.new_guest("21"))
        self.assert_error(resp, "ROOM_OCCUPIED")

    def test_maintenance_room_rejected(self):
        resp = self.checkin(room_no=ROOM_10_04, guest=self.new_guest("22"))
        self.assert_error(resp, "ROOM_UNDER_MAINTENANCE")

    def test_cleaning_room_rejected(self):
        resp = self.checkin(room_no=ROOM_83_03, guest=self.new_guest("23"))
        self.assert_error(resp, "ROOM_NOT_VACANT")

    def test_same_day_checkout_rejected(self):
        resp = self.client.post(
            "/api/stays",
            json={
                "guest": self.new_guest("24"),
                "room_id": self.room_id(ROOM_83_04),
                "expected_checkout_date": date_str(today_fn()),
            },
        )
        self.assert_error(resp, "INVALID_DATE_RANGE")

    def test_over_capacity_rejected(self):
        resp = self.checkin(
            room_no=ROOM_10_01, guest=self.new_guest("25"), adults=3, children=1
        )
        self.assert_error(resp, "INVALID_PARAM")

    def test_guest_payload_xor(self):
        base = {
            "room_id": self.room_id(ROOM_83_04),
            "expected_checkout_date": date_str(today_fn() + timedelta(days=1)),
        }
        # 两个都给
        resp = self.client.post(
            "/api/stays", json={**base, "guest_id": 1, "guest": self.new_guest("26")}
        )
        self.assert_error(resp, "INVALID_PARAM")
        # 一个都不给
        resp = self.client.post("/api/stays", json=base)
        self.assert_error(resp, "INVALID_PARAM")

    def test_extra_field_rejected(self):
        # extra="forbid"：前端多传字段直接挡在入口，避免"传了但没生效"的静默错误
        resp = self.client.post(
            "/api/stays",
            json={
                "guest": self.new_guest("27"),
                "room_id": self.room_id(ROOM_83_04),
                "expected_checkout_date": date_str(today_fn() + timedelta(days=1)),
                "room_rate_cents": 1,
            },
        )
        self.assert_error(resp, "INVALID_PARAM")

    def test_bad_date_format(self):
        resp = self.client.post(
            "/api/stays",
            json={
                "guest": self.new_guest("28"),
                "room_id": self.room_id(ROOM_83_04),
                "expected_checkout_date": "2026/10/30",
            },
        )
        self.assert_error(resp, "INVALID_DATE")

    def test_unknown_room(self):
        resp = self.client.post(
            "/api/stays",
            json={
                "guest": self.new_guest("29"),
                "room_id": 9999,
                "expected_checkout_date": date_str(today_fn() + timedelta(days=1)),
            },
        )
        self.assert_error(resp, "ROOM_NOT_FOUND")

    def test_failed_checkin_leaves_no_trace(self):
        """被拒绝的入住不能留下任何东西：不能有单据、不能有客人、房态不能变。"""
        before_guests = self.scalar("SELECT COUNT(*) FROM guests")
        before_stays = self.scalar("SELECT COUNT(*) FROM stays")
        self.checkin(room_no=ROOM_83_01, guest=self.new_guest("30"))

        self.assertEqual(self.scalar("SELECT COUNT(*) FROM guests"), before_guests)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM stays"), before_stays)
        self.assertEqual(self.room_of(self.board(), ROOM_83_01)["status"], "OCCUPIED")


class StayOperationRulesTest(ApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        resp = self.checkin(room_no=ROOM_83_04, guest=self.new_guest("31"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.stay = resp.json()
        self.stay_id = self.stay["id"]

    def test_extend_must_be_later(self):
        resp = self.client.post(
            f"/api/stays/{self.stay_id}/extend",
            json={"expected_checkout_date": self.stay["expected_checkout_date"]},
        )
        self.assert_error(resp, "STAY_ALREADY_EXTENDED_TO")

    def test_change_to_same_room_rejected(self):
        resp = self.client.post(
            f"/api/stays/{self.stay_id}/change-room",
            json={"room_id": self.room_id(ROOM_83_04)},
        )
        self.assert_error(resp, "STAY_ROOM_UNCHANGED")

    def test_change_to_occupied_room_rejected(self):
        resp = self.client.post(
            f"/api/stays/{self.stay_id}/change-room",
            json={"room_id": self.room_id(ROOM_83_01)},
        )
        self.assert_error(resp, "ROOM_OCCUPIED")

    def test_charge_zero_rejected(self):
        resp = self.client.post(
            f"/api/stays/{self.stay_id}/charges",
            json={"category": "OTHER", "name": "测试", "amount": "0"},
        )
        self.assert_error(resp, "INVALID_AMOUNT")

    def test_charge_over_limit_rejected(self):
        # 单笔杂费上限默认 1000 元（settings.MAX_CHARGE_CENTS）
        resp = self.client.post(
            f"/api/stays/{self.stay_id}/charges",
            json={"category": "OTHER", "name": "测试", "amount": "1000.01"},
        )
        self.assert_error(resp, "INVALID_AMOUNT")

    def test_unknown_stay(self):
        resp = self.client.get("/api/stays/9999")
        self.assert_error(resp, "STAY_NOT_FOUND")


class RoomAdminRulesTest(ApiTestBase):
    def test_admin_token_required(self):
        resp = self.client.post(
            "/api/rooms",
            json={"room_no": "8401", "room_type_id": 1, "floor": 8},
        )
        self.assert_error(resp, "UNAUTHORIZED")

        resp = self.client.post(
            "/api/rooms",
            json={"room_no": "8401", "room_type_id": 1, "floor": 8},
            headers={"X-Admin-Token": "wrong-token"},
        )
        self.assert_error(resp, "UNAUTHORIZED")

    def test_create_room_ok_with_token(self):
        resp = self.client.post(
            "/api/rooms",
            json={"room_no": "8401", "room_type_id": 1, "floor": 8, "note": "新增测试房"},
            headers=ADMIN_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "VACANT")
        self.assertEqual(body["room_type_code"], "STD")

    def test_duplicate_room_no(self):
        resp = self.client.post(
            "/api/rooms",
            json={"room_no": "8304", "room_type_id": 1, "floor": 8},
            headers=ADMIN_HEADERS,
        )
        self.assert_error(resp, "ROOM_NO_EXISTS")

    def test_duplicate_type_code(self):
        resp = self.client.post(
            "/api/room-types",
            json={"code": "STD", "name": "重复代码房", "price": "199"},
            headers=ADMIN_HEADERS,
        )
        self.assert_error(resp, "ROOM_TYPE_CODE_EXISTS")

    def test_room_status_transitions(self):
        rid = self.room_id(ROOM_83_04)
        # 空闲 → 维修：允许
        resp = self.client.put(
            f"/api/rooms/{rid}/status", json={"status": "MAINTENANCE"}, headers=ADMIN_HEADERS
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        # 维修 → 待清扫：不允许（得先修好回空闲）
        resp = self.client.put(
            f"/api/rooms/{rid}/status", json={"status": "CLEANING"}, headers=ADMIN_HEADERS
        )
        self.assert_error(resp, "ROOM_STATUS_INVALID")
        # 维修 → 空闲：允许
        resp = self.client.put(
            f"/api/rooms/{rid}/status", json={"status": "VACANT"}, headers=ADMIN_HEADERS
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_occupied_room_status_locked(self):
        rid = self.room_id(ROOM_83_01)
        resp = self.client.put(
            f"/api/rooms/{rid}/status", json={"status": "VACANT"}, headers=ADMIN_HEADERS
        )
        self.assert_error(resp, "ROOM_HAS_ACTIVE_STAY")

    def test_cannot_set_occupied_by_hand(self):
        """房态 OCCUPIED 只能由入住产生 —— 手工设等于凭空造出一个客人。"""
        rid = self.room_id(ROOM_83_04)
        resp = self.client.put(
            f"/api/rooms/{rid}/status", json={"status": "OCCUPIED"}, headers=ADMIN_HEADERS
        )
        self.assert_error(resp, "INVALID_PARAM")

    def test_delete_room_with_history_blocked(self):
        for room_no, code in ((ROOM_83_01, "ROOM_HAS_ACTIVE_STAY"), (ROOM_83_03, "ROOM_HAS_HISTORY")):
            resp = self.client.delete(f"/api/rooms/{self.room_id(room_no)}", headers=ADMIN_HEADERS)
            self.assert_error(resp, code)

    def test_delete_fresh_room_ok(self):
        created = self.client.post(
            "/api/rooms",
            json={"room_no": "8402", "room_type_id": 1, "floor": 8},
            headers=ADMIN_HEADERS,
        ).json()
        resp = self.client.delete(f"/api/rooms/{created['id']}", headers=ADMIN_HEADERS)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assert_error(self.client.get(f"/api/rooms/{created['id']}"), "ROOM_NOT_FOUND")
