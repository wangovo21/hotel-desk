"""房卡业务：发卡 / 退卡 / 整单回收。

刷卡硬件走 **USB 键盘仿真**（与 nfc-market 的 KL9007U 同一方式）：
读写器没有驱动，刷卡等于往当前聚焦的输入框整串敲卡号并以回车结尾。
所以后端只关心"收到一个卡号字符串"，硬件细节完全留在前端输入框里。

规则：
  · 只有在住单能发卡（退了房的卡是废卡，收回来才发得出去）
  · 一张实体卡同时只能绑一张在住单（数据库部分唯一索引兜底并发）
  · 退房 / 撤销入住时自动收回全部在用卡 —— 漏收卡是真实酒店的高频事故
"""
from __future__ import annotations

import logging
import re
import sqlite3

from app.core.errors import AppError
from app.db import write_tx
from app.models.stay import CardIssueIn, CardRevokeIn
from app.repo import card_repo, stay_repo
from app.services import serializers

logger = logging.getLogger("hotel_desk")

# 读写器常见输出：纯数字 / 十六进制（可能带 : 或空格分隔）/ 厂商前缀-编号。
# 保留字母数字与短横线，其余当分隔符剔除；统一大写，避免同一张卡大小写对不上。
_CARD_NO_RE = re.compile(r"^[A-Z0-9-]{4,32}$")


def normalize_card_no(raw: str) -> str:
    """'ab:cd 12 34' → 'ABCD1234'。空串/畸形号在这里就拦下，别等唯一索引报 500。"""
    text = re.sub(r"[^A-Za-z0-9-]", "", str(raw)).upper()
    if not text:
        raise AppError("CARD_NO_EMPTY")
    if not _CARD_NO_RE.fullmatch(text):
        raise AppError(
            "CARD_NO_INVALID",
            f"卡号「{str(raw).strip()[:40]}」不像读写器输出的卡号（字母/数字/短横线，4-32 位）",
        )
    return text


def issue(conn: sqlite3.Connection, stay_id: int, body: CardIssueIn) -> list[dict]:
    """给在住单发一张卡。卡号已绑在别的在住单上时拒绝（CARD_IN_USE）。"""
    stay = stay_repo.get_stay(conn, stay_id)
    if stay is None:
        raise AppError("STAY_NOT_FOUND")
    if stay["status"] != "IN_HOUSE":
        raise AppError("STAY_NOT_IN_HOUSE")

    card_no = normalize_card_no(body.card_no)

    with write_tx(conn):
        clash = card_repo.find_active_by_no(conn, card_no)
        if clash is not None:
            if int(clash["stay_id"]) == stay_id:
                raise AppError(
                    "CARD_IN_USE",
                    f"卡 {card_no} 已经发给了这张入住单，不用重复发",
                )
            raise AppError("CARD_IN_USE")

        card_id = card_repo.insert_card(
            conn,
            stay_id=stay_id,
            card_no=card_no,
            room_no=stay["room_no"],
            issued_by=body.operator,
        )
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="ISSUE_CARD",
            to_value=card_no,
            operator=body.operator,
            remark=body.remark,
        )

    logger.info("发卡 %s → 单 %s（%s）", card_no, stay["stay_no"], stay["room_no"])
    return detail(conn, stay_id)


def revoke(conn: sqlite3.Connection, card_id: int, body: CardRevokeIn) -> list[dict]:
    """退一张卡。已收回的卡报 CARD_ALREADY_REVOKED，幂等交给前端提示。"""
    card = card_repo.get_card(conn, card_id)
    if card is None:
        raise AppError("CARD_NOT_FOUND")
    if card["status"] != "ACTIVE":
        raise AppError(
            "CARD_ALREADY_REVOKED",
            f"卡 {card['card_no']} 已于 {card['revoked_at']} 收回",
        )

    with write_tx(conn):
        card_repo.revoke_card(conn, card_id, revoked_by=body.operator, reason=body.reason)
        stay_repo.insert_event(
            conn,
            stay_id=int(card["stay_id"]),
            type_="REVOKE_CARD",
            from_value=card["card_no"],
            operator=body.operator,
            remark=body.reason,
        )

    logger.info("退卡 %s（单 %s）", card["card_no"], card["stay_id"])
    return detail(conn, int(card["stay_id"]))


def revoke_all_for_stay(
    conn: sqlite3.Connection,
    stay_id: int,
    *,
    operator: str | None,
    reason: str,
) -> int:
    """整单回收。退房/撤销入住时调用；没有在用卡就什么都不发生。

    ★ **不开自己的事务**：调用方（checkout/cancel）已经在 write_tx 里了，
      BEGIN IMMEDIATE 嵌套会直接报错。这里的写跟随外层一起提交或回滚。
    """
    active = card_repo.active_cards_of_stay(conn, stay_id)
    if not active:
        return 0

    card_repo.revoke_all_for_stay(conn, stay_id, reason=reason)
    for card in active:
        stay_repo.insert_event(
            conn,
            stay_id=stay_id,
            type_="REVOKE_CARD",
            from_value=card["card_no"],
            operator=operator,
            remark=reason,
        )
    return len(active)


def detail(conn: sqlite3.Connection, stay_id: int) -> list[dict]:
    return [serializers.card_out(r) for r in card_repo.list_by_stay(conn, stay_id)]


def count_active(conn: sqlite3.Connection, stay_id: int) -> int:
    return card_repo.count_active_by_stay(conn, stay_id)
