$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonW = Join-Path $Root ".venv\Scripts\pythonw.exe"
$Launcher = Join-Path $Root "desktop_launcher.pyw"
if (-not (Test-Path $PythonW)) { exit 0 }
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "CareerOS.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = '"' + $Launcher + '"'
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "CareerOS - AI Career Planning Operating System"
$Shortcut.Save()
exit 0
