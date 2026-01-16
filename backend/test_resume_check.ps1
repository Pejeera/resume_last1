# Test Resume Check via API Gateway
# Usage: .\test_resume_check.ps1

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
Write-Host "Resume Status Checker via API Gateway" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API URL: $ApiUrl" -ForegroundColor Yellow
Write-Host ""

# Step 1: Login to get JWT token
Write-Host "[Step 1] Logging in to get JWT token..." -ForegroundColor Cyan
try {
    $loginBody = @{
        username = $Username
        password = $Password
    } | ConvertTo-Json
    
    $loginResponse = Invoke-RestMethod -Uri "$ApiUrl/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    
    $idToken = $loginResponse.idToken
    Write-Host "   [OK] Login successful!" -ForegroundColor Green
    Write-Host "   Email: $($loginResponse.email)" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host "   [ERROR] Login failed!" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "   Status Code: $statusCode" -ForegroundColor Red
        
        try {
            $errorStream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($errorStream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "   Response: $errorBody" -ForegroundColor Red
        } catch {
            # Ignore error reading response
        }
    }
    Write-Host ""
    exit 1
}

# Step 2: List all resumes
Write-Host "[Step 2] Fetching list of all resumes..." -ForegroundColor Cyan
try {
    $headers = @{
        "Authorization" = "Bearer $idToken"
        "Content-Type" = "application/json"
    }
    
    $listResponse = Invoke-RestMethod -Uri "$ApiUrl/api/resumes/list" -Method GET -Headers $headers -ErrorAction Stop
    Write-Host "   [OK] Successfully retrieved resume list" -ForegroundColor Green
    
    $totalResumes = $listResponse.total
    $resumes = $listResponse.resumes
    
    Write-Host "   [INFO] Total resumes found: $totalResumes" -ForegroundColor Yellow
    Write-Host ""
    
    if ($totalResumes -eq 0) {
        Write-Host "   [WARNING] No resumes found in the system!" -ForegroundColor Red
        Write-Host ""
        Write-Host "   [TIP] To upload a resume:" -ForegroundColor Cyan
        Write-Host "      POST $ApiUrl/api/resumes/upload" -ForegroundColor Yellow
        Write-Host "      Content-Type: multipart/form-data" -ForegroundColor Yellow
        Write-Host "      Body: file=<resume-file>" -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }
    
    # Display resume list (first 10)
    Write-Host "   [LIST] Resume List (showing first 10):" -ForegroundColor Cyan
    Write-Host "   " + ("-" * 80) -ForegroundColor Gray
    $counter = 1
    $displayCount = [Math]::Min(10, $resumes.Count)
    foreach ($resume in $resumes[0..($displayCount-1)]) {
        $resumeId = $resume.resume_id
        $name = $resume.name
        $createdAt = $resume.created_at
        $s3Key = $resume.s3_key
        
        Write-Host "   [$counter] ID: $resumeId" -ForegroundColor White
        Write-Host "        Name: $name" -ForegroundColor Gray
        Write-Host "        Created: $createdAt" -ForegroundColor Gray
        if ($s3Key) {
            Write-Host "        S3 Key: $s3Key" -ForegroundColor Gray
        }
        Write-Host ""
        $counter++
    }
    if ($totalResumes -gt 10) {
        Write-Host "   ... and $($totalResumes - 10) more resumes" -ForegroundColor Gray
    }
    Write-Host "   " + ("-" * 80) -ForegroundColor Gray
    Write-Host ""
    
} catch {
    Write-Host "   [ERROR] Failed to list resumes" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    }
    Write-Host ""
    exit 1
}

# Step 3: Check the problematic resume ID from the error
$problematicId = "727c54c4-79d8-4d80-87e9-d8a5651f8557"
Write-Host "[Step 3] Checking problematic Resume ID from error: $problematicId" -ForegroundColor Cyan

