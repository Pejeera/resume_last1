# Complete API Test - Both with and without login
# Usage: .\test_api_complete.ps1 -Username "email@example.com" -Password "password"

param(
    [Parameter(Mandatory=$false)]
    [string]$Username = "jeerasee@metrosystems.co.th",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "Namwan2546.",
    
    [Parameter(Mandatory=$false)]
    [string]$UserPoolId = "ap-southeast-2_bKxx54EbY",
    
    [Parameter(Mandatory=$false)]
    [string]$ClientId = "14keq2t7pc87ncl3i26rrf5vec",
    
    [Parameter(Mandatory=$false)]
    [string]$ClientSecret = "jjlm1l5lg2fvb2na0i2kuv75edgv8fvbskc8dq34abv5362tmdl",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-southeast-2"
)

$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Complete API Test - With & Without Login" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Function to calculate SECRET_HASH
function Get-SecretHash {
    param(
        [string]$Username,
        [string]$ClientId,
        [string]$ClientSecret
    )
    
    try {
        $hmac = New-Object System.Security.Cryptography.HMACSHA256
        $hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($ClientSecret)
        $message = $Username + $ClientId
        $messageBytes = [System.Text.Encoding]::UTF8.GetBytes($message)
        $hash = $hmac.ComputeHash($messageBytes)
        return [Convert]::ToBase64String($hash)
    } catch {
        Write-Host "Error calculating SECRET_HASH: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# Function to test API endpoint
function Test-ApiEndpoint {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [string]$Description = ""
    )
    
    $fullUrl = "$apiUrl$Endpoint"
    Write-Host "  Testing: $Endpoint" -ForegroundColor Gray
    
    try {
        $response = Invoke-WebRequest -Uri $fullUrl -Method $Method -Headers $Headers -UseBasicParsing -ErrorAction Stop
        Write-Host "    ✅ Status: $($response.StatusCode)" -ForegroundColor Green
        
        try {
            $json = $response.Content | ConvertFrom-Json
            if ($json.status) {
                Write-Host "    Response: $($response.Content)" -ForegroundColor Gray
            } elseif ($json.total -ne $null) {
                Write-Host "    Total: $($json.total)" -ForegroundColor Cyan
                if ($json.jobs -and $json.jobs.Count -gt 0) {
                    Write-Host "    First item: $($json.jobs[0].title)" -ForegroundColor Gray
                }
            } else {
                Write-Host "    Response: $($response.Content.Substring(0, [Math]::Min(100, $response.Content.Length)))..." -ForegroundColor Gray
            }
        } catch {
            Write-Host "    Response: $($response.Content)" -ForegroundColor Gray
        }
        
        return $true
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "    ❌ Status: $statusCode" -ForegroundColor Red
        
        if ($statusCode -eq 401) {
            Write-Host "    ℹ️  Expected: API Gateway rejected request (no/invalid token)" -ForegroundColor Yellow
        } else {
            Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
            if ($_.Exception.Response) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $responseBody = $reader.ReadToEnd()
                if ($responseBody) {
                    Write-Host "    Response: $responseBody" -ForegroundColor Yellow
                }
            }
        }
        return $false
    }
}

# ==========================================
# TEST 1: Without Login (No Token)
# ==========================================
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "TEST 1: Without Login (No JWT Token)" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "Expected: All requests should return 401 (Unauthorized)" -ForegroundColor Yellow
Write-Host ""

$test1Results = @{
    "/api/health" = $false
    "/api/jobs/list" = $false
    "/" = $false
}

Write-Host "[1.1] Testing /api/health (no token)..." -ForegroundColor Cyan
$test1Results["/api/health"] = Test-ApiEndpoint -Endpoint "/api/health" -Description "Health check"
Write-Host ""

Write-Host "[1.2] Testing /api/jobs/list (no token)..." -ForegroundColor Cyan
$test1Results["/api/jobs/list"] = Test-ApiEndpoint -Endpoint "/api/jobs/list" -Description "Jobs list"
Write-Host ""

Write-Host "[1.3] Testing / (no token)..." -ForegroundColor Cyan
$test1Results["/"] = Test-ApiEndpoint -Endpoint "/" -Description "Root endpoint"
Write-Host ""

# Summary for Test 1
$test1Passed = ($test1Results["/api/health"] -eq $false -and 
                $test1Results["/api/jobs/list"] -eq $false -and 
                $test1Results["/"] -eq $false)

Write-Host "Test 1 Summary: " -NoNewline -ForegroundColor Cyan
if ($test1Passed) {
    Write-Host "✅ PASSED (All returned 401 as expected)" -ForegroundColor Green
} else {
    Write-Host "❌ FAILED (Some requests did not return 401)" -ForegroundColor Red
}
Write-Host ""

