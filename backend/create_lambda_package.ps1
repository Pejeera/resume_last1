# Script to create Lambda function package (code only, no dependencies)
# Use when deploying Lambda function with Layer

param(
    [string]$SourceFile = "lambda-final/lambda_function.py",
    [string]$OutputFile = "lambda-function-only.zip"
)

Write-Host "=== Creating Lambda Function Package (code only) ===" -ForegroundColor Cyan

# Check source file
if (-not (Test-Path $SourceFile)) {
    Write-Host "`n[WARNING] Not found $SourceFile" -ForegroundColor Yellow
    Write-Host "Trying lambda_function.py instead..." -ForegroundColor Yellow
    $SourceFile = "lambda_function.py"
    
    if (-not (Test-Path $SourceFile)) {
        Write-Host "`n[ERROR] Lambda function code not found" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n[1/3] Reading Lambda function code..." -ForegroundColor Yellow
$code = Get-Content $SourceFile -Raw

# Check for sys.path manipulation (should not have if using Layer)
if ($code -match "sys\.path\.insert|sys\.path\.append") {
    Write-Host "`n[WARNING] Found sys.path manipulation in code" -ForegroundColor Yellow
    Write-Host "If using Lambda Layer, this should not be present" -ForegroundColor Yellow
    Write-Host "Continue? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne "Y" -and $response -ne "y") {
        exit 0
    }
}

# Check for import requests
if ($code -notmatch "import requests") {
    Write-Host "`n[WARNING] 'import requests' not found in code" -ForegroundColor Yellow
    Write-Host "Please verify code is correct" -ForegroundColor Yellow
}

Write-Host "[OK] Code read successfully" -ForegroundColor Green

# Create temporary directory
Write-Host "`n[2/3] Creating package..." -ForegroundColor Yellow
$tempDir = "temp-lambda-package"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy lambda function code
Copy-Item $SourceFile -Destination (Join-Path $tempDir "lambda_function.py")

Write-Host "[OK] Code copied successfully" -ForegroundColor Green

# Create ZIP
Write-Host "`n[3/3] Creating ZIP file..." -ForegroundColor Yellow
if (Test-Path $OutputFile) {
    Remove-Item $OutputFile -Force
    Write-Host "Removed old $OutputFile" -ForegroundColor Yellow
}

Push-Location $tempDir
Compress-Archive -Path "lambda_function.py" -DestinationPath "..\$OutputFile" -Force
Pop-Location

Remove-Item $tempDir -Recurse -Force

if (Test-Path $OutputFile) {
    $zipSize = (Get-Item $OutputFile).Length / 1KB
    $zipSizeRounded = [math]::Round($zipSize, 2)
    Write-Host "[OK] Created $OutputFile successfully (Size: $zipSizeRounded KB)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create ZIP" -ForegroundColor Red
    exit 1
}

# Verify ZIP contents
Write-Host "`nVerifying ZIP contents..." -ForegroundColor Yellow
$tempCheck = "temp-zip-check"
if (Test-Path $tempCheck) {
    Remove-Item $tempCheck -Recurse -Force
}

Expand-Archive -Path $OutputFile -DestinationPath $tempCheck -Force

$files = Get-ChildItem -Path $tempCheck -Recurse -File
Write-Host "Files in ZIP:" -ForegroundColor Gray
foreach ($file in $files) {
    Write-Host "  - $($file.Name)" -ForegroundColor Gray
}

# Check that there's no python/ directory (should not have if using Layer)
if (Test-Path (Join-Path $tempCheck "python")) {
    Write-Host "`n[WARNING] Found python/ directory in ZIP" -ForegroundColor Yellow
    Write-Host "If using Lambda Layer, dependencies should not be in ZIP" -ForegroundColor Yellow
}

Remove-Item $tempCheck -Recurse -Force

Write-Host "`n=== Package created successfully ===" -ForegroundColor Green
Write-Host "`nCreated file: $OutputFile" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Use deploy_lambda_with_layer.ps1 for automatic deployment" -ForegroundColor White
Write-Host "2. Or upload $OutputFile to Lambda function in AWS Console" -ForegroundColor White
Write-Host "3. Verify that Layer is attached to Lambda function" -ForegroundColor White
