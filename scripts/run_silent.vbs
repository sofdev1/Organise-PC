' Runs run_forever.bat hidden (no console window) using the current folder.
' run_forever.bat relaunches main.py automatically if it ever crashes/exits.
' Used by install_startup.bat to launch the suite silently on login.

Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)

objShell.CurrentDirectory = projectDir
objShell.Run """" & projectDir & "\run_forever.bat""", 0, False