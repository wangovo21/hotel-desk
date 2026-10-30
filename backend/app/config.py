from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """极简 .env 读取：KEY=VALUE、# 注释、去掉成对引号。

    刻意不引第三方库（python-dotenv）：这里只需要"读几行配置"，
    多一个依赖就多一个装不上的理由。**已存在的环境变量优先**，
    这样部署时用 shell 变量覆盖 .env 是自然生效的。
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

APP_NAME = "酒店前台录入系统"
APP_VERSION = "1.0.0"
APP_ENV = os.environ.get("APP_ENV", "dev").strip().lower()

DB_PATH = Path(os.environ.get("DB_PATH") or (BACKEND_DIR / "data" / "hotel.db"))

# 后台写接口口令。前台动作不受它约束（见 README「权限边界」）。
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

STATIC_DIR = BACKEND_DIR / "app" / "static"

DOCS_ENABLED = os.environ.get("DOCS_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
    "",
)
