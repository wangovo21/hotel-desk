@echo off
chcp 65001 >nul
setlocal

rem ===========================================================================
rem  酒店前台录入系统 · Windows 一键启动
rem  只做一件事：找一个装了依赖的 Python，然后把 start.py 跑起来。
rem  真正的逻辑都在 start.py 里（macOS / Linux 用的是同一个文件）。
rem ===========================================================================

cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [错误] 没找到 Python。请先安装 Python 3.11+ 并勾选 "Add to PATH"。
    pause
    exit /b 1
)

%PY% start.py %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
    echo.
    echo [启动失败] 退出码 %CODE%，请把上面的报错发出来。
    pause
)
endlocal
