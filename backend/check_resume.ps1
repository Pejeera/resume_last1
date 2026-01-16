# Check Resume Status
# Usage: .\check_resume.ps1 [-ResumeId "resume-id-here"] [-ApiUrl "api-url"]
# If ResumeId is not provided, will list all resumes

param(
    [Parameter(Mandatory=$false)]
    [string]$ResumeId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com",
    
    [Parameter(Mandatory=$false)]
    [string]$Token = ""
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Resume Status Checker" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API URL: $ApiUrl" -ForegroundColor Yellow
Write-Host ""

# Prepare headers
$headers = @{
    "Content-Type" = "application/json"
}
if (-not [string]::IsNullOrEmpty($Token)) {
    $headers["Authorization"] = "Bearer $Token"
    Write-Host "[OK] Using JWT token" -ForegroundColor Green
} else {
    Write-Host "[WARNING] No JWT token provided (may fail if API requires auth)" -ForegroundColor Yellow
}
Write-Host ""

# Step 1: List all resumes
Write-Host "[Step 1] Fetching list of all resumes..." -ForegroundColor Cyan
try {
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
    
    # Display resume list
    Write-Host "   [LIST] Resume List:" -ForegroundColor Cyan
    Write-Host "   " + ("-" * 80) -ForegroundColor Gray
    $counter = 1
    foreach ($resume in $resumes) {
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
    Write-Host "   " + ("-" * 80) -ForegroundColor Gray
    Write-Host ""
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "   [ERROR] Failed to list resumes" -ForegroundColor Red
    Write-Host "   Status Code: $statusCode" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($statusCode -eq 401) {
        Write-Host ""
        Write-Host "   [TIP] This API requires authentication. Please provide a JWT token:" -ForegroundColor Yellow
        Write-Host "      .\check_resume.ps1 -Token 'your-jwt-token'" -ForegroundColor Yellow
    }
    Write-Host ""
    exit 1
}

# Step 2: Check specific resume ID if provided
if (-not [string]::IsNullOrEmpty($ResumeId)) {
    Write-Host "[Step 2] Checking specific Resume ID: $ResumeId" -ForegroundColor Cyan
    
    # Check if resume exists in the list
    $foundResume = $resumes | Where-Object { $_.resume_id -eq $ResumeId }
    
    if ($foundResume) {
        Write-Host "   [OK] Resume found in the list!" -ForegroundColor Green
        Write-Host "   Name: $($foundResume.name)" -ForegroundColor Yellow
        Write-Host "   Created: $($foundResume.created_at)" -ForegroundColor Yellow
        if ($foundResume.s3_key) {
            Write-Host "   S3 Key: $($foundResume.s3_key)" -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "   [TIP] This resume exists in S3. If you're getting 404 errors," -ForegroundColor Cyan
        Write-Host "      it might not be indexed in OpenSearch yet." -ForegroundColor Cyan
        Write-Host "      Try re-uploading or wait for indexing to complete." -ForegroundColor Cyan
    } else {
        Write-Host "   [ERROR] Resume NOT found in the list!" -ForegroundColor Red
        Write-Host ""
        Write-Host "   [TIP] This resume ID does not exist in the system." -ForegroundColor Yellow
        Write-Host "      Possible reasons:" -ForegroundColor Yellow
        Write-Host "      1. Resume was never uploaded" -ForegroundColor Gray
        Write-Host "      2. Resume was deleted" -ForegroundColor Gray
        Write-Host "      3. Resume ID is incorrect" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   [TIP] To upload a new resume:" -ForegroundColor Cyan
        Write-Host "      POST $ApiUrl/api/resumes/upload" -ForegroundColor Yellow
        Write-Host "      Content-Type: multipart/form-data" -ForegroundColor Yellow
        Write-Host "      Body: file=<resume-file>" -ForegroundColor Yellow
        Write-Host ""
    }
} else {
    Write-Host "[Step 2] No specific Resume ID provided" -ForegroundColor Cyan
    Write-Host "   [TIP] To check a specific resume, use:" -ForegroundColor Yellow
    Write-Host "      .\check_resume.ps1 -ResumeId 'resume-id-here'" -ForegroundColor Yellow
    Write-Host ""
}

# Step 3: Check the problematic resume ID from the error
$problematicId = "727c54c4-79d8-4d80-87e9-d8a5651f8557"
if ($ResumeId -ne $problematicId) {
    Write-Host "[Step 3] Checking problematic Resume ID from error: $problematicId" -ForegroundColor Cyan
    
    $foundProblematic = $resumes | Where-Object { $_.resume_id -eq $problematicId }
    
    if ($foundProblematic) {
        Write-Host "   [OK] Resume found!" -ForegroundColor Green
        Write-Host "   Name: $($foundProblematic.name)" -ForegroundColor Yellow
        Write-Host "   Created: $($foundProblematic.created_at)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "   [WARNING] Resume exists in S3 but search failed." -ForegroundColor Yellow
        Write-Host "      This might mean:" -ForegroundColor Yellow
        Write-Host "      1. Resume is not indexed in OpenSearch" -ForegroundColor Gray
        Write-Host "      2. Resume processing failed" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   [TIP] Try re-uploading the resume to trigger re-processing:" -ForegroundColor Cyan
        Write-Host "      POST $ApiUrl/api/resumes/upload" -ForegroundColor Yellow
    } else {
        Write-Host "   [ERROR] Resume NOT found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "   [TIP] This resume ID does not exist. You need to upload it first:" -ForegroundColor Yellow
        Write-Host "      POST $ApiUrl/api/resumes/upload" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Check Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

