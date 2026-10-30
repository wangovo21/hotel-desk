"""测试脚手架。

三条保证（照原项目的约定，因为它确实把问题挡在了正确的地方）：
  · 模板库由**正式建库流程**生成（apply_schema + seed_reference_data + seed_demo），
    不是手搓的最小表 —— 约束没生效、索引拼错这类问题只有真库才暴露得出来；
  · 每个用例复制一份独立库文件，用例之间互不污染；
  · 走真实 HTTP（TestClient 起完整 ASGI 栈），异常信封、响应模型、鉴权依赖都在范围内。
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import config
from app.core.dates import date_str, today as today_fn
from app.db import connect
from app.db.init_db import SCHEMA_VERSION, apply_schema, seed_demo, seed_reference_data
from app.main import create_app

ADMIN_TOKEN = "hotel-test-token-0123456789"
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN}

# 演示数据（init_db.SEED_DEMO_*）的固定事实
ROOM_83_01 = "8301"   # 在住：张伟
ROOM_83_02 = "8302"   # 在住：李娜（已加一笔 88 元餐饮）
ROOM_83_03 = "8303"   # 已退房 → 待清扫
ROOM_83_04 = "8304"   # 空闲
ROOM_83_05 = "8305"   # 空闲
ROOM_83_06 = "8306"   # 空闲
ROOM_10_04 = "10304"  # 维修中
ROOM_10_01 = "10301"  # 家庭房（容量 3），用于容量校验
GUEST_ZHANGWEI, GUEST_LINA, GUEST_CHENMING, GUEST_WANGFANG = 1, 2, 3, 4


def build_template(path: Path) -> None:
    conn = connect(path)
    try:
        apply_schema(conn)
        seed_reference_data(conn)
        seed_demo(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    finally:
        conn.close()


class ApiTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="hotel-test-"))
        cls.template = cls.tmp / "template.db"
        build_template(cls.template)

        conn = connect(cls.template)
        try:
            rooms = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
            types = conn.execute("SELECT COUNT(*) FROM room_types").fetchone()[0]
            guests = conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0]
            stays = conn.execute("SELECT COUNT(*) FROM stays").fetchone()[0]
        finally:
            conn.close()
        assert (types, rooms, guests, stays) == (4, 20, 4, 3), (
            f"模板库不对：types={types} rooms={rooms} guests={guests} stays={stays}"
        )

        cls.app = create_app()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self) -> None:
        self.db = self.tmp / f"t-{uuid.uuid4().hex[:12]}.db"
        shutil.copyfile(self.template, self.db)

        # 用 mock.patch.object 改运行时值：deps.get_db 读的是 config.DB_PATH，
        # `from app.config import DB_PATH` 会在 import 时就把路径钉死。
        self._patch_db = mock.patch.object(config, "DB_PATH", self.db)
        self._patch_db.start()
        self.addCleanup(self._patch_db.stop)

        self._patch_token = mock.patch.object(config, "ADMIN_TOKEN", ADMIN_TOKEN)
        self._patch_token.start()
        self.addCleanup(self._patch_token.stop)

        self.client = TestClient(self.app)

    # -- 读库小工具 --------------------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = connect(self.db)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def scalar(self, sql: str, params: tuple = ()):
        conn = connect(self.db)
        try:
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    def exec_sql(self, sql: str, params: tuple = ()) -> None:
        """直接改库，用来造"只有直接改库才做得出来"的状态（比如逾期未退）。

        ★ 别拿它造正常业务数据（手工写一张入住单）：那会绕开 stay_service，
          `uq_stays_room_in_house` 和事件留痕都跟着失真，后面的断言会以
          "余额/房态对不上"的形式失败，看不出根因。
        """
        conn = connect(self.db)
        try:
            conn.execute(sql, params)
        finally:
            conn.close()

    # -- 业务小工具 --------------------------------------------------------
    def room_id(self, room_no: str) -> int:
        return int(self.scalar("SELECT id FROM rooms WHERE room_no = ?", (room_no,)))

    def stay_id_in_room(self, room_no: str) -> int:
        return int(
            self.scalar(
                """SELECT s.id FROM stays s JOIN rooms r ON r.id = s.room_id
                    WHERE r.room_no = ? AND s.status = 'IN_HOUSE'""",
                (room_no,),
            )
        )

    def checkin(
        self,
        *,
        room_no: str = ROOM_83_04,
        guest_id: int | None = None,
        guest: dict | None = None,
        nights: int = 1,
        **extra,
    ):
        payload = {
            "room_id": self.room_id(room_no),
            "expected_checkout_date": date_str(today_fn() + timedelta(days=nights)),
            **extra,
        }
        if guest_id is not None:
            payload["guest_id"] = guest_id
        if guest is not None:
            payload["guest"] = guest
        return self.client.post("/api/stays", json=payload)

    def new_guest(self, suffix: str = "01") -> dict:
        return {
            "name": f"测试客{suffix}",
            "id_type": "ID_CARD",
            "id_no": f"{int(suffix):06d}",  # 模拟系统：证件号是 6 位虚拟号
            "phone": f"1390000{int(suffix):04d}",
            "gender": "MALE",
        }

    def board(self) -> dict:
        resp = self.client.get("/api/rooms/board")
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def room_of(self, board: dict, room_no: str) -> dict:
        for floor in board["floors"]:
            for room in floor["rooms"]:
                if room["room_no"] == room_no:
                    return room
        raise AssertionError(f"看板里没有房间 {room_no}")

    def assert_error(self, resp, code: str) -> None:
        self.assertGreaterEqual(resp.status_code, 400, resp.text)
        body = resp.json()
        self.assertIn("error", body, f"不是统一错误信封：{body}")
        self.assertEqual(body["error"]["code"], code, body)
        self.assertTrue(body["error"]["message"], "错误信封缺少面向用户的 message")
