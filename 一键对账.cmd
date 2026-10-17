@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在运行一键对账（机器核对 + 出页），请稍候...
".venv\Scripts\python.exe" -B scripts\run_all.py --open
echo.
echo 运行结束。结果目录：outputs\<run_id>\（index.html 为入口）。
pause
