@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running one-click audit reconcile (machine checks + HTML output)...
".venv\Scripts\python.exe" -B scripts\run_all.py --open
echo.
echo Done. Output folder: outputs\RUN_ID\index.html
pause
