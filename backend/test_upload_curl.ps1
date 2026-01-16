# Test Resume Upload using curl (more reliable for multipart/form-data)
# Usage: .\test_upload_curl.ps1 [-FilePath "path/to/resume.pdf"]

param(
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com",
    
    [Parameter(Mandatory=$false)]
    [string]$Username = "jeerasee@metrosystems.co.th",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "Namwan2546.",
    
    [Parameter(Mandatory=$false)]
    [string]$FilePath = ""
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Resume Upload using curl" -ForegroundColor Cyan
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

# Step 2: Check if file path provided
if ([string]::IsNullOrEmpty($FilePath)) {
    Write-Host "[Step 2] No file path provided" -ForegroundColor Yellow
    Write-Host "   Creating a test file for upload..." -ForegroundColor Cyan
    
    # Create a test text file
    $testContent = @"
Test Resume Content
Name: Test User
Email: test@example.com
Skills: Python, FastAPI, AWS
Experience: 5 years in software development
"@
    
    $testFilePath = "$env:TEMP\test_resume_upload_$(Get-Date -Format 'yyyyMMddHHmmss').txt"
    $testContent | Out-File -FilePath $testFilePath -Encoding UTF8
    $FilePath = $testFilePath
    Write-Host "   Created test file: $FilePath" -ForegroundColor Green
    Write-Host ""
}

# Check if file exists
if (-not (Test-Path $FilePath)) {
    Write-Host "   [ERROR] File not found: $FilePath" -ForegroundColor Red
    exit 1
}

# Check if curl is available
$curlCmd = Get-Command curl -ErrorAction SilentlyContinue
if (-not $curlCmd) {
    Write-Host "   [ERROR] curl command not found!" -ForegroundColor Red
    Write-Host "   Please install curl or use test_upload_resume.ps1 instead" -ForegroundColor Yellow
    exit 1
}

Write-Host "[Step 3] Uploading resume using curl..." -ForegroundColor Cyan
Write-Host "   File: $FilePath" -ForegroundColor Yellow
Write-Host "   Size: $((Get-Item $FilePath).Length) bytes" -ForegroundColor Yellow
Write-Host ""

try {
    $fileName = Split-Path -Leaf $FilePath
    $uploadUrl = "$ApiUrl/api/resumes/upload"
    
    # Build curl command
    $curlArgs = @(
        "-X", "POST",
        $uploadUrl,
        "-H", "Authorization: Bearer $idToken",
        "-H", "Accept: application/json",
        "-F", "file=@`"$FilePath`";type=application/octet-stream"
    )
    
    Write-Host "   Executing curl command..." -ForegroundColor Gray
    Write-Host "   Command: curl -X POST $uploadUrl -H 'Authorization: Bearer ...' -F 'file=@$fileName'" -ForegroundColor Gray
    Write-Host ""
    
    # Execute curl
    $response = & curl @curlArgs 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Upload successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "   Response:" -ForegroundColor Cyan
        Write-Host $response -ForegroundColor White
        Write-Host ""
        
        try {
            $responseJson = $response | ConvertFrom-Json
            Write-Host "   Parsed Response:" -ForegroundColor Cyan
            Write-Host "   - Resume ID: $($responseJson.resume_id)" -ForegroundColor White
            Write-Host "   - S3 URL: $($responseJson.s3_url)" -ForegroundColor White
            Write-Host "   - Name: $($responseJson.name)" -ForegroundColor White
            Write-Host "   - Created: $($responseJson.created_at)" -ForegroundColor White
        } catch {
            # Not JSON or already displayed
        }
    } else {
        Write-Host "   [ERROR] Upload failed!" -ForegroundColor Red
        Write-Host "   Exit Code: $LASTEXITCODE" -ForegroundColor Red
        Write-Host "   Response: $response" -ForegroundColor Red
        Write-Host ""
        Write-Host "   [TROUBLESHOOTING]" -ForegroundColor Yellow
        Write-Host "   1. Check API Gateway CORS configuration" -ForegroundColor Gray
        Write-Host "   2. Check Lambda function logs" -ForegroundColor Gray
        Write-Host "   3. Verify JWT token is valid" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "   [ERROR] Upload failed!" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

