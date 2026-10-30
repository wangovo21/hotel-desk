"""枚举 → 中文标签。**唯一一份**。

为什么不让前端自己翻译：房态"待清扫"这种词，前端要显示在房卡上、
后端要写进导出报表、日志里还要能看懂。三处各写一份映射，改文案必然漏。
所以后端把 `status` 和 `status_label` 一起返回，前端只管上色。
"""
from __future__ import annotations

ROOM_STATUS_LABELS = {
    "VACANT": "空闲",
    "OCCUPIED": "在住",
    "CLEANING": "待清扫",
    "MAINTENANCE": "维修中",
}

STAY_STATUS_LABELS = {
    "IN_HOUSE": "在住",
    "CHECKED_OUT": "已退房",
    "CANCELLED": "已撤销",
}

CHARGE_CATEGORY_LABELS = {
    "ROOM": "房费",
    "FOOD": "餐饮",
    "LAUNDRY": "洗衣",
    "MINIBAR": "迷你吧",
    "EXTRA_BED": "加床",
    "DAMAGE": "赔偿",
    "OTHER": "其他",
}

STAY_EVENT_LABELS = {
    "CHECKIN": "入住登记",
    "EXTEND": "续住",
    "CHANGE_ROOM": "换房",
    "ADD_CHARGE": "加收费用",
    "CHECKOUT": "退房结账",
    "CANCEL": "撤销入住",
    "ISSUE_CARD": "发放房卡",
    "REVOKE_CARD": "收回房卡",
}

CARD_STATUS_LABELS = {
    "ACTIVE": "在用",
    "REVOKED": "已收回",
}

ID_TYPE_LABELS = {
    "ID_CARD": "身份证",
    "PASSPORT": "护照",
    "HK_MACAO": "港澳通行证",
    "TAIWAN": "台湾通行证",
    "OTHER": "其他证件",
}

GENDER_LABELS = {"MALE": "男", "FEMALE": "女", "UNKNOWN": "未填"}


def label(mapping: dict[str, str], key: str) -> str:
    """未知值不抛异常 —— 前端显示一个原样代码，比整个列表 500 好排查。"""
    return mapping.get(key, key)
