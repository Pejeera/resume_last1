# PowerShell script to deploy Lambda function
# Usage: .\deploy_lambda.ps1

$zipFile = "lambda-deployment.zip"

# Lambda function configuration
$functionName = "ResumeMatchAPI"
$region = "us-east-1"  # Found in us-east-1

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Lambda Function" -ForegroundColor Cyan
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

# Step 2: Create ZIP file
Write-Host "[2/4] Creating deployment package..." -ForegroundColor Green
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

# Include all necessary files and folders
# Exclude: test files, docs, scripts, cache, git
$excludeDirs = @("__pycache__", ".git", "test_*", "*.md", "*.ps1", "*.sh", ".env", "*.log")
$includeItems = @()

# Add app folder
if (Test-Path "app") {
    $includeItems += "app"
}

# Add Python files
Get-ChildItem -Path . -Filter "*.py" | ForEach-Object {
    if ($_.Name -notlike "test_*") {
        $includeItems += $_.FullName
    }
}

# Add requirements.txt
if (Test-Path "requirements.txt") {
    $includeItems += "requirements.txt"
}

# Add all installed packages (dependencies)
Get-ChildItem -Path . -Directory | Where-Object {
    $name = $_.Name
    $exclude = $false
    foreach ($pattern in $excludeDirs) {
        if ($name -like $pattern) {
            $exclude = $true
            break
        }
    }
    # Include packages (not test files, not app, not cache)
    return -not $exclude -and $name -ne "app" -and $name -notlike "test_*"
} | ForEach-Object {
    $includeItems += $_.FullName
}

# Create ZIP
Compress-Archive -Path $includeItems -DestinationPath $zipFile -Force
Write-Host "Created: $zipFile ($(Get-Item $zipFile | Select-Object -ExpandProperty Length) bytes)" -ForegroundColor Green

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
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Verify handler: lambda_function.handler" -ForegroundColor Yellow
Write-Host "2. Test endpoint: /api/health" -ForegroundColor Yellow
Write-Host "3. Check CloudWatch Logs if needed" -ForegroundColor Yellow

