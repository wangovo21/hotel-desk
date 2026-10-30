from __future__ import annotations

from tests.base import ADMIN_HEADERS, ROOM_83_01, ROOM_83_02, ApiTestBase


class HealthAndBoardTest(ApiTestBase):
    def test_health(self):
        body = self.client.get("/api/health").json()
        self.assertTrue(body["db"]["ok"], body)
        self.assertEqual(body["db"]["tables"], 8)
        self.assertEqual(body["db"]["schema_version"], 2)
        self.assertTrue(body["admin_api_enabled"])
        self.assertEqual(body["hotel_name"], "云栖酒店")

    def test_board_groups_by_floor(self):
        board = self.board()
        self.assertEqual(board["total_rooms"], 20)
        self.assertEqual([f["floor"] for f in board["floors"]], [8, 9, 10])
        self.assertEqual(board["counts"]["OCCUPIED"], 2)
        self.assertEqual(board["counts"]["CLEANING"], 1)
        self.assertEqual(board["counts"]["MAINTENANCE"], 1)
        self.assertEqual(board["counts"]["VACANT"], 16)

        # 房卡上要能直接读到客人：省掉"点进去看是谁"的一次交互
        stay = self.room_of(board, ROOM_83_01)["current_stay"]
        self.assertEqual(stay["guest_name"], "张伟")
        self.assertEqual(stay["room_rate_display"], "289.00")

    def test_room_list_filters(self):
        resp = self.client.get("/api/rooms", params={"status": "OCCUPIED"})
        self.assertEqual(resp.status_code, 200)
        rooms = resp.json()
        self.assertEqual(len(rooms), 2)
        self.assertTrue(all(r["status"] == "OCCUPIED" for r in rooms))

        resp = self.client.get("/api/rooms", params={"floor": 10})
        self.assertEqual(len(resp.json()), 4)

        resp = self.client.get("/api/rooms", params={"keyword": "8308"})
        self.assertEqual([r["room_no"] for r in resp.json()], ["8308"])


class DashboardTest(ApiTestBase):
    def test_dashboard_numbers(self):
        dash = self.client.get("/api/stats/dashboard").json()
        self.assertEqual(dash["total_rooms"], 20)
        self.assertEqual(dash["in_house_count"], 2)
        # 出租率分母是"可售房"：20 - 1 间维修 = 19
        self.assertEqual(dash["occupancy_percent"], 10.5)
        self.assertEqual(dash["guests_in_house"], 2)
        self.assertEqual(len(dash["room_type_usage"]), 4)
        self.assertEqual(len(dash["trend"]), 7)
        # 演示数据里两间在住各押 300 / 500
        self.assertEqual(dash["in_house_deposit_cents"], 30_000 + 50_000)

    def test_overdue_detection(self):
        """把一间在住单的预计离店日改成昨天，看板要把它列进逾期。"""
        stay_id = self.stay_id_in_room(ROOM_83_02)
        self.exec_sql(
            "UPDATE stays SET expected_checkout_date = date('now','localtime','-1 day') WHERE id = ?",
            (stay_id,),
        )
        dash = self.client.get("/api/stats/dashboard").json()
        overdue_ids = [s["id"] for s in dash["overdue_stays"]]
        self.assertIn(stay_id, overdue_ids)
        self.assertTrue(all(s["overdue"] for s in dash["overdue_stays"]))


class ListAndSearchTest(ApiTestBase):
    def test_stay_list(self):
        page = self.client.get("/api/stays").json()
        self.assertEqual(page["total"], 3)

        page = self.client.get("/api/stays", params={"status": "IN_HOUSE"}).json()
        self.assertEqual(page["total"], 2)

        page = self.client.get("/api/stays", params={"keyword": "张伟"}).json()
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["guest_name"], "张伟")

    def test_in_house_endpoint(self):
        rows = self.client.get("/api/stays/in-house").json()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "IN_HOUSE" for r in rows))

    def test_page_size_limit(self):
        resp = self.client.get("/api/stays", params={"page_size": 500})
        self.assert_error(resp, "INVALID_PARAM")

    def test_guest_list_masks_id(self):
        page = self.client.get("/api/guests").json()
        self.assertEqual(page["total"], 4)
        zhang = next(g for g in page["items"] if g["name"] == "张伟")
        self.assertEqual(zhang["id_no_masked"], "10**01")  # 6 位虚拟号只遮中段
        self.assertEqual(zhang["id_type_label"], "身份证")
        self.assertEqual(zhang["stay_count"], 1)

    def test_guest_detail_has_history(self):
        detail = self.client.get("/api/guests/2").json()
        self.assertEqual(detail["name"], "李娜")
        self.assertEqual(len(detail["stays"]), 1)
        self.assertEqual(detail["stays"][0]["room_no"], ROOM_83_02)


