@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "data" mkdir "data" >nul 2>&1
set "BOOTLOG=%CD%\data\bootstrap.log"

echo ================================================== > "%BOOTLOG%"
echo CareerOS bootstrap - %date% %time% >> "%BOOTLOG%"
echo Root: %CD% >> "%BOOTLOG%"
echo ================================================== >> "%BOOTLOG%"

if exist ".venv\Scripts\python.exe" goto checkenv

echo CareerOS first-run initialization...
echo This may take several minutes the first time.
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=py -3"
    goto makevenv
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=python"
    goto makevenv
)

echo Python 3.11+ was not found. >> "%BOOTLOG%"
echo.
echo Python 3.11+ is required for the full CareerOS application.
echo The standalone H5 showcase will open instead.
echo.
start "" "CareerOS_H5_Showcase.html"
pause
exit /b 1

:makevenv
echo Creating local environment...
%PYCMD% -m venv .venv >> "%BOOTLOG%" 2>&1
if errorlevel 1 goto fail

echo Installing CareerOS dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%BOOTLOG%" 2>&1
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%BOOTLOG%" 2>&1
if errorlevel 1 goto fail


:checkenv
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,pydantic,cryptography" >nul 2>&1
if errorlevel 1 (
    echo Repairing CareerOS dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%BOOTLOG%" 2>&1
    if errorlevel 1 goto fail
)

:launch
if not exist ".venv\Scripts\pythonw.exe" goto fail
rem Best-effort Desktop shortcut creation. Failure here does not block launch.
powershell -NoProfile -ExecutionPolicy Bypass -File "windows\repair_desktop_shortcut_silent.ps1" >nul 2>&1
start "" ".venv\Scripts\pythonw.exe" "desktop_launcher.pyw"
exit /b 0

:fail
echo.
echo CareerOS initialization failed.
echo Log: %BOOTLOG%
echo.
echo Opening the standalone H5 showcase as a fallback.
start "" "CareerOS_H5_Showcase.html"
pause
exit /b 1