$foundProblematic = $resumes | Where-Object { $_.resume_id -eq $problematicId }

if ($foundProblematic) {
    Write-Host "   [OK] Resume found in the list!" -ForegroundColor Green
    Write-Host "   Name: $($foundProblematic.name)" -ForegroundColor Yellow
    Write-Host "   Created: $($foundProblematic.created_at)" -ForegroundColor Yellow
    if ($foundProblematic.s3_key) {
        Write-Host "   S3 Key: $($foundProblematic.s3_key)" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "   [WARNING] Resume exists in S3 but search failed with 404." -ForegroundColor Yellow
    Write-Host "      This might mean:" -ForegroundColor Yellow
    Write-Host "      1. Resume is not indexed in OpenSearch" -ForegroundColor Gray
    Write-Host "      2. Resume processing failed" -ForegroundColor Gray
    Write-Host "      3. Resume data is incomplete" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   [TIP] Solutions:" -ForegroundColor Cyan
    Write-Host "      - Try re-uploading the resume to trigger re-processing" -ForegroundColor Yellow
    Write-Host "      - Check OpenSearch index to see if resume is indexed" -ForegroundColor Yellow
    Write-Host "      - Verify resume has text content for search" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "   [ERROR] Resume NOT found in the list!" -ForegroundColor Red
    Write-Host ""
    Write-Host "   [ANALYSIS] This resume ID does not exist in the system." -ForegroundColor Yellow
    Write-Host "      Possible reasons:" -ForegroundColor Yellow
    Write-Host "      1. Resume was never uploaded" -ForegroundColor Gray
    Write-Host "      2. Resume was deleted" -ForegroundColor Gray
    Write-Host "      3. Resume ID is incorrect" -ForegroundColor Gray
    Write-Host "      4. Resume is in different S3 bucket or prefix" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   [TIP] To upload a new resume:" -ForegroundColor Cyan
    Write-Host "      POST $ApiUrl/api/resumes/upload" -ForegroundColor Yellow
    Write-Host "      Authorization: Bearer $($idToken.Substring(0, 20))..." -ForegroundColor Yellow
    Write-Host "      Content-Type: multipart/form-data" -ForegroundColor Yellow
    Write-Host "      Body: file=<resume-file>" -ForegroundColor Yellow
    Write-Host ""
}

# Step 4: Try to search with the problematic resume ID
Write-Host "[Step 4] Testing search_by_resume endpoint with problematic ID..." -ForegroundColor Cyan
try {
    $searchBody = @{
        resume_id = $problematicId
    } | ConvertTo-Json
    
    $searchResponse = Invoke-RestMethod -Uri "$ApiUrl/api/jobs/search_by_resume" -Method POST -Body $searchBody -Headers $headers -ContentType "application/json" -ErrorAction Stop
    
    Write-Host "   [OK] Search successful!" -ForegroundColor Green
    Write-Host "   Found $($searchResponse.total) matching jobs" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   [ERROR] Search failed!" -ForegroundColor Red
    Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($statusCode -eq 404) {
        Write-Host ""
        Write-Host "   [CONFIRMED] 404 Error - Resume not found in S3 or OpenSearch" -ForegroundColor Yellow
        Write-Host "      This confirms the error you saw in the image." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "   [SOLUTION] You need to:" -ForegroundColor Cyan
        Write-Host "      1. Upload the resume first using /api/resumes/upload" -ForegroundColor Yellow
        Write-Host "      2. Wait for processing and indexing to complete" -ForegroundColor Yellow
        Write-Host "      3. Then try searching again" -ForegroundColor Yellow
    }
    
    try {
        $errorStream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($errorStream)
        $errorBody = $reader.ReadToEnd()
        $errorJson = $errorBody | ConvertFrom-Json
        Write-Host "   Response: $($errorJson.detail)" -ForegroundColor Red
    } catch {
        # Ignore error reading response
    }
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Check Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

