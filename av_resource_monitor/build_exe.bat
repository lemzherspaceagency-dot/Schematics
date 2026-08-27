@echo off
REM Builds a standalone Windows .exe of the GUI monitor - no Python needed
REM to RUN it afterwards. Run this ONCE (Python is only needed for this
REM build step) - e.g. once inside your Windows Sandbox, or on any other
REM Windows machine, then copy the resulting .exe wherever you like,
REM including into future fresh Sandbox sessions.

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"
    echo and make sure "tcl/tk and IDLE" stays checked^), then run this file again.
    pause
    exit /b 1
)

echo Installing build dependencies ^(pyinstaller, psutil^)...
python -m pip install --upgrade --quiet pyinstaller psutil
if errorlevel 1 (
    echo pip install failed - check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo Building AV_Resource_Monitor.exe ...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name AV_Resource_Monitor ^
    av_monitor_gui.py

if errorlevel 1 (
    echo Build failed - see the errors above.
    pause
    exit /b 1
)

copy /y "dist\AV_Resource_Monitor.exe" "AV_Resource_Monitor.exe" >nul
rmdir /s /q build >nul 2>nul
del /q AV_Resource_Monitor.spec >nul 2>nul

echo.
echo Done. AV_Resource_Monitor.exe is ready in this folder.
echo You can now copy just that one .exe file anywhere - it no longer needs Python.
pause
