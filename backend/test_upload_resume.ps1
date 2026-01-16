# Test Resume Upload via API Gateway
# Usage: .\test_upload_resume.ps1 [-FilePath "path/to/resume.pdf"]

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
Write-Host "Test Resume Upload via API Gateway" -ForegroundColor Cyan
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
    Write-Host "   [TIP] Usage: .\test_upload_resume.ps1 -FilePath 'C:\path\to\resume.pdf'" -ForegroundColor Yellow
    Write-Host ""
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

Write-Host "[Step 3] Uploading resume..." -ForegroundColor Cyan
Write-Host "   File: $FilePath" -ForegroundColor Yellow
Write-Host "   Size: $((Get-Item $FilePath).Length) bytes" -ForegroundColor Yellow
Write-Host ""

try {
    # Prepare multipart form data
    $boundary = [System.Guid]::NewGuid().ToString()
    $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
    $fileName = Split-Path -Leaf $FilePath
    
    # Build multipart form data
    $bodyLines = @()
    $bodyLines += "--$boundary"
    $bodyLines += "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`""
    $bodyLines += "Content-Type: application/octet-stream"
    $bodyLines += ""
    $bodyLines += [System.Text.Encoding]::UTF8.GetString($fileBytes)
    $bodyLines += "--$boundary--"
    
    $bodyText = $bodyLines -join "`r`n"
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyText)
    
    # Headers
    $headers = @{
        "Authorization" = "Bearer $idToken"
        "Content-Type" = "multipart/form-data; boundary=$boundary"
    }
    
    # Upload using Invoke-WebRequest
    $response = Invoke-WebRequest -Uri "$ApiUrl/api/resumes/upload" -Method POST -Headers $headers -Body $bodyBytes -ErrorAction Stop
    
    Write-Host "   [OK] Upload successful!" -ForegroundColor Green
    Write-Host "   Status Code: $($response.StatusCode)" -ForegroundColor Yellow
    
    try {
        $responseJson = $response.Content | ConvertFrom-Json
        Write-Host ""
        Write-Host "   Response:" -ForegroundColor Cyan
        Write-Host "   - Resume ID: $($responseJson.resume_id)" -ForegroundColor White
        Write-Host "   - S3 URL: $($responseJson.s3_url)" -ForegroundColor White
        Write-Host "   - Name: $($responseJson.name)" -ForegroundColor White
        Write-Host "   - Created: $($responseJson.created_at)" -ForegroundColor White
        Write-Host ""
    } catch {
        Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "   [ERROR] Upload failed!" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "   Status Code: $statusCode" -ForegroundColor Red
        
        try {
            $errorStream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($errorStream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "   Response: $errorBody" -ForegroundColor Red
            
            try {
                $errorJson = $errorBody | ConvertFrom-Json
                Write-Host "   Detail: $($errorJson.detail)" -ForegroundColor Red
            } catch {
                # Not JSON
            }
        } catch {
            Write-Host "   Could not read error response" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "   [TROUBLESHOOTING]" -ForegroundColor Yellow
    Write-Host "   1. Check if API Gateway has CORS configured" -ForegroundColor Gray
    Write-Host "   2. Check if multipart/form-data is supported" -ForegroundColor Gray
    Write-Host "   3. Check Lambda function logs for errors" -ForegroundColor Gray
    Write-Host "   4. Try using curl command instead" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

