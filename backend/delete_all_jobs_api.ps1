# Script to delete all jobs using API Gateway
# This will call the DELETE API for each job

$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Delete All Jobs from S3 and OpenSearch" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 0: Login to get token
Write-Host "[0/4] Logging in..." -ForegroundColor Yellow
try {
    $loginBody = @{
        username = "jeerasee@metrosystems.co.th"
        password = "Namwan2546."
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod -Uri "$apiUrl/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    $idToken = $loginResponse.idToken
    $headers = @{
        "Authorization" = "Bearer $idToken"
    }
    Write-Host "Login successful!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "ERROR: Failed to login: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 1: Get all jobs
Write-Host "[1/4] Getting list of all jobs..." -ForegroundColor Yellow
try {
    $jobsResponse = Invoke-RestMethod -Uri "$apiUrl/api/jobs/list" -Method GET -Headers $headers -ErrorAction Stop
    $jobs = $jobsResponse.jobs
    
    if ($null -eq $jobs -or $jobs.Count -eq 0) {
        Write-Host "No jobs found. Nothing to delete." -ForegroundColor Green
        exit 0
    }
    
    Write-Host "Found $($jobs.Count) job(s)" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "ERROR: Failed to get jobs list: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Delete each job
Write-Host "[2/4] Deleting jobs..." -ForegroundColor Yellow
$deletedCount = 0
$failedCount = 0
$errors = @()

foreach ($job in $jobs) {
    $jobId = $job.id
    $jobTitle = $job.title
    
    if ([string]::IsNullOrEmpty($jobId)) {
        Write-Host "  Skipping job without ID: $jobTitle" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "  Deleting: $jobTitle (ID: $jobId)" -ForegroundColor Gray
    
    try {
        $deleteResponse = Invoke-RestMethod -Uri "$apiUrl/api/jobs/$jobId" -Method DELETE -Headers $headers -ErrorAction Stop
        
        $opensearchDeleted = $deleteResponse.deleted_from_opensearch
        $s3Deleted = $deleteResponse.deleted_from_s3
        
        if ($opensearchDeleted -and $s3Deleted) {
            Write-Host "    [OK] Deleted from both S3 and OpenSearch" -ForegroundColor Green
            $deletedCount++
        } elseif ($opensearchDeleted -or $s3Deleted) {
            Write-Host "    [WARNING] Partially deleted (OpenSearch: $opensearchDeleted, S3: $s3Deleted)" -ForegroundColor Yellow
            $deletedCount++
        } else {
            Write-Host "    [ERROR] Failed to delete" -ForegroundColor Red
            $failedCount++
            $errors += "Job $jobId ($jobTitle): Failed to delete"
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 404) {
            Write-Host "    ⚠ Not found (may have been already deleted)" -ForegroundColor Yellow
        } else {
            Write-Host "    ✗ Error: $($_.Exception.Message)" -ForegroundColor Red
            $failedCount++
            $errors += "Job $jobId ($jobTitle): $($_.Exception.Message)"
        }
    }
}

# Step 3: Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[3/4] Summary" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Total jobs found: $($jobs.Count)" -ForegroundColor White
Write-Host "Successfully deleted: $deletedCount" -ForegroundColor Green
Write-Host "Failed: $failedCount" -ForegroundColor $(if ($failedCount -gt 0) { "Red" } else { "Green" })

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Errors:" -ForegroundColor Red
    foreach ($error in $errors) {
        Write-Host "  - $error" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "✅ All jobs deleted successfully!" -ForegroundColor Green
}

Write-Host "============================================================" -ForegroundColor Cyan
