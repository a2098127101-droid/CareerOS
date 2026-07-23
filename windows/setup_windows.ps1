$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
Write-Host "CareerOS Windows Setup" -ForegroundColor White

$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    $PyCmd = "py"
    $PyArgs = @("-3")
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) {
        throw "Python was not found. Install Python 3.11+ and enable Add Python to PATH."
    }
    $PyCmd = "python"
    $PyArgs = @()
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $PyCmd @PyArgs -m venv .venv
}

Write-Host "Installing dependencies..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

# Desktop shortcut directly targets pythonw.exe. This intentionally bypasses
# Windows Script Host so UTF-8/ANSI VBScript parsing cannot break startup.
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "CareerOS.lnk"
$PythonW = Join-Path $Root ".venv\Scripts\pythonw.exe"
$Launcher = Join-Path $Root "desktop_launcher.pyw"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = '"' + $Launcher + '"'
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "CareerOS - AI Career Planning Operating System"
$Shortcut.Save()

Write-Host ""
Write-Host "Setup completed." -ForegroundColor Green
Write-Host "A CareerOS shortcut has been created on your Windows Desktop."
Write-Host "From now on, double-click CareerOS on the Desktop to launch the app."
Write-Host ""
Write-Host "Shortcut target:" -ForegroundColor DarkGray
Write-Host $PythonW -ForegroundColor DarkGray
Read-Host "Press Enter to close"
