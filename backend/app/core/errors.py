from __future__ import annotations

from typing import Any

# ============================================================================
# 错误码总表。规矩（照抄原项目的约定，因为它确实省事）：
#   1) 每条 message 直接写成**面向客人/前台**的整句中文，前端原样显示，
#      前端不再维护第二份错误文案（两份文案必然走偏）。
#   2) 键名带业务前缀（ROOM_ / GUEST_ / STAY_ / BILL_），一眼能看出是谁的问题。
#   3) 新增错误码必须先登记在这里，否则 AppError 直接 KeyError —— 开发期就炸，
#      不要让一个没文案的错误冒到客人面前变成 500。
#   4) HTTP 状态码的语义：
#        400 输入不合法（改输入就能过）
#        404 目标不存在
#        409 状态冲突（房间被占、单据已结、房型在用……改输入也没用，得换动作）
#        401/500 部署或权限问题
# ============================================================================
ERRORS: dict[str, tuple[int, str]] = {
    # ---- 房间 ----
    "ROOM_NOT_FOUND":            (404, "房间不存在"),
    "ROOM_NO_EXISTS":            (409, "该房号已存在"),
    "ROOM_OCCUPIED":             (409, "该房间有客人在住，请先办理退房或换房"),
    "ROOM_NOT_VACANT":           (409, "该房间当前不是空房，无法办理入住"),
    "ROOM_UNDER_MAINTENANCE":    (409, "该房间正在维修，不能安排入住"),
    "ROOM_HAS_ACTIVE_STAY":      (409, "该房间还有未结束的入住单，不能修改或删除"),
    "ROOM_STATUS_INVALID":       (409, "房态流转不合法，请刷新后重试"),
    "ROOM_HAS_HISTORY":          (409, "该房间已有入住历史，不能删除，可改为维修或停用"),

    # ---- 房型 ----
    "ROOM_TYPE_NOT_FOUND":       (404, "房型不存在"),
    "ROOM_TYPE_IN_USE":          (409, "该房型下还挂着房间，不能删除"),
    "ROOM_TYPE_OFF":             (409, "该房型已停用，不能安排入住"),
    "ROOM_TYPE_CODE_EXISTS":     (409, "该房型代码已存在"),

    # ---- 客人 ----
    "GUEST_NOT_FOUND":           (404, "客人档案不存在"),
    "GUEST_ID_EXISTS":           (409, "该证件号已登记过，请直接选择已有客人"),
    "GUEST_BLACKLISTED":         (409, "该客人已被列入黑名单，请联系值班经理"),

    # ---- 入住单 ----
    "STAY_NOT_FOUND":            (404, "入住单不存在"),
    "STAY_NOT_IN_HOUSE":         (409, "该入住单已结束（已退房或已撤销），不能再操作"),
    "STAY_ALREADY_CHECKED_OUT":  (409, "该入住单已退房，不能重复退房"),
    "STAY_HAS_CHARGES":          (409, "该入住单已产生杂费，不能直接撤销，请走退房结账"),
    "STAY_ALREADY_EXTENDED_TO":  (400, "新的离店日期必须晚于当前预计离店日期"),
    "STAY_ROOM_UNCHANGED":       (400, "新房间与当前房间相同，无需换房"),
    "STAY_NO_CHARGE_TO_SETTLE":  (400, "该入住单没有任何费用可结算"),

    # ---- 房卡 ----
    "CARD_NOT_FOUND":            (404, "房卡记录不存在"),
    "CARD_NO_EMPTY":             (400, "卡号不能为空，请刷卡或输入卡号"),
    "CARD_NO_INVALID":           (400, "卡号不合法：只允许字母、数字、短横线，长度 4-32"),
    "CARD_IN_USE":               (409, "这张卡已绑定其他在住单，请先收回或换一张卡"),
    "CARD_ALREADY_REVOKED":      (409, "这张房卡已收回，不能重复退卡"),

    # ---- 日期与金额 ----
    "INVALID_DATE":              (400, "日期格式不合法，应为 YYYY-MM-DD"),
    "INVALID_DATE_RANGE":        (400, "离店日期必须晚于入住日期"),
    "INVALID_NIGHTS":            (400, "间夜数不合法"),
    "INVALID_AMOUNT":            (400, "金额不合法"),
    "INVALID_PARAM":             (400, "请求参数不合法"),

    # ---- 通用 ----
    "UNAUTHORIZED":              (401, "无权限"),
    "ADMIN_TOKEN_NOT_CONFIGURED": (500, "服务端未配置 admin token（环境变量 ADMIN_TOKEN），后台写接口已关闭"),
    "TABLE_NOT_FOUND":           (404, "该表不支持在线编辑"),

    "NOT_FOUND":                 (404, "接口不存在"),
    "METHOD_NOT_ALLOWED":        (405, "请求方法不允许"),
    "HTTP_ERROR":                (500, "请求处理失败"),
    "DB_ERROR":                  (500, "数据库操作失败，请重试"),
    "INTERNAL_ERROR":            (500, "服务器内部错误，请重试"),
}


class AppError(Exception):
    """业务异常。只在 service 层抛，api 层不捕获 —— 由全局 handler 统一转信封。"""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if code not in ERRORS:
            raise KeyError(f"未登记的错误码：{code!r}，请先在 ERRORS 里定义")

        self.code = code
        self.http_status, default_message = ERRORS[code]
        self.message = message or default_message
        self.detail = detail or None
        super().__init__(f"[{code}] {self.message}")

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail:
            error["detail"] = self.detail
        return {"error": error}

    def __repr__(self) -> str:
        return f"<AppError {self.http_status} {self.code}: {self.message}>"
