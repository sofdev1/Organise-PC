@echo off
REM Removes the auto-start shortcut created by install_startup.bat

set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Organise_PC.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo Removed auto-start shortcut. The suite will no longer launch at login.
) else (
    echo No auto-start shortcut found. Nothing to do.
)
pause