class SettingsTest(ApiTestBase):
    def test_list_settings(self):
        rows = self.client.get("/api/settings").json()
        keys = {r["key"] for r in rows}
        self.assertIn("HOTEL_NAME", keys)
        self.assertIn("DEFAULT_DEPOSIT_CENTS", keys)

    def test_update_requires_admin(self):
        resp = self.client.put("/api/settings", json={"key": "HOTEL_NAME", "value": "新名字"})
        self.assert_error(resp, "UNAUTHORIZED")

    def test_update_validates_value(self):
        resp = self.client.put(
            "/api/settings",
            json={"key": "DEFAULT_DEPOSIT_CENTS", "value": "-1"},
            headers=ADMIN_HEADERS,
        )
        self.assert_error(resp, "INVALID_PARAM")

        resp = self.client.put(
            "/api/settings",
            json={"key": "DROP_TABLE", "value": "1"},
            headers=ADMIN_HEADERS,
        )
        self.assert_error(resp, "INVALID_PARAM")

    def test_update_ok(self):
        resp = self.client.put(
            "/api/settings",
            json={"key": "HOTEL_NAME", "value": "云栖酒店 · 西湖店"},
            headers=ADMIN_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["value"], "云栖酒店 · 西湖店")
        # 看板抬头跟着变（同一个参数只有一处真相）
        self.assertEqual(
            self.client.get("/api/stats/dashboard").json()["hotel_name"], "云栖酒店 · 西湖店"
        )

    def test_new_deposit_applies_to_next_checkin(self):
        """改默认押金后，新入住的单子立刻用新值（不用重启服务）。"""
        self.client.put(
            "/api/settings",
            json={"key": "DEFAULT_DEPOSIT_CENTS", "value": "50000"},
            headers=ADMIN_HEADERS,
        )
        resp = self.checkin(room_no="8304", guest=self.new_guest("41"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["deposit_cents"], 50_000)


class MockIdCardTest(ApiTestBase):
    """模拟系统的证件号：身份证一律 6 位虚拟号，不追求贴近真实身份证。"""

    def make_guest(self, id_no: str, name: str = "模拟客") -> dict:
        return {
            "name": name,
            "id_type": "ID_CARD",
            "id_no": id_no,
            "phone": "13800001234",
            "gender": "UNKNOWN",
        }

    def test_six_digit_mock_accepted(self):
        resp = self.client.post(
            "/api/guests", json=self.make_guest("123456"), headers=ADMIN_HEADERS
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["id_no"], "123456")
        self.assertEqual(body["id_type"], "ID_CARD")

    def test_six_digit_mock_can_check_in(self):
        resp = self.checkin(room_no="8304", guest=self.make_guest("654321", "模拟客乙"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["guest_name"], "模拟客乙")

    def test_real_id_card_no_longer_accepted(self):
        """这是模拟系统：18 位真身份证号一律拒绝，只认 6 位虚拟号。"""
        for bad in ("110101199001011234", "11010119900101123X"):
            with self.subTest(id_no=bad):
                resp = self.client.post(
                    "/api/guests", json=self.make_guest(bad), headers=ADMIN_HEADERS
                )
                self.assert_error(resp, "INVALID_PARAM")

    def test_other_lengths_rejected(self):
        for bad in ("12345", "1234567", "12345X", "abcdef"):
            with self.subTest(id_no=bad):
                resp = self.client.post(
                    "/api/guests", json=self.make_guest(bad), headers=ADMIN_HEADERS
                )
                self.assert_error(resp, "INVALID_PARAM")

    def test_passport_not_restricted_to_six(self):
        """护照等类型不受 6 位限制，按实际号码录。"""
        resp = self.client.post(
            "/api/guests",
            json={
                "name": "外籍客",
                "id_type": "PASSPORT",
                "id_no": "E99887766",
                "gender": "UNKNOWN",
            },
            headers=ADMIN_HEADERS,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
