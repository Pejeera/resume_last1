# Test API with Cognito Login
# Usage: .\test_api_with_login.ps1 -Username "email@example.com" -Password "password" -UserPoolId "pool-id" -ClientId "client-id" -ClientSecret "secret"

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,
    
    [Parameter(Mandatory=$true)]
    [string]$Password,
    
    [Parameter(Mandatory=$false)]
    [string]$UserPoolId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ClientId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ClientSecret = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-southeast-2"
)

$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing API with Cognito Login" -ForegroundColor Cyan
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

# Step 1: Find User Pool if not provided
if ([string]::IsNullOrEmpty($UserPoolId) -or [string]::IsNullOrEmpty($ClientId)) {
    Write-Host "[Step 1] Finding Cognito User Pool..." -ForegroundColor Yellow
    
    try {
        $pools = aws cognito-idp list-user-pools --max-results 20 --region $Region --output json | ConvertFrom-Json
        if ($pools.UserPools.Count -eq 0) {
            Write-Host "❌ No Cognito User Pools found!" -ForegroundColor Red
            exit 1
        }
        
        $selectedPool = $pools.UserPools[0]
        $UserPoolId = $selectedPool.Id
        Write-Host "Using User Pool: $($selectedPool.Name) ($UserPoolId)" -ForegroundColor Green
        
        # Find Client ID
        Write-Host ""
        Write-Host "[Step 1.1] Finding Cognito User Pool Client..." -ForegroundColor Yellow
        $clients = aws cognito-idp list-user-pool-clients --user-pool-id $UserPoolId --region $Region --output json | ConvertFrom-Json
        if ($clients.UserPoolClients.Count -eq 0) {
            Write-Host "❌ No clients found in User Pool!" -ForegroundColor Red
            exit 1
        }
        
        $ClientId = $clients.UserPoolClients[0].ClientId
        Write-Host "Using Client ID: $ClientId" -ForegroundColor Green
        
        # Try to get client secret
        Write-Host ""
        Write-Host "[Step 1.2] Getting Client Secret..." -ForegroundColor Yellow
        try {
            $clientInfo = aws cognito-idp describe-user-pool-client --user-pool-id $UserPoolId --client-id $ClientId --region $Region --output json | ConvertFrom-Json
            if ($clientInfo.UserPoolClient.ClientSecret) {
                $ClientSecret = $clientInfo.UserPoolClient.ClientSecret
                Write-Host "✅ Found Client Secret" -ForegroundColor Green
            } else {
                Write-Host "⚠️  Client does not have a secret (public client)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠️  Could not get client secret: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "❌ Error finding User Pool: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[Step 2] Logging in to Cognito..." -ForegroundColor Yellow
Write-Host "  Username: $Username" -ForegroundColor Gray
Write-Host "  User Pool: $UserPoolId" -ForegroundColor Gray
Write-Host "  Client ID: $ClientId" -ForegroundColor Gray
Write-Host ""

try {
    # Build auth parameters
    $authParams = "USERNAME=$Username,PASSWORD=$Password"
    
    # Add SECRET_HASH if client secret is provided
    if (-not [string]::IsNullOrEmpty($ClientSecret)) {
        $secretHash = Get-SecretHash -Username $Username -ClientId $ClientId -ClientSecret $ClientSecret
        $authParams += ",SECRET_HASH=$secretHash"
        Write-Host "  Using SECRET_HASH (confidential client)" -ForegroundColor Gray
    } else {
        Write-Host "  Using public client (no secret)" -ForegroundColor Gray
    }
    Write-Host ""
    
    # Login to Cognito
    $authResponse = aws cognito-idp initiate-auth `
        --auth-flow USER_PASSWORD_AUTH `
        --client-id $ClientId `
        --auth-parameters $authParams `
        --region $Region `
        --output json 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Login failed!" -ForegroundColor Red
        Write-Host "Error: $authResponse" -ForegroundColor Yellow
        
        # Check if it's a challenge (like NEW_PASSWORD_REQUIRED)
        if ($authResponse -match "NEW_PASSWORD_REQUIRED") {
            Write-Host ""
            Write-Host "ℹ️  User needs to set a new password (NEW_PASSWORD_REQUIRED challenge)" -ForegroundColor Yellow
            Write-Host "Please login via Cognito console or use AWS CLI to set new password" -ForegroundColor Cyan
        }
        exit 1
    }
    
    $authResult = $authResponse | ConvertFrom-Json
    
    if ($authResult.AuthenticationResult) {
        $idToken = $authResult.AuthenticationResult.IdToken
        $accessToken = $authResult.AuthenticationResult.AccessToken
        
        Write-Host "✅ Login successful!" -ForegroundColor Green
        Write-Host "  IdToken: $($idToken.Substring(0, [Math]::Min(50, $idToken.Length)))..." -ForegroundColor Gray
        Write-Host ""
        
        # Step 3: Test API with token
        Write-Host "[Step 3] Testing API with JWT token..." -ForegroundColor Yellow
        Write-Host ""
        
        # Test Health endpoint
        Write-Host "[3.1] Testing /api/health..." -ForegroundColor Cyan
        try {
            $headers = @{
                "Authorization" = "Bearer $idToken"
            }
            $response = Invoke-WebRequest -Uri "$apiUrl/api/health" -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
            Write-Host "   ✅ Status: $($response.StatusCode)" -ForegroundColor Green
            Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
        } catch {
            $statusCode = $_.Exception.Response.StatusCode.value__
            Write-Host "   ❌ Status: $statusCode" -ForegroundColor Red
            Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
        }
        Write-Host ""
        
        # Test Jobs list endpoint
        Write-Host "[3.2] Testing /api/jobs/list..." -ForegroundColor Cyan
        try {
            $headers = @{
                "Authorization" = "Bearer $idToken"
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
            Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
            if ($_.Exception.Response) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $responseBody = $reader.ReadToEnd()
                Write-Host "   Response: $responseBody" -ForegroundColor Yellow
            }
        }
        Write-Host ""
        
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host "✅ Test Complete!" -ForegroundColor Green
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "  - Check CloudWatch logs to see user claims:" -ForegroundColor Cyan
        Write-Host "    aws logs tail /aws/lambda/resume-search-api --follow --region $Region" -ForegroundColor Gray
        
    } elseif ($authResult.ChallengeName) {
        Write-Host "⚠️  Authentication challenge required: $($authResult.ChallengeName)" -ForegroundColor Yellow
        Write-Host "Response: $($authResult | ConvertTo-Json -Depth 10)" -ForegroundColor Gray
    } else {
        Write-Host "❌ Login failed - unexpected response!" -ForegroundColor Red
        Write-Host "Response: $($authResult | ConvertTo-Json -Depth 10)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Error during login: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Full error: $_" -ForegroundColor Yellow
    exit 1
}
