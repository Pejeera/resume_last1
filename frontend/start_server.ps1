# Start local web server for frontend
# Usage: .\start_server.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Frontend Web Server" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$port = 8000
$frontendDir = $PSScriptRoot

Write-Host "Frontend directory: $frontendDir" -ForegroundColor Yellow
Write-Host "Server will start on: http://localhost:$port" -ForegroundColor Yellow
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

# Start Python HTTP server
Set-Location $frontendDir
& $pythonCmd -m http.server $port

