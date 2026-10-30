"""入住 → 加费 → 续住 → 换房 → 退房 的完整链路。

这条链路是本系统的"主流程"，它一通，其余都是分支。
断言的重点不是"接口返回 200"，而是**账和房态在每一步之后都说得通**。
"""
from __future__ import annotations

from datetime import timedelta

from app.core.dates import date_str, today as today_fn
from tests.base import ADMIN_HEADERS, ROOM_83_04, ROOM_83_05, ROOM_83_06, ApiTestBase


class CheckinFlowTest(ApiTestBase):
    def test_full_lifecycle(self):
        # ---- 1. 新客入住 8304，1 晚，默认房价 289，默认押金 300 ----
        resp = self.checkin(room_no=ROOM_83_04, guest=self.new_guest("11"))
        self.assertEqual(resp.status_code, 200, resp.text)
        stay = resp.json()
        stay_id = stay["id"]

        self.assertEqual(stay["status"], "IN_HOUSE")
        self.assertEqual(stay["room_no"], ROOM_83_04)
        self.assertEqual(stay["room_rate_cents"], 28_900)
        self.assertEqual(stay["deposit_cents"], 30_000)
        self.assertEqual(stay["nights"], 1)
        self.assertTrue(stay["stay_no"].startswith("RS"))
        self.assertEqual(stay["bill"]["total_cents"], 28_900)
        self.assertEqual(stay["bill"]["balance_cents"], -1_100)  # 押金比房费多 11 元
        self.assertEqual(stay["bill"]["settlement"], "REFUND")

        # 房态跟着变，且房卡上能直接看到客人
        board = self.board()
        room = self.room_of(board, ROOM_83_04)
        self.assertEqual(room["status"], "OCCUPIED")
        self.assertEqual(room["current_stay"]["guest_name"], "测试客11")

        # 客人档案被建档，房费快照落在单上
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM guests WHERE name = '测试客11'"), 1
        )
        self.assertEqual(
            self.scalar("SELECT room_rate_cents FROM stays WHERE id = ?", (stay_id,)), 28_900
        )

        # ---- 2. 加一笔餐饮 88 × 2 ----
        resp = self.client.post(
            f"/api/stays/{stay_id}/charges",
            json={"category": "FOOD", "name": "客房送餐", "amount": "88", "quantity": 2},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        bill = resp.json()["bill"]
        self.assertEqual(bill["charges_total_cents"], 17_600)
        self.assertEqual(bill["total_cents"], 46_500)
        self.assertEqual(bill["balance_cents"], 16_500)  # 应收 - 押金
        self.assertEqual(bill["settlement"], "DUE")

        # ---- 3. 续住到 3 晚 ----
        resp = self.client.post(
            f"/api/stays/{stay_id}/extend",
            json={"expected_checkout_date": date_str(today_fn() + timedelta(days=3))},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        extended = resp.json()
        self.assertEqual(extended["nights"], 3)
        self.assertEqual(extended["bill"]["room_fee_cents"], 28_900 * 3)
        self.assertEqual(extended["bill"]["total_cents"], 28_900 * 3 + 17_600)
        # 续住必须留痕，否则客人说"我明明续过"时无从对证
        types = [e["type"] for e in extended["events"]]
        self.assertEqual(types, ["CHECKIN", "ADD_CHARGE", "EXTEND"])

        # ---- 4. 换房 8304 → 8305（同房型，房价不该悄悄变） ----
        resp = self.client.post(
            f"/api/stays/{stay_id}/change-room",
            json={"room_id": self.room_id(ROOM_83_05)},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        moved = resp.json()
        self.assertEqual(moved["room_no"], ROOM_83_05)
        self.assertEqual(moved["room_rate_cents"], 28_900)
        self.assertEqual(moved["bill"]["total_cents"], 28_900 * 3 + 17_600)
        self.assertEqual(self.room_of(self.board(), ROOM_83_04)["status"], "CLEANING")

        # ---- 5. 退房结账（不传 nights → 按实际，今天入住今天退是 1 晚） ----
        resp = self.client.post(f"/api/stays/{stay_id}/checkout", json={})
        self.assertEqual(resp.status_code, 200, resp.text)
        out = resp.json()
        self.assertEqual(out["status"], "CHECKED_OUT")
        self.assertEqual(out["nights"], 1)
        self.assertEqual(out["bill"]["room_fee_cents"], 28_900)
        self.assertEqual(out["bill"]["total_cents"], 28_900 + 17_600)
        self.assertEqual(out["bill"]["balance_cents"], 46_500 - 30_000)

        # 账单里必须有一条 ROOM 明细，且金额等于 房价 × 间夜
        room_lines = [c for c in out["charges"] if c["category"] == "ROOM"]
        self.assertEqual(len(room_lines), 1)
        self.assertEqual(room_lines[0]["amount_cents"], 28_900)

        # 房态进入待清扫，不是直接回空闲（这是酒店的真实流程）
        self.assertEqual(self.room_of(self.board(), ROOM_83_05)["status"], "CLEANING")

        # 当日营收把这一单算进去了
        dash = self.client.get("/api/stats/dashboard").json()
        self.assertGreaterEqual(dash["today_revenue_cents"], out["bill"]["total_cents"])
        self.assertEqual(dash["today_checkouts"], 1)  # 演示库那单是两天前退的，今天只有本单

        # ---- 6. 已退房的单不能再操作 ----
        resp = self.client.post(f"/api/stays/{stay_id}/checkout", json={})
        self.assert_error(resp, "STAY_NOT_IN_HOUSE")

    def test_cancel_returns_room_to_vacant(self):
        resp = self.checkin(room_no=ROOM_83_06, guest=self.new_guest("12"))
        self.assertEqual(resp.status_code, 200, resp.text)
        stay_id = resp.json()["id"]

        resp = self.client.post(f"/api/stays/{stay_id}/cancel", params={"operator": "前台A"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["status"], "CANCELLED")
        # 撤销后房间直接回空闲（没住过人，不需要打扫）
        self.assertEqual(self.room_of(self.board(), ROOM_83_06)["status"], "VACANT")

    def test_cancel_blocked_when_charges_exist(self):
        resp = self.checkin(room_no=ROOM_83_06, guest=self.new_guest("13"))
        stay_id = resp.json()["id"]
        self.client.post(
            f"/api/stays/{stay_id}/charges",
            json={"category": "MINIBAR", "name": "可乐", "amount": "10"},
        )
        resp = self.client.post(f"/api/stays/{stay_id}/cancel", json={})
        self.assert_error(resp, "STAY_HAS_CHARGES")

    def test_returning_guest_reuses_profile(self):
        """老客再住一次：同一证件不该建出第二份档案。"""
        guest = self.new_guest("14")
        first = self.checkin(room_no="8304", guest=guest)
        self.assertEqual(first.status_code, 200, first.text)
        second = self.checkin(room_no="8306", guest=guest)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM guests WHERE id_no = ?", (guest["id_no"],)), 1
        )
        self.assertEqual(first.json()["guest_id"], second.json()["guest_id"])

    def test_blacklisted_guest_blocked(self):
        resp = self.client.put(
            "/api/guests/4",
            json={"blacklisted": True},
            headers=ADMIN_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        resp = self.checkin(room_no="8304", guest_id=4)
        self.assert_error(resp, "GUEST_BLACKLISTED")
