# Quick script to check Docker status
Write-Host "Checking Docker status..." -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker is installed: $dockerVersion" -ForegroundColor Green
    } else {
        Write-Host "Docker is not installed" -ForegroundColor Red
        Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "Docker is not installed" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if Docker daemon is running
Write-Host ""
Write-Host "Checking Docker daemon..." -ForegroundColor Cyan
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker daemon is running" -ForegroundColor Green
        Write-Host ""
        Write-Host "You can now run: .\deploy_lambda_docker.ps1" -ForegroundColor Green
    } else {
        Write-Host "Docker daemon is NOT running" -ForegroundColor Red
        Write-Host ""
        Write-Host "To fix this:" -ForegroundColor Yellow
        Write-Host "1. Open Docker Desktop application" -ForegroundColor Yellow
        Write-Host "2. Wait for Docker to start (look for whale icon in system tray)" -ForegroundColor Yellow
        Write-Host "3. Run this script again to verify" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Or start Docker Desktop manually:" -ForegroundColor Yellow
        Write-Host "  Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" -ForegroundColor Gray
    }
} catch {
    Write-Host "Error checking Docker daemon: $_" -ForegroundColor Red
}

Write-Host ""

