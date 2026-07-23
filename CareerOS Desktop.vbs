Option Explicit
Dim fso, shell, root, launcher
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = root & "\OPEN_CareerOS.cmd"
shell.Run Chr(34) & launcher & Chr(34), 1, False
