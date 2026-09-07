@echo off
REM Restart loop: relaunches main.py if it ever exits/crashes.
REM Uses pythonw.exe (no console flash on each restart) and paths relative
REM to this file's own location, so it works regardless of where the
REM project folder is placed.

setlocal
set "SCRIPT_DIR=%~dp0"

:loop
"%SCRIPT_DIR%tg-renamer\Scripts\pythonw.exe" "%SCRIPT_DIR%main.py"
timeout /t 5 /nobreak >nul
goto loop