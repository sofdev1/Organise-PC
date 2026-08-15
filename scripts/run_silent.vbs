' Runs main.py with pythonw.exe (no console window) using the current folder.
' Used by install_startup.bat to launch the suite silently on login.

Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)

objShell.CurrentDirectory = projectDir
objShell.Run "pythonw.exe main.py", 0, False
