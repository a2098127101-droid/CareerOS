$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "请先运行 windows\Setup_CareerOS_Windows.cmd" -ForegroundColor Yellow
    exit 1
}
& ".venv\Scripts\python.exe" -m pip install pyinstaller
& ".venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm --clean --windowed --name CareerOS `
    --add-data "app/static;app/static" `
    --add-data "knowledge;knowledge" `
    --collect-all uvicorn `
    --collect-all fastapi `
    --hidden-import app.main `
    --hidden-import app.agent_service `
    --hidden-import app.llm_gateway `
    desktop_launcher.pyw
Write-Host "构建完成：dist\CareerOS\CareerOS.exe" -ForegroundColor Green
