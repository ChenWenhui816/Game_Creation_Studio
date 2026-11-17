@echo off
setlocal
cd /d "%~dp0"
echo Starting Game Creation Studio...
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\gameconsole.py serve
) else (
  python scripts\gameconsole.py serve
)
if errorlevel 1 pause
