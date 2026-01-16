# Start Backend API Server
# Usage: .\start_backend.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Backend API Server" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$backendDir = $PSScriptRoot

Write-Host "Backend directory: $backendDir" -ForegroundColor Yellow
Write-Host "Server will start on: http://localhost:8000" -ForegroundColor Yellow
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Green
Write-Host ""

# Check if Python is available
$pythonCmd = "python"
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python not found! Please install Python first." -ForegroundColor Red
    exit 1
}

# Start FastAPI server
Set-Location $backendDir
& $pythonCmd main.py

