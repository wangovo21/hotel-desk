from __future__ import annotations

import hmac
import sqlite3
from dataclasses import dataclass
from typing import Iterator

from fastapi import Depends, Header, Query

from app import config
from app.core.errors import AppError
from app.db import connect


def get_db() -> Iterator[sqlite3.Connection]:
    """每个请求一条连接，请求结束关掉。

    SQLite + WAL 下连接开销极小（毫秒级），换来的是"请求之间绝不会有
    共享连接的脏状态"。连接池在这里是负优化。
    """
    conn = connect(config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@dataclass(frozen=True)
class Page:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数，上限 200"),
) -> Page:
    return Page(page=page, page_size=page_size)


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> str:
    """后台写接口的口令校验。

    ★ 它挡的是"局域网里随手构造一个 POST 就能改房价/删房间"，**不是登录**：
      口令是构建期注入前端产物的静态串，打开开发者工具就能看到。
      本系统的安全边界是"前台内网 + 只对员工开放"，不是公网多租户。
      真要多操作员审计，得换成每人一账号的会话体系（未实现）。

    ★ 前台日常动作（入住/续住/换房/加费/退房）**不走这个校验** ——
      收银员每来一个客人都要输一次口令的系统，最后一定是口令贴在显示器上。
    """
    expected = config.ADMIN_TOKEN
    if not expected:
        raise AppError("ADMIN_TOKEN_NOT_CONFIGURED")

    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode("utf-8"), expected.encode("utf-8")
    ):
        raise AppError("UNAUTHORIZED")

    return x_admin_token


AdminGuard = Depends(require_admin)
DbConn = Depends(get_db)
PageDep = Depends(pagination)
