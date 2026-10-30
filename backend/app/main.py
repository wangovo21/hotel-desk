from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.api import ROUTERS
from app.core.errors import ERRORS, AppError
from app.db.probe import probe

logger = logging.getLogger("hotel_desk")

_HTTP_CODE_MAP = {401: "UNAUTHORIZED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}

SWAGGER_BUNDLE = config.STATIC_DIR / "swagger" / "swagger-ui-bundle.js"
SWAGGER_CSS = config.STATIC_DIR / "swagger" / "swagger-ui.css"

FRONTEND_DIST = config.PROJECT_DIR / "frontend" / "dist"


def _envelope(code: str, message: str | None = None, detail: dict | None = None) -> dict:
    error: dict = {"code": code, "message": message or ERRORS[code][1]}
    if detail:
        error["detail"] = detail
    return {"error": error}


def _field_errors(exc: RequestValidationError) -> list[dict]:
    out: list[dict] = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        out.append({"field": ".".join(loc) or "body", "message": err.get("msg", "参数不合法")})
    return out


def register_exception_handlers(app: FastAPI) -> None:
    """四类失败收敛成同一个信封：`{"error": {"code", "message", "detail?"}}`。

    前端只解析这一种形状。少一种形状，前端就少一条"这个格子为什么是红的"的猜测。
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        log = logger.error if exc.http_status >= 500 else logger.info
        log("%s %s -> %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _field_errors(exc)
        logger.info("%s %s -> INVALID_PARAM %s", request.method, request.url.path, errors)
        return JSONResponse(
            status_code=400,
            content=_envelope("INVALID_PARAM", detail={"errors": errors}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code)
        if code is None:
            return JSONResponse(
                status_code=exc.status_code,
                content=_envelope("HTTP_ERROR", str(exc.detail) or None),
            )
        return JSONResponse(status_code=exc.status_code, content=_envelope(code))

    @app.exception_handler(sqlite3.IntegrityError)
    async def handle_integrity_error(
        request: Request, exc: sqlite3.IntegrityError
    ) -> JSONResponse:
        # 唯一索引撞车（比如同一间房同时被两张入住单占用）走到这里。
        # 这是并发或脏数据的问题，不是用户输入的问题 —— 500 而不是 400。
        logger.exception("%s %s -> DB_ERROR (%s)", request.method, request.url.path, exc)
        return JSONResponse(status_code=500, content=_envelope("DB_ERROR"))

    @app.exception_handler(sqlite3.Error)
    async def handle_sqlite_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.exception("%s %s -> DB_ERROR (%s)", request.method, request.url.path, type(exc).__name__)
        return JSONResponse(status_code=500, content=_envelope("DB_ERROR"))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("%s %s -> INTERNAL_ERROR", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_envelope("INTERNAL_ERROR"))


def docs_ready() -> bool:
    return config.DOCS_ENABLED and SWAGGER_BUNDLE.is_file() and SWAGGER_CSS.is_file()


def _register_docs(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

    @app.get("/docs", include_in_schema=False)
    async def docs_page():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{config.APP_NAME} · 接口文档",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
        )


def _mount_frontend(app: FastAPI) -> bool:
    """前端构建产物存在就一起托管 —— 这样生产环境只需要跑一个后端进程。

    dev 下没有 dist（vite 跑在 5173 并自带代理），这里静默跳过；
    打包后（npm run build）刷新页面就能直接用 8000 端口访问全部界面。
    """
    if not (FRONTEND_DIST / "index.html").is_file():
        return False
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return True


def _print_startup_banner(db_status: dict, docs_on: bool, frontend_on: bool) -> None:
    line = "=" * 70
    fl = {"flush": True}
    admin = "已启用" if config.ADMIN_TOKEN else "未配置 → 后台写接口全部返回 500（刻意如此，配好再用）"
    db_mark = "正常" if db_status["ok"] else "异常"
    docs = "已启用 /docs" if docs_on else "已关闭（DOCS_ENABLED=0 或静态资源缺失）"

    print(line, **fl)
    print(f" {config.APP_NAME}  v{config.APP_VERSION}  (env={config.APP_ENV})", **fl)
    print(f" 数据库   : {config.DB_PATH}", **fl)
    print(f"            [{db_mark}] {db_status['detail']}"
          f"（schema v{db_status['schema_version']} / {db_status['tables']} 张表）", **fl)
    print(f" 后台口令 : {admin}", **fl)
    print(f" 接口文档 : {docs}  →  http://127.0.0.1:8000/docs", **fl)
    print(f" 前端页面 : {'已托管 dist → http://127.0.0.1:8000/' if frontend_on else '未打包（dev 请开 5173）'}", **fl)
    print(line, **fl)

    if not db_status["ok"]:
        print(" [提示] 数据库不可用，先执行：python -m app.db.init_db --demo", **fl)
        print(line, **fl)
    if config.DOCS_ENABLED and not docs_on:
        print(" [警告] /docs 已禁用：本地缺少 Swagger UI 资源（app/static/swagger）", **fl)
        print(line, **fl)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _print_startup_banner(probe(config.DB_PATH), docs_ready(), (FRONTEND_DIST / "index.html").is_file())
    yield
    logger.info("服务已停止")


def create_app() -> FastAPI:
    docs_on = docs_ready()

    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        description=(
            "酒店前台录入系统的接口文档。\n\n"
            "覆盖房态、入住登记、续住、换房、杂费与退房结账。\n"
            "金额一律用「分」的整数传输，日期用 `YYYY-MM-DD`，时刻用 `YYYY-MM-DD HH:MM:SS`。"
        ),
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_on else None,
    )

    if config.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.CORS_ORIGINS,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    for router in ROUTERS:
        app.include_router(router, prefix="/api")

    if docs_on:
        _register_docs(app)

    # ★ 必须放在 API 与 docs 之后：mount("/") 会兜住所有未匹配路径，
    #   注册早了会把 /api/* 一起吃掉。
    _mount_frontend(app)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
