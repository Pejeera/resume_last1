# Quick Deploy and Test Script
# This script deploys Lambda and tests the upload endpoint

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2"
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Quick Deploy and Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if deployment package exists
Write-Host "[Step 1] Checking deployment package..." -ForegroundColor Cyan
if (-not (Test-Path "lambda-deployment-clean.zip")) {
    Write-Host "   [WARNING] Deployment package not found!" -ForegroundColor Yellow
    Write-Host "   [ACTION] Running deployment script..." -ForegroundColor Yellow
    Write-Host ""
    
    if (Test-Path "deploy_lambda_clean.ps1") {
        & .\deploy_lambda_clean.ps1 -FunctionName $FunctionName -Region $Region
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   [ERROR] Deployment script failed!" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "   [ERROR] deploy_lambda_clean.ps1 not found!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "   [OK] Deployment package found" -ForegroundColor Green
}

Write-Host ""

# Step 2: Deploy to Lambda
Write-Host "[Step 2] Deploying to Lambda..." -ForegroundColor Cyan
try {
    $zipPath = Resolve-Path "lambda-deployment-clean.zip"
    Write-Host "   Uploading: $zipPath" -ForegroundColor Gray
    
    $updateResult = aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$zipPath" `
        --region $Region `
        2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Deployment successful!" -ForegroundColor Green
        
        # Wait for update to complete
        Write-Host "   Waiting for function update to complete..." -ForegroundColor Gray
        Start-Sleep -Seconds 5
        
        # Get function status
        $statusResult = aws lambda get-function --function-name $FunctionName --region $Region 2>&1 | ConvertFrom-Json
        Write-Host "   Function Status: $($statusResult.Configuration.State)" -ForegroundColor Yellow
        Write-Host "   Last Modified: $($statusResult.Configuration.LastModified)" -ForegroundColor Yellow
    } else {
        Write-Host "   [ERROR] Deployment failed!" -ForegroundColor Red
        Write-Host "   Error: $updateResult" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   [ERROR] Deployment error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Test login
Write-Host "[Step 3] Testing login..." -ForegroundColor Cyan
$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

try {
    $loginBody = @{
        username = "jeerasee@metrosystems.co.th"
        password = "Namwan2546."
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod -Uri "$apiUrl/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    $idToken = $loginResponse.idToken
    Write-Host "   [OK] Login successful!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   [ERROR] Login failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "   [TROUBLESHOOTING]" -ForegroundColor Yellow
    Write-Host "   - Check Lambda function logs in CloudWatch" -ForegroundColor Gray
    Write-Host "   - Verify Lambda function is updated" -ForegroundColor Gray
    Write-Host "   - Check API Gateway integration" -ForegroundColor Gray
    exit 1
}

# Step 4: Test upload (optional)
Write-Host "[Step 4] Testing upload endpoint (optional)..." -ForegroundColor Cyan
Write-Host "   To test upload, run:" -ForegroundColor Yellow
Write-Host "   .\test_upload_curl.ps1" -ForegroundColor White
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[NEXT STEPS]" -ForegroundColor Yellow
Write-Host "1. Test upload in Swagger UI" -ForegroundColor White
Write-Host "2. Check CloudWatch Logs if errors occur" -ForegroundColor White
Write-Host "3. Verify OpenSearch connection works" -ForegroundColor White
Write-Host ""

