"""房卡：发卡 / 退卡 / 冲突 / 自动回收。

重点不是"接口通"，而是三条容易翻车的边界：
  · 一张卡不能同时绑两张在住单（连自己在住单上重复发也不行）
  · 退卡后同一张卡要能再发给别人（部分唯一索引只管 ACTIVE）
  · 退房/撤销必须把卡一起收走，漏收卡就是给陌生人留了一把钥匙
"""
from __future__ import annotations

from tests.base import GUEST_CHENMING, GUEST_LINA, ROOM_83_04, ROOM_83_05, ApiTestBase


class CardFlowTest(ApiTestBase):
    def issue(self, stay_id: int, card_no: str, **extra):
        return self.client.post(
            f"/api/stays/{stay_id}/cards", json={"card_no": card_no, **extra}
        )

    def cards_of(self, stay_id: int) -> list[dict]:
        resp = self.client.get(f"/api/stays/{stay_id}/cards")
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def test_issue_to_in_house_stay(self):
        resp = self.checkin(guest_id=GUEST_CHENMING)
        stay_id = resp.json()["id"]

        resp = self.issue(stay_id, "NF-1001", operator="前台小李")
        self.assertEqual(resp.status_code, 200, resp.text)
        cards = resp.json()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["card_no"], "NF-1001")
        self.assertEqual(cards[0]["status"], "ACTIVE")
        self.assertEqual(cards[0]["status_label"], "在用")
        self.assertEqual(cards[0]["room_no"], "8304")

        # 详情带 cards，且留痕有发卡事件
        detail = self.client.get(f"/api/stays/{stay_id}").json()
        self.assertEqual(len(detail["cards"]), 1)
        issue_events = [e for e in detail["events"] if e["type"] == "ISSUE_CARD"]
        self.assertEqual(len(issue_events), 1)
        self.assertEqual(issue_events[0]["to_value"], "NF-1001")

    def test_card_no_normalized(self):
        """读写器常吐 'ab:cd 1234' 这类带分隔符的串，归一化后入库。"""
        resp = self.checkin(guest_id=GUEST_CHENMING)
        stay_id = resp.json()["id"]

        resp = self.issue(stay_id, "ab:cd 1234")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()[0]["card_no"], "ABCD1234")

    def test_duplicate_active_card_rejected(self):
        resp_a = self.checkin(room_no=ROOM_83_04, guest_id=GUEST_CHENMING)
        resp_b = self.checkin(room_no=ROOM_83_05, guest_id=GUEST_LINA)
        stay_a, stay_b = resp_a.json()["id"], resp_b.json()["id"]

        self.assertEqual(self.issue(stay_a, "NF-2001").status_code, 200)

        # 发给别的在住单 → 拒
        self.assert_error(self.issue(stay_b, "NF-2001"), "CARD_IN_USE")
        # 同一张单重复发 → 也拒（提示语不同，但都是 CARD_IN_USE）
        self.assert_error(self.issue(stay_a, "NF-2001"), "CARD_IN_USE")

    def test_invalid_card_no_rejected(self):
        resp = self.checkin(guest_id=GUEST_CHENMING)
        stay_id = resp.json()["id"]

        self.assert_error(self.issue(stay_id, "!!!"), "CARD_NO_EMPTY")  # 清洗后没剩东西
        self.assert_error(self.issue(stay_id, "abc"), "CARD_NO_INVALID")  # 太短
        self.assert_error(self.issue(stay_id, "   "), "CARD_NO_EMPTY")

    def test_issue_to_closed_stay_rejected(self):
        """已退房的历史单不能发卡 —— 那是在给空气发钥匙。"""
        stay_id = int(
            self.scalar("SELECT id FROM stays WHERE status = 'CHECKED_OUT' LIMIT 1")
        )
        self.assert_error(self.issue(stay_id, "NF-3001"), "STAY_NOT_IN_HOUSE")

    def test_revoke_then_reissue(self):
        resp_a = self.checkin(room_no=ROOM_83_04, guest_id=GUEST_CHENMING)
        resp_b = self.checkin(room_no=ROOM_83_05, guest_id=GUEST_LINA)
        stay_a, stay_b = resp_a.json()["id"], resp_b.json()["id"]

        cards = self.issue(stay_a, "NF-4001").json()
        card_id = cards[0]["id"]

        resp = self.client.post(
            f"/api/cards/{card_id}/revoke", json={"operator": "前台", "reason": "客人退卡"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        revoked = [c for c in resp.json() if c["id"] == card_id][0]
        self.assertEqual(revoked["status"], "REVOKED")
        self.assertEqual(revoked["status_label"], "已收回")
        self.assertEqual(revoked["revoke_reason"], "客人退卡")

        # 重复退卡 → 拒
        self.assert_error(
            self.client.post(f"/api/cards/{card_id}/revoke", json={}),
            "CARD_ALREADY_REVOKED",
        )

        # 收回后同一张卡可以发给别的在住单
        resp = self.issue(stay_b, "NF-4001")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()[0]["room_no"], ROOM_83_05)

        # 退卡也有留痕
        detail = self.client.get(f"/api/stays/{stay_a}").json()
        revoke_events = [e for e in detail["events"] if e["type"] == "REVOKE_CARD"]
        self.assertEqual(len(revoke_events), 1)
        self.assertEqual(revoke_events[0]["from_value"], "NF-4001")

    def test_revoke_unknown_card(self):
        self.assert_error(
            self.client.post("/api/cards/99999/revoke", json={}), "CARD_NOT_FOUND"
        )

    def test_checkout_auto_revokes_cards(self):
        resp = self.checkin(guest_id=GUEST_CHENMING)
        stay_id = resp.json()["id"]
        self.issue(stay_id, "NF-5001")
        self.issue(stay_id, "NF-5002")  # 同住两个人各拿一张

        resp = self.client.post(f"/api/stays/{stay_id}/checkout", json={})
        self.assertEqual(resp.status_code, 200, resp.text)
        cards = resp.json()["cards"]
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(c["status"] == "REVOKED" for c in cards))
        self.assertTrue(all("退房" in (c["revoke_reason"] or "") for c in cards))

        revoke_events = [e for e in resp.json()["events"] if e["type"] == "REVOKE_CARD"]
        self.assertEqual(len(revoke_events), 2)

    def test_cancel_auto_revokes_cards(self):
        resp = self.checkin(guest_id=GUEST_CHENMING)
        stay_id = resp.json()["id"]
        self.issue(stay_id, "NF-6001")

        resp = self.client.post(
            f"/api/stays/{stay_id}/cancel?operator=前台", json={}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        cards = resp.json()["cards"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["status"], "REVOKED")


if __name__ == "__main__":
    import unittest

    unittest.main()
