Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strScript = strPath & "\exercise_ai.py"

' === pythonw.exe dynamisch finden ===
strPythonW = ""

' Methode 1: Python Launcher (C:\Windows\py.exe) - immer verfuegbar
strPyLauncher = "C:\Windows\py.exe"
If fso.FileExists(strPyLauncher) Then
    On Error Resume Next
    Set objExec = objShell.Exec("""" & strPyLauncher & """ -c ""import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))""")
    strPythonW = Trim(objExec.StdOut.ReadAll())
    On Error GoTo 0
    If Not fso.FileExists(strPythonW) Then strPythonW = ""
End If

' Methode 2: Windows Registry Fallback
If strPythonW = "" Then
    On Error Resume Next
    strPythonW = objShell.RegRead("HKCU\Software\Python\PythonCore\3.11\InstallPath\WindowedExecutablePath")
    On Error GoTo 0
    If Not fso.FileExists(strPythonW) Then strPythonW = ""
End If

' Nichts gefunden -> Fehlermeldung
If strPythonW = "" Then
    MsgBox "Fehler: Python wurde nicht gefunden!" & vbCrLf & vbCrLf & _
           "Bitte stelle sicher, dass Python installiert ist.", _
           vbCritical, "ExerciseAI - Startfehler"
    WScript.Quit
End If

objShell.CurrentDirectory = strPath

' Nutze 1 (Normal) statt 0 (Hide). pythonw.exe öffnet sowieso keine Konsole,
' aber 0 zwingt Windows dazu, ALLE Fenster des Prozesses zu verstecken (auch die PyQt GUI!)
objShell.Run """" & strPythonW & """ """ & strScript & """", 1, False
