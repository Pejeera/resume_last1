<# 
Quick test script for Lambda function
Tests the deployed Lambda function by invoking it directly
#>

param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing Lambda Function" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region  : $Region" -ForegroundColor Yellow
Write-Host ""

# Test event for HTTP API v2 format (API Gateway)
$testEventObj = @{
    version = "2.0"
    routeKey = "GET /api/health"
    rawPath = "/api/health"
    rawQueryString = ""
    headers = @{
        accept = "application/json"
        "content-type" = "application/json"
    }
    requestContext = @{
        http = @{
            method = "GET"
            path = "/api/health"
            protocol = "HTTP/1.1"
            sourceIp = "127.0.0.1"
        }
        requestId = "test-request-$(Get-Date -Format 'yyyyMMddHHmmss')"
        routeKey = "GET /api/health"
        stage = "`$default"
        timeEpoch = [int64]((Get-Date).ToUniversalTime() - (Get-Date "1970-01-01")).TotalSeconds
    }
    isBase64Encoded = $false
}
# Convert to JSON string
$jsonContent = $testEventObj | ConvertTo-Json -Depth 10 -Compress

# Save to temporary file using .NET method (most reliable for UTF-8 without BOM)
$tempEventFile = "temp_lambda_event.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$bytes = $utf8NoBom.GetBytes($jsonContent)
[System.IO.File]::WriteAllBytes($tempEventFile, $bytes)

Write-Host "[1/2] Invoking Lambda function..." -ForegroundColor Green
Write-Host "Testing endpoint: GET /api/health" -ForegroundColor Gray
Write-Host ""

try {
    # Try using the existing test_event.json first, or use the temp file
    $eventFile = if (Test-Path "test_event.json") { "test_event.json" } else { $tempEventFile }
    
    # Use file:// prefix - AWS CLI on Windows should accept this format
    $fileUri = "file://$eventFile"
    
    Write-Host "Using event file: $eventFile" -ForegroundColor Gray
    Write-Host "File URI: $fileUri" -ForegroundColor Gray
    Write-Host ""
    
    $response = aws lambda invoke `
        --function-name $FunctionName `
        --region $Region `
        --payload $fileUri `
        --cli-binary-format raw-in-base64-out `
        response.json

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to invoke Lambda function." -ForegroundColor Red
        exit 1
    }

    # Read and parse response
    $responseContent = Get-Content response.json -Raw | ConvertFrom-Json
    
    Write-Host "[2/2] Response received!" -ForegroundColor Green
    Write-Host ""
    
    # Check if there's an error
    if ($responseContent.PSObject.Properties.Name -contains "errorMessage") {
        Write-Host "❌ Lambda Error:" -ForegroundColor Red
        Write-Host $responseContent.errorMessage -ForegroundColor Red
        if ($responseContent.PSObject.Properties.Name -contains "stackTrace") {
            Write-Host ""
            Write-Host "Stack Trace:" -ForegroundColor Yellow
            Write-Host $responseContent.stackTrace -ForegroundColor Yellow
        }
    } else {
        # Parse the response body
        $statusCode = $responseContent.statusCode
        $body = $responseContent.body | ConvertFrom-Json
        
        Write-Host "✅ Status Code: $statusCode" -ForegroundColor Green
        Write-Host ""
        Write-Host "Response Body:" -ForegroundColor Cyan
        $body | ConvertTo-Json -Depth 10 | Write-Host
        
        if ($statusCode -eq 200) {
            Write-Host ""
            Write-Host "✅ Lambda function is working correctly!" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "⚠️  Lambda returned status code: $statusCode" -ForegroundColor Yellow
        }
    }
    
    # Cleanup
    if (Test-Path response.json) {
        Remove-Item response.json -Force
    }
    
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    # Ensure cleanup even on error (only delete temp file, not test_event.json)
    if (Test-Path $tempEventFile) {
        Remove-Item $tempEventFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test completed!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

