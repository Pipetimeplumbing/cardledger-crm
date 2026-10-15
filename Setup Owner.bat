@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Open CardLedger once to install its Python environment, then run this file again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" setup_owner.py
pause
