#!/usr/bin/env python
"""一键启动：建库 → 对齐前后端口令 → 起后端 8000 + 前端 5173 → 打开浏览器。

`start.bat` / `run-local.sh` 都只是"找一个能用的 Python"的壳，真正的逻辑全在这里，
免得两个平台各写一遍、慢慢走偏。

两种模式：
    python start.py            开发模式：后端 --reload + vite dev（改了代码立刻生效）
    python start.py --prod     生产模式：npm run build，然后只起后端（dist 由 FastAPI 托管）
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DB_FILE = BACKEND / "data" / "hotel.db"

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-admin-token")

IS_WIN = os.name == "nt"
LINE = "=" * 70


def log(msg: str) -> None:
    print(msg, flush=True)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def ensure_env_files() -> None:
    """生成/沿用前后端 .env —— 关键是**两边的口令必须一致**。

    前端把口令打包进产物、后端拿它做比对；一边有值一边没有，
    表现是"页面能看、一保存就 401"，而且报错信息不会告诉你是这个原因。
    所以这里统一由启动脚本写一次，不信手工维护。
    """
    backend_env = BACKEND / ".env"
    if not backend_env.is_file():
        backend_env.write_text(
            "APP_ENV=dev\n"
            f"ADMIN_TOKEN={ADMIN_TOKEN}\n"
            "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n"
            "DOCS_ENABLED=1\n",
            encoding="utf-8",
        )
        log(f"[env] 已生成 {backend_env.relative_to(ROOT)}")

    frontend_env = FRONTEND / ".env"
    if not frontend_env.is_file():
        frontend_env.write_text(
            f"VITE_ADMIN_TOKEN={ADMIN_TOKEN}\nVITE_API_BASE=\n", encoding="utf-8"
        )
        log(f"[env] 已生成 {frontend_env.relative_to(ROOT)}")


def ensure_deps(demo: bool) -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        log("[deps] 缺少 fastapi/uvicorn，开始安装后端依赖…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(BACKEND / "requirements.txt")],
            cwd=str(BACKEND),
        )

    if not DB_FILE.is_file():
        log("[db] 数据库不存在，开始建库" + ("（含演示数据）" if demo else "（空库）"))
        cmd = [sys.executable, "-m", "app.db.init_db"]
        if demo:
            cmd.append("--demo")
        subprocess.check_call(cmd, cwd=str(BACKEND))
    else:
        log(f"[db] 使用已有数据库 {DB_FILE.relative_to(ROOT)}")


def ensure_node_modules() -> None:
    if (FRONTEND / "node_modules").is_dir():
        return
    log("[web] 首次运行，安装前端依赖（约 1~2 分钟）…")
    npm = "npm.cmd" if IS_WIN else "npm"
    if shutil.which(npm) is None:
        raise SystemExit("找不到 npm。请先安装 Node.js 18+ 后重试。")
    subprocess.check_call([npm, "install", "--no-audit", "--no-fund"], cwd=str(FRONTEND))


def wait_health(port: int, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.5)
    return False


def spawn(cmd: list[str], cwd: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.Popen(cmd, cwd=str(cwd), env=env)


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if IS_WIN:
        # taskkill /T 连子进程一起收掉：vite 会再拉一个 esbuild 子进程，
        # 只 kill 父进程会留下它占着 5173
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="酒店前台录入系统 · 一键启动")
    parser.add_argument("--prod", action="store_true", help="构建前端并由后端统一托管（单端口 8000）")
    parser.add_argument("--port", type=int, default=8000, help="后端端口，默认 8000")
    parser.add_argument("--web-port", type=int, default=5173, help="前端 dev 端口，默认 5173")
    parser.add_argument("--no-demo", action="store_true", help="建空库，不灌演示数据")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args(argv)

    demo = not args.no_demo

    log(LINE)
    log(" 酒店前台录入系统 · 启动中")
    log(LINE)

    if not port_free(args.port):
        log(f"[错误] 端口 {args.port} 已被占用。先关掉占用它的进程，或换 --port")
        return 1
    if not args.prod and not port_free(args.web_port):
        log(f"[错误] 端口 {args.web_port} 已被占用。先关掉它，或换 --web-port")
        return 1

    ensure_env_files()
    ensure_deps(demo)
    ensure_node_modules()

    backend_proc: subprocess.Popen | None = None
    frontend_proc: subprocess.Popen | None = None
    open_url = f"http://127.0.0.1:{args.port}/"

    try:
        if args.prod:
            log("[web] 构建前端…")
            npm = "npm.cmd" if IS_WIN else "npm"
            subprocess.check_call([npm, "run", "build"], cwd=str(FRONTEND))
            log("[api] 启动后端（托管 dist，单端口）…")
            backend_proc = spawn(
                [sys.executable, "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", str(args.port)],
                BACKEND,
            )
        else:
            log("[api] 启动后端 :%d（--reload）…" % args.port)
            backend_proc = spawn(
                [sys.executable, "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", str(args.port), "--reload"],
                BACKEND,
            )

            if not wait_health(args.port, timeout=20):
                log("[警告] 后端健康检查没通过，仍继续起前端（页面会显示「后端不可用」）")
            else:
                log("[api] 后端就绪")

            log("[web] 启动前端 :%d …" % args.web_port)
            npm = "npm.cmd" if IS_WIN else "npm"
            frontend_proc = spawn([npm, "run", "dev", "--", "--port", str(args.web_port)], FRONTEND)
            open_url = f"http://127.0.0.1:{args.web_port}/"

        if not wait_health(args.port, timeout=30):
            log("[警告] 后端暂未通过健康检查，请看下方日志")

        log(LINE)
        log(f" 界面   : {open_url}")
        log(f" 接口   : http://127.0.0.1:{args.port}/docs")
        log(f" 后台口令: {ADMIN_TOKEN}（房型/房间/客人档案/参数这些写接口需要）")
        log(" 停止   : Ctrl+C")
        log(LINE)

        if not args.no_browser:
            webbrowser.open(open_url)

        # 前台/后端任一进程退出就收摊，不要留下半个系统在跑
        while True:
            if backend_proc.poll() is not None:
                log("[退出] 后端进程已结束")
                break
            if frontend_proc is not None and frontend_proc.poll() is not None:
                log("[退出] 前端进程已结束")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        log("\n[停止] 收到 Ctrl+C，正在收尾…")
    finally:
        stop(frontend_proc)
        stop(backend_proc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
