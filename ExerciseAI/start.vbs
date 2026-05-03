Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strPythonW = "C:\Users\damian\AppData\Local\Programs\Python\Python311\pythonw.exe"
strScript = strPath & "\exercise_ai.py"

objShell.CurrentDirectory = strPath
' Nutze 1 (Normal) statt 0 (Hide). pythonw.exe öffnet sowieso keine Konsole,
' aber 0 zwingt Windows dazu, ALLE Fenster des Prozesses zu verstecken (auch die PyQt GUI!)
objShell.Run """" & strPythonW & """ """ & strScript & """", 1, False
