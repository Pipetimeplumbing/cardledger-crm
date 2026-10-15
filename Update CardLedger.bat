@echo off
title Update CardLedger
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 update.py
) else (
  python update.py
)
pause
