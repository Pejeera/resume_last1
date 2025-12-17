# Simple deploy - try to use existing dependencies or minimal set
$functionName = "ResumeMatchAPI"
$region = "us-east-1"
$zipFile = "lambda-deployment.zip"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Simple Lambda Deploy" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $functionName" -ForegroundColor Yellow
Write-Host "Region: $region" -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: This will use existing dependencies." -ForegroundColor Yellow
Write-Host "For Linux-compatible deps, use Docker method." -ForegroundColor Yellow
Write-Host ""

# Create minimal package with source code only
Write-Host "[1/3] Creating package..." -ForegroundColor Green
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue
}

# Include only source code - Lambda may have some dependencies already
$items = @("app", "*.py", "requirements.txt")

# Try to include key dependencies if they exist
$keyDeps = @("mangum", "fastapi", "starlette", "pydantic")
foreach ($dep in $keyDeps) {
    if (Test-Path $dep) {
        $items += $dep
        Write-Host "  Including: $dep" -ForegroundColor Gray
    }
}

Compress-Archive -Path $items -DestinationPath $zipFile -Force
Write-Host "Created: $zipFile ($([math]::Round((Get-Item $zipFile).Length / 1MB, 2)) MB)" -ForegroundColor Green

# Upload
Write-Host "[2/3] Uploading to Lambda..." -ForegroundColor Green
aws lambda update-function-code `
    --function-name $functionName `
    --zip-file "fileb://$zipFile" `
    --region $region

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload" -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Waiting for update..." -ForegroundColor Green
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "Test: python test_api_routes.py" -ForegroundColor Yellow

