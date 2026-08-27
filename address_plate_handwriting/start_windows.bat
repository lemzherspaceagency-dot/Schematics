@echo off
rem Double-click this to start the handwriting app.
cd /d "%~dp0"
py capture_handwriting.py
if errorlevel 1 python capture_handwriting.py
if errorlevel 1 (
  echo.
  echo Could not start. Install Python from python.org ^(tick "Add Python to PATH"^),
  echo then double-click this file again.
  pause
)
