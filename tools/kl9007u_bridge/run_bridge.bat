@echo off
rem KL9007U 读写器桥接：刷卡自动发卡/退卡（必须用 32 位 Python，见同目录 py32）
chcp 65001 >nul
cd /d "%~dp0"

echo 用法示例：
echo   run_bridge.bat                 启动后从在住列表里选目标
echo   run_bridge.bat 8301            直接以 8301 房为刷卡目标
echo   run_bridge.bat 8301 revoke     刷卡 = 退卡
echo.

if "%~1"=="" (
  py32\python.exe -u bridge.py %*
) else (
  py32\python.exe -u bridge.py --stay %1 %2 %3 %4 %5
)
pause
