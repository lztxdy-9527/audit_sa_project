@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Run one-click reconcile on the DIFF DEMO package (A-B04: one shadow bank line).
echo Expect 7 cases (1 R02 clue + 6 bank differences/unmatched) and overall SUCCESS_WITH_DIFFERENCES.
echo.
".venv\Scripts\python.exe" -B scripts\run_all.py --config config\run_all_diff_demo.json --allow-differences --open
echo.
echo Done. Output folder: outputs\RUN_ID\index.html
pause
