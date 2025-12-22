# Script to create Lambda Layer for requests and requests-aws4auth
# This replaces bundling dependencies in Lambda package

Write-Host "=== Creating Lambda Layer for requests ===" -ForegroundColor Cyan

# Create directory for Layer
$layerDir = "lambda-layer"
$pythonDir = Join-Path $layerDir "python"

Write-Host "`n[1/4] Creating directories..." -ForegroundColor Yellow
if (Test-Path $layerDir) {
    Write-Host "Removing old directory..." -ForegroundColor Yellow
    Remove-Item -Path $layerDir -Recurse -Force
}

New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
Write-Host "[OK] Created directory $pythonDir" -ForegroundColor Green

# Install dependencies
Write-Host "`n[2/4] Installing requests and requests-aws4auth..." -ForegroundColor Yellow
Push-Location $pythonDir

try {
    # Install using pip into python/ directory
    pip install requests requests-aws4auth -t . --quiet
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] pip install failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[OK] Dependencies installed successfully" -ForegroundColor Green
    
    # Check if requests is installed
    if (Test-Path "requests") {
        Write-Host "[OK] Found requests/" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] requests/ not found" -ForegroundColor Red
        exit 1
    }
    
    if (Test-Path "requests_aws4auth") {
        Write-Host "[OK] Found requests_aws4auth/" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] requests_aws4auth/ not found (may not be required)" -ForegroundColor Yellow
    }
    
} finally {
    Pop-Location
}

# Create ZIP file
Write-Host "`n[3/4] Creating ZIP file..." -ForegroundColor Yellow
$zipFile = "requests-layer.zip"

if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
    Write-Host "Removed old $zipFile" -ForegroundColor Yellow
}

# Use Compress-Archive (PowerShell built-in)
Push-Location $layerDir
Compress-Archive -Path "python" -DestinationPath "..\$zipFile" -Force
Pop-Location

if (Test-Path $zipFile) {
    $zipSize = (Get-Item $zipFile).Length / 1MB
    $zipSizeRounded = [math]::Round($zipSize, 2)
    Write-Host "[OK] Created $zipFile successfully (Size: $zipSizeRounded MB)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create ZIP" -ForegroundColor Red
    exit 1
}

# Verify structure in ZIP
Write-Host "`n[4/4] Verifying ZIP structure..." -ForegroundColor Yellow
$tempExtract = "temp-zip-check"
if (Test-Path $tempExtract) {
    Remove-Item $tempExtract -Recurse -Force
}

Expand-Archive -Path $zipFile -DestinationPath $tempExtract -Force

$expectedDirs = @("python/requests", "python/urllib3", "python/certifi")
$allFound = $true

foreach ($dir in $expectedDirs) {
    $fullPath = Join-Path $tempExtract $dir
    if (Test-Path $fullPath) {
        Write-Host "[OK] Found $dir" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Not found $dir" -ForegroundColor Red
        $allFound = $false
    }
}

Remove-Item $tempExtract -Recurse -Force

if (-not $allFound) {
    Write-Host "`n[ERROR] ZIP structure is incorrect" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Layer created successfully ===" -ForegroundColor Green
Write-Host "`nCreated file: $zipFile" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Go to AWS Console -> Lambda -> Layers" -ForegroundColor White
Write-Host "2. Create layer" -ForegroundColor White
Write-Host "3. Upload: $zipFile" -ForegroundColor White
Write-Host "4. Runtime: Python 3.10 (or Python 3.11)" -ForegroundColor White
Write-Host "5. Create" -ForegroundColor White
Write-Host "`nOr use deploy_lambda_with_layer.ps1 script for automatic deployment" -ForegroundColor Cyan