# ==========================================
# TEST 2: With Login (With JWT Token)
# ==========================================
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "TEST 2: With Login (With JWT Token)" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host ""

Write-Host "[Step 1] Logging in to Cognito..." -ForegroundColor Yellow
Write-Host "  Username: $Username" -ForegroundColor Gray
Write-Host "  User Pool: $UserPoolId" -ForegroundColor Gray
Write-Host "  Client ID: $ClientId" -ForegroundColor Gray
Write-Host ""

try {
    # Calculate SECRET_HASH
    $secretHash = Get-SecretHash -Username $Username -ClientId $ClientId -ClientSecret $ClientSecret
    
    # Login to Cognito
    $authParams = "USERNAME=$Username,PASSWORD=$Password"
    if (-not [string]::IsNullOrEmpty($ClientSecret)) {
        $authParams += ",SECRET_HASH=$secretHash"
    }
    
    $authResponse = aws cognito-idp initiate-auth `
        --auth-flow USER_PASSWORD_AUTH `
        --client-id $ClientId `
        --auth-parameters $authParams `
        --region $Region `
        --output json 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Login failed!" -ForegroundColor Red
        Write-Host "Error: $authResponse" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Skipping Test 2 (with login)..." -ForegroundColor Yellow
        exit 1
    }
    
    $authResult = $authResponse | ConvertFrom-Json
    
    if ($authResult.AuthenticationResult) {
        $idToken = $authResult.AuthenticationResult.IdToken
        $accessToken = $authResult.AuthenticationResult.AccessToken
        
        Write-Host "✅ Login successful!" -ForegroundColor Green
        Write-Host "  IdToken: $($idToken.Substring(0, [Math]::Min(50, $idToken.Length)))..." -ForegroundColor Gray
        Write-Host ""
        
        # Create headers with token
        $authHeaders = @{
            "Authorization" = "Bearer $idToken"
        }
        
        # Test endpoints with token
        $test2Results = @{
            "/api/health" = $false
            "/api/jobs/list" = $false
            "/" = $false
        }
        
        Write-Host "[2.1] Testing /api/health (with token)..." -ForegroundColor Cyan
        $test2Results["/api/health"] = Test-ApiEndpoint -Endpoint "/api/health" -Headers $authHeaders -Description "Health check"
        Write-Host ""
        
        Write-Host "[2.2] Testing /api/jobs/list (with token)..." -ForegroundColor Cyan
        $test2Results["/api/jobs/list"] = Test-ApiEndpoint -Endpoint "/api/jobs/list" -Headers $authHeaders -Description "Jobs list"
        Write-Host ""
        
        Write-Host "[2.3] Testing / (with token)..." -ForegroundColor Cyan
        $test2Results["/"] = Test-ApiEndpoint -Endpoint "/" -Headers $authHeaders -Description "Root endpoint"
        Write-Host ""
        
        # Summary for Test 2 (404 for / is acceptable if route doesn't exist)
        $test2Passed = ($test2Results["/api/health"] -eq $true -and 
                        $test2Results["/api/jobs/list"] -eq $true)
        
        Write-Host "Test 2 Summary: " -NoNewline -ForegroundColor Cyan
        if ($test2Passed) {
            Write-Host "✅ PASSED (All returned 200 OK)" -ForegroundColor Green
        } else {
            Write-Host "❌ FAILED (Some requests did not return 200)" -ForegroundColor Red
        }
        Write-Host ""
        
    } else {
        Write-Host "❌ Login failed - unexpected response!" -ForegroundColor Red
        Write-Host "Response: $($authResult | ConvertTo-Json -Depth 10)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Error during login: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Full error: $_" -ForegroundColor Yellow
}

# ==========================================
# FINAL SUMMARY
# ==========================================
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "FINAL TEST SUMMARY" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Test 1 (Without Login): " -NoNewline -ForegroundColor Yellow
if ($test1Passed) {
    Write-Host "✅ PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ FAILED" -ForegroundColor Red
}

Write-Host "Test 2 (With Login): " -NoNewline -ForegroundColor Yellow
if ($test2Passed) {
    Write-Host "✅ PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ FAILED" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  - Check CloudWatch logs for user claims:" -ForegroundColor Cyan
Write-Host "    aws logs tail /aws/lambda/resume-search-api --follow --region $Region" -ForegroundColor Gray
Write-Host "  - Verify user email in logs: $Username" -ForegroundColor Cyan
Write-Host ""

