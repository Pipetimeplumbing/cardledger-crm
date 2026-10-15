Option Explicit
Dim shell, files, folder, launcher, result
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
launcher = Chr(34) & folder & "\background.pyw" & Chr(34)
On Error Resume Next
shell.Run "pyw -3 " & launcher, 0, False
If Err.Number <> 0 Then
  Err.Clear
  shell.Run "pythonw " & launcher, 0, False
  If Err.Number <> 0 Then MsgBox "Install Python 3.12 or newer with its launcher, then try again.", 16, "CardLedger"
End If
