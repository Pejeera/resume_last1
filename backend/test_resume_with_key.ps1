# Test Resume Search with resume_key (s3_key)
# Usage: .\test_resume_with_key.ps1

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com",
    
    [Parameter(Mandatory=$false)]
    [string]$Username = "jeerasee@metrosystems.co.th",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "Namwan2546."
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Resume Search with resume_key" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Login
Write-Host "[Step 1] Logging in..." -ForegroundColor Cyan
try {
    $loginBody = @{
        username = $Username
        password = $Password
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod -Uri "$ApiUrl/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    $idToken = $loginResponse.idToken
    Write-Host "   [OK] Login successful!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   [ERROR] Login failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Get resume list to get s3_key
Write-Host "[Step 2] Getting resume list..." -ForegroundColor Cyan
try {
    $headers = @{
        "Authorization" = "Bearer $idToken"
        "Content-Type" = "application/json"
    }
    
    $listResponse = Invoke-RestMethod -Uri "$ApiUrl/api/resumes/list" -Method GET -Headers $headers -ErrorAction Stop
    $resumes = $listResponse.resumes
    
    $targetResume = $resumes | Where-Object { $_.resume_id -eq "727c54c4-79d8-4d80-87e9-d8a5651f8557" }
    
    if (-not $targetResume) {
        Write-Host "   [ERROR] Resume not found in list!" -ForegroundColor Red
        exit 1
    }
    
    $s3Key = $targetResume.s3_key
    Write-Host "   [OK] Found resume!" -ForegroundColor Green
    Write-Host "   Resume ID: $($targetResume.resume_id)" -ForegroundColor Yellow
    Write-Host "   S3 Key: $s3Key" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host "   [ERROR] Failed to get resume list: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Test search with resume_id
Write-Host "[Step 3] Testing search with resume_id..." -ForegroundColor Cyan
try {
    $searchBody = @{
        resume_id = "727c54c4-79d8-4d80-87e9-d8a5651f8557"
    } | ConvertTo-Json
    
    $searchResponse = Invoke-RestMethod -Uri "$ApiUrl/api/jobs/search_by_resume" -Method POST -Body $searchBody -Headers $headers -ContentType "application/json" -ErrorAction Stop
    
    Write-Host "   [OK] Search successful with resume_id!" -ForegroundColor Green
    Write-Host "   Found $($searchResponse.total) matching jobs" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   [ERROR] Search failed with resume_id!" -ForegroundColor Red
    Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    
    try {
        $errorStream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($errorStream)
        $errorBody = $reader.ReadToEnd()
        $errorJson = $errorBody | ConvertFrom-Json
        Write-Host "   Response: $($errorJson.detail)" -ForegroundColor Red
    } catch {
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

# Step 4: Test search with resume_key (s3_key)
Write-Host "[Step 4] Testing search with resume_key (s3_key)..." -ForegroundColor Cyan
try {
    $searchBody = @{
        resume_key = $s3Key
        resume_id = "727c54c4-79d8-4d80-87e9-d8a5651f8557"  # Also provide resume_id for reference
    } | ConvertTo-Json
    
    $searchResponse = Invoke-RestMethod -Uri "$ApiUrl/api/jobs/search_by_resume" -Method POST -Body $searchBody -Headers $headers -ContentType "application/json" -ErrorAction Stop
    
    Write-Host "   [OK] Search successful with resume_key!" -ForegroundColor Green
    Write-Host "   Found $($searchResponse.total) matching jobs" -ForegroundColor Yellow
    Write-Host ""
    
    if ($searchResponse.results -and $searchResponse.results.Count -gt 0) {
        Write-Host "   Top 3 matching jobs:" -ForegroundColor Cyan
        $top3 = $searchResponse.results[0..([Math]::Min(2, $searchResponse.results.Count - 1))]
        foreach ($job in $top3) {
            Write-Host "   - $($job.title) (Score: $($job.score))" -ForegroundColor White
        }
    }
    Write-Host ""
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   [ERROR] Search failed with resume_key!" -ForegroundColor Red
    Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    
    try {
        $errorStream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($errorStream)
        $errorBody = $reader.ReadToEnd()
        $errorJson = $errorBody | ConvertFrom-Json
        Write-Host "   Response: $($errorJson.detail)" -ForegroundColor Red
    } catch {
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

