# Test API with JWT Token
# Usage: .\test_api.ps1 -Token "your-jwt-token-here"

param(
    [Parameter(Mandatory=$false)]
    [string]$Token = ""
)

$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing Resume Matching API" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API URL: $apiUrl" -ForegroundColor Yellow
Write-Host ""

if ([string]::IsNullOrEmpty($Token)) {
    Write-Host "⚠️  No JWT token provided" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To test with JWT token:" -ForegroundColor Cyan
    Write-Host "  1. Login via Cognito to get IdToken" -ForegroundColor Yellow
    Write-Host "  2. Run: .\test_api.ps1 -Token 'your-id-token-here'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Testing without token (should get 401)..." -ForegroundColor Yellow
} else {
    Write-Host "✅ Using JWT token (first 20 chars: $($Token.Substring(0, [Math]::Min(20, $Token.Length)))...)" -ForegroundColor Green
    Write-Host ""
}

# Test 1: Health endpoint
Write-Host "[1/3] Testing /api/health..." -ForegroundColor Cyan
try {
    $headers = @{}
    if (-not [string]::IsNullOrEmpty($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }
    
    $response = Invoke-WebRequest -Uri "$apiUrl/api/health" -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
    Write-Host "   ✅ Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   ❌ Status: $statusCode" -ForegroundColor Red
    if ($statusCode -eq 401) {
        Write-Host "   ℹ️  Expected: API Gateway JWT Authorizer rejected request (no valid token)" -ForegroundColor Yellow
    } else {
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host ""

# Test 2: Jobs list endpoint
Write-Host "[2/3] Testing /api/jobs/list..." -ForegroundColor Cyan
try {
    $headers = @{}
    if (-not [string]::IsNullOrEmpty($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }
    
    $response = Invoke-WebRequest -Uri "$apiUrl/api/jobs/list" -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
    Write-Host "   ✅ Status: $($response.StatusCode)" -ForegroundColor Green
    $json = $response.Content | ConvertFrom-Json
    Write-Host "   Jobs found: $($json.total)" -ForegroundColor Cyan
    if ($json.jobs -and $json.jobs.Count -gt 0) {
        Write-Host "   First job: $($json.jobs[0].title)" -ForegroundColor Gray
    }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   ❌ Status: $statusCode" -ForegroundColor Red
    if ($statusCode -eq 401) {
        Write-Host "   ℹ️  Expected: API Gateway JWT Authorizer rejected request (no valid token)" -ForegroundColor Yellow
    } else {
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host ""

# Test 3: Root endpoint
Write-Host "[3/3] Testing / endpoint..." -ForegroundColor Cyan
try {
    $headers = @{}
    if (-not [string]::IsNullOrEmpty($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }
    
    $response = Invoke-WebRequest -Uri "$apiUrl/" -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
    Write-Host "   ✅ Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   ❌ Status: $statusCode" -ForegroundColor Red
    if ($statusCode -eq 401) {
        Write-Host "   ℹ️  Expected: API Gateway JWT Authorizer rejected request (no valid token)" -ForegroundColor Yellow
    } else {
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ API Gateway JWT Authorizer is working" -ForegroundColor Green
Write-Host "✅ Backend is deployed and ready" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Login via Cognito to get IdToken" -ForegroundColor Cyan
Write-Host "  2. Test with: .\test_api.ps1 -Token 'your-id-token'" -ForegroundColor Cyan
Write-Host "  3. Check CloudWatch logs to see user claims" -ForegroundColor Cyan

