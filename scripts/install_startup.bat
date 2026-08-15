@echo off
REM Adds a shortcut to run_silent.vbs in the current user's Startup folder,
REM so Organise_PC launches automatically on login.
REM Safe to run multiple times — it just overwrites its own shortcut.

setlocal
set "SCRIPT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\Organise_PC.lnk"

powershell -NoProfile -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell;" ^
  "$Shortcut = $WshShell.CreateShortcut('%SHORTCUT%');" ^
  "$Shortcut.TargetPath = 'wscript.exe';" ^
  "$Shortcut.Arguments = '\"%SCRIPT_DIR%run_silent.vbs\"';" ^
  "$Shortcut.WorkingDirectory = '%SCRIPT_DIR%';" ^
  "$Shortcut.Description = 'Organise_PC';" ^
  "$Shortcut.Save()"

echo.
echo Done. A shortcut was added to your Startup folder:
echo %SHORTCUT%
echo.
echo The suite will now start automatically next time you log in.
echo To stop it from auto-starting, delete that shortcut.
pause
