@echo off
title CardLedger - Sports and Trading Card CRM
cd /d "%~dp0"
echo Starting CardLedger CRM...
echo Sports cards, Pokemon, Marvel, Disney, and Magic: The Gathering
echo Keep this window open while using CardLedger.
echo.
where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 start.py
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python is required. Install Python 3.12 or newer from python.org.
    echo During installation, select Add Python to PATH.
    pause
    exit /b 1
  )
  python start.py
)
pause
