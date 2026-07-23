@echo off
setlocal
cd /d "%~dp0"
echo CareerOS Diagnostics
echo ====================
echo Root: %CD%
echo.
where py >nul 2>&1 && echo [OK] Python Launcher: py || echo [--] Python Launcher: py not found
where python >nul 2>&1 && echo [OK] python command available || echo [--] python command not found
if exist ".venv\Scripts\python.exe" (echo [OK] Local virtual environment exists) else (echo [--] Local virtual environment missing)
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import fastapi,uvicorn,pydantic,cryptography; print('[OK] Core Python dependencies available')" 2>nul
if exist "CareerOS_H5_Showcase.html" (echo [OK] Standalone H5 showcase exists) else (echo [!!] H5 showcase missing)
if exist "data\bootstrap.log" echo Bootstrap log: %CD%\data\bootstrap.log
if exist "data\desktop.log" echo Desktop log: %CD%\data\desktop.log
echo.
pause
