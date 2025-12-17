# Fixed deploy script - includes ALL dependencies
$functionName = "ResumeMatchAPI"
$region = "us-east-1"
$zipFile = "lambda-deployment.zip"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Lambda Function (Fixed)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $functionName" -ForegroundColor Yellow
Write-Host "Region: $region" -ForegroundColor Yellow
Write-Host ""

# Step 1: Install dependencies
Write-Host "[1/4] Installing dependencies..." -ForegroundColor Green
pip install -r requirements.txt -t . --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Step 2: Create ZIP file with ALL files
Write-Host "[2/4] Creating deployment package..." -ForegroundColor Green
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue
}

# Use 7zip or native PowerShell to include ALL files
# Get all items except test files, docs, scripts
$allItems = Get-ChildItem -Path . -Recurse | Where-Object {
    $fullPath = $_.FullName
    $name = $_.Name
    
    # Exclude patterns
    if ($name -like "test_*" -or 
        $name -like "*.md" -or 
        $name -like "*.ps1" -or 
        $name -like "*.sh" -or
        $name -like ".env" -or
        $name -like "*.log" -or
        $fullPath -like "*\.git\*" -or
        $fullPath -like "*\__pycache__\*") {
        return $false
    }
    return $true
}

# Create ZIP with all items
$allItems | Compress-Archive -DestinationPath $zipFile -Force
Write-Host "Created: $zipFile ($([math]::Round((Get-Item $zipFile).Length / 1MB, 2)) MB)" -ForegroundColor Green

# Step 3: Upload to Lambda
Write-Host "[3/4] Uploading to Lambda..." -ForegroundColor Green
aws lambda update-function-code `
    --function-name $functionName `
    --zip-file "fileb://$zipFile" `
    --region $region

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload to Lambda" -ForegroundColor Red
    exit 1
}

Write-Host "[4/4] Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Waiting for Lambda to update..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify handler: lambda_function.handler" -ForegroundColor Yellow
Write-Host "2. Test: python test_api_routes.py" -ForegroundColor Yellow
Write-Host "3. Check CloudWatch Logs if needed" -ForegroundColor Yellow

