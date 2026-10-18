@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running one-click reconcile WITH differences allowed...
echo   demo step four-way differences are tolerated; site is still published.
echo.
".venv\Scripts\python.exe" -B scripts\run_all.py --allow-differences --open
echo.
echo Done. Output folder: outputs\RUN_ID\index.html  (overall may be SUCCESS_WITH_DIFFERENCES)
pause
