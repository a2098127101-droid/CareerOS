$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonW = Join-Path $Root ".venv\Scripts\pythonw.exe"
$Launcher = Join-Path $Root "desktop_launcher.pyw"

if (-not (Test-Path $PythonW)) {
    Write-Host "CareerOS virtual environment is missing. Running setup first..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "setup_windows.ps1")
    exit
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "CareerOS.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = '"' + $Launcher + '"'
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "CareerOS - AI Career Planning Operating System"
$Shortcut.Save()

Write-Host "CareerOS Desktop shortcut repaired successfully." -ForegroundColor Green
Write-Host $ShortcutPath
Read-Host "Press Enter to close"
