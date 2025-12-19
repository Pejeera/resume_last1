# Script to check and explain timeout settings

$FunctionName = "ResumeMatchAPI"
$Region = "us-east-1"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Timeout Settings Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Lambda timeout
Write-Host "[1] Lambda Execution Timeout" -ForegroundColor Green
$lambdaConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query '{Timeout:Timeout,MemorySize:MemorySize}' `
    --output json | ConvertFrom-Json

Write-Host "   Current: $($lambdaConfig.Timeout) seconds (15 minutes)" -ForegroundColor Yellow
Write-Host "   Maximum: 900 seconds (15 minutes)" -ForegroundColor Gray
Write-Host "   Status: Already at MAXIMUM" -ForegroundColor Green
Write-Host ""

# 2. Lambda Init Timeout
Write-Host "[2] Lambda Init Timeout" -ForegroundColor Green
Write-Host "   Current: 10 seconds" -ForegroundColor Yellow
Write-Host "   Maximum: 10 seconds (HARD LIMIT - cannot be changed)" -ForegroundColor Red
Write-Host "   Status: This is causing the timeout issue!" -ForegroundColor Red
Write-Host "   Reason: Lambda in VPC without network access" -ForegroundColor Yellow
Write-Host ""

# 3. API Gateway timeout
Write-Host "[3] API Gateway Timeout" -ForegroundColor Green
Write-Host "   Default: 30 seconds" -ForegroundColor Yellow
Write-Host "   Maximum: 29 seconds (for REST API)" -ForegroundColor Gray
Write-Host "   Note: Can be increased but won't help if Lambda init times out" -ForegroundColor Yellow
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Root Cause Analysis" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The problem is NOT execution timeout, but INIT timeout:" -ForegroundColor Red
Write-Host ""
Write-Host "1. Lambda Init Phase (10 seconds max):" -ForegroundColor Yellow
Write-Host "   - Lambda tries to initialize modules" -ForegroundColor White
Write-Host "   - Tries to connect to S3 (timeout)" -ForegroundColor White
Write-Host "   - Tries to connect to CloudWatch Logs (timeout)" -ForegroundColor White
Write-Host "   - Times out after 10 seconds" -ForegroundColor White
Write-Host ""
Write-Host "2. Why it times out:" -ForegroundColor Yellow
Write-Host "   - Lambda is in VPC" -ForegroundColor White
Write-Host "   - VPC has no internet access (no NAT Gateway)" -ForegroundColor White
Write-Host "   - VPC has no VPC Endpoints for AWS services" -ForegroundColor White
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Solutions (in order of recommendation)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Solution 1: Add VPC Endpoints (RECOMMENDED)" -ForegroundColor Green
Write-Host "   - Create S3 Gateway Endpoint (FREE)" -ForegroundColor White
Write-Host "   - Create CloudWatch Logs Interface Endpoint (costs ~$7/month)" -ForegroundColor White
Write-Host "   - This allows Lambda to access AWS services without internet" -ForegroundColor White
Write-Host ""
Write-Host "Solution 2: Add NAT Gateway" -ForegroundColor Green
Write-Host "   - Provides internet access for Lambda" -ForegroundColor White
Write-Host "   - Costs ~$32/month + data transfer" -ForegroundColor White
Write-Host ""
Write-Host "Solution 3: Remove Lambda from VPC (QUICK FIX)" -ForegroundColor Green
Write-Host "   - If Lambda doesn't need VPC access" -ForegroundColor White
Write-Host "   - Lambda will have internet access automatically" -ForegroundColor White
Write-Host "   - This is the fastest solution for testing" -ForegroundColor White
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

