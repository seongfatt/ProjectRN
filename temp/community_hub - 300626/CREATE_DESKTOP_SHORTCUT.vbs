Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oLink = WshShell.CreateShortcut(strDesktop & "\Community Hub.lnk")
oLink.TargetPath = CreateObject("Scripting.FileSystemObject").GetAbsolutePathName("START_APP.bat")
oLink.WorkingDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
oLink.IconLocation = "%SystemRoot%\System32\SHELL32.dll,14"
oLink.Description = "Woodlands Zone 6 - Community Hub"
oLink.Save
MsgBox "Shortcut created on Desktop!", 64, "Done"
