' Silent PyScribe launcher for the source project.
' Uses pythonw.exe so no console window is created.
Option Explicit

Dim shell, fso, root, pythonw, mainPy, rc
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
mainPy = fso.BuildPath(root, "main.py")

pythonw = "pythonw.exe"
If fso.FileExists(fso.BuildPath(root, "pythonw.exe")) Then
    pythonw = fso.BuildPath(root, "pythonw.exe")
End If

If Not fso.FileExists(mainPy) Then
    MsgBox "PyScribe: main.py не найден." & vbCrLf & mainPy, vbCritical, "PyScribe"
    WScript.Quit 1
End If

shell.CurrentDirectory = root
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & mainPy & Chr(34), 0, False
WScript.Quit 0
