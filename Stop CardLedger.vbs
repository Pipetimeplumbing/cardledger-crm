Option Explicit
Dim shell, files, folder, launcher
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
launcher = Chr(34) & folder & "\background.pyw" & Chr(34)
On Error Resume Next
shell.Run "pyw -3 " & launcher & " --stop", 0, False
If Err.Number <> 0 Then
  Err.Clear
  shell.Run "pythonw " & launcher & " --stop", 0, False
  If Err.Number <> 0 Then MsgBox "Python's windowless launcher could not be found.", 16, "CardLedger"
End If
