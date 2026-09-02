' start_silent.vbs
' รัน auto_refresh.py แบบไม่มีหน้าต่าง
Dim scriptPath
scriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

CreateObject("WScript.Shell").Run _
    "pythonw """ & scriptPath & "\auto_refresh.py""", _
    0, False
