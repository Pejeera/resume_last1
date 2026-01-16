# Test Lambda Function Directly
# This helps identify if the issue is with Lambda or API Gateway

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Direct Lambda Function Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health check endpoint
Write-Host "[Test 1] Testing health endpoint..." -ForegroundColor Cyan

$healthEvent = @{
    version = "2.0"
    routeKey = "GET /api/health"
    rawPath = "/api/health"
    rawQueryString = ""
    headers = @{
        "accept" = "application/json"
        "content-type" = "application/json"
    }
    requestContext = @{
        http = @{
            method = "GET"
            path = "/api/health"
        }
        accountId = "123456789012"
        apiId = "test"
        requestId = "test-request-id"
        time = "01/Jan/2024:00:00:00 +0000"
        timeEpoch = 1704067200
    }
} | ConvertTo-Json -Depth 10

try {
    $response = aws lambda invoke `
        --function-name $FunctionName `
        --region $Region `
        --payload $healthEvent `
        --cli-binary-format raw-in-base64-out `
        response.json `
        2>&1
    
    if ($LASTEXITCODE -eq 0) {
        $result = Get-Content response.json | ConvertFrom-Json
        Write-Host "   [OK] Lambda invoked successfully" -ForegroundColor Green
        Write-Host "   Response:" -ForegroundColor Cyan
        Write-Host ($result | ConvertTo-Json -Depth 5) -ForegroundColor White
        
        # Check for errors in response
        if ($result.errorMessage) {
            Write-Host ""
            Write-Host "   [ERROR] Lambda error:" -ForegroundColor Red
            Write-Host "   $($result.errorMessage)" -ForegroundColor Red
            if ($result.stackTrace) {
                Write-Host "   Stack trace:" -ForegroundColor Red
                Write-Host $result.stackTrace -ForegroundColor Red
            }
        }
    } else {
        Write-Host "   [ERROR] Failed to invoke Lambda" -ForegroundColor Red
        Write-Host "   $response" -ForegroundColor Red
    }
} catch {
    Write-Host "   [ERROR] Exception: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# Cleanup
if (Test-Path "response.json") {
    Remove-Item "response.json" -Force
}

Write-Host "==========================================" -ForegroundColor Cyan

