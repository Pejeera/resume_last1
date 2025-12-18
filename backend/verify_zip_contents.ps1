<#
ตรวจสอบเนื้อหาใน zip file ว่ามีไฟล์ต้องห้ามหรือไม่
รันหลังจากสร้าง zip แล้ว
#>

param(
    [string]$ZipFile = "lambda-deployment-clean.zip"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Verifying ZIP Contents" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ZipFile)) {
    Write-Host "ERROR: Zip file not found: $ZipFile" -ForegroundColor Red
    exit 1
}

Write-Host "Extracting zip to temporary directory..." -ForegroundColor Green
$tempDir = Join-Path $env:TEMP ("lambda_zip_check_" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tempDir -Force -ErrorAction SilentlyContinue | Out-Null

try {
    # Expand-Archive with error handling for permission issues
    try {
        Expand-Archive -Path $ZipFile -DestinationPath $tempDir -Force -ErrorAction Stop
    } catch {
        Write-Host "⚠️  Expand-Archive failed (possibly permission issue), retrying with new temp dir..." -ForegroundColor Yellow
        # Clean up old temp dir (safe - check exists first)
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        # Create new temp dir with GUID
        $tempDir = Join-Path $env:TEMP ("lambda_zip_check_" + [guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $tempDir -Force -ErrorAction SilentlyContinue | Out-Null
        Expand-Archive -Path $ZipFile -DestinationPath $tempDir -Force -ErrorAction Stop
    }
    
    Write-Host "Checking for forbidden files at root level..." -ForegroundColor Green
    $forbiddenFiles = @("http.py", "typing.py")
    $foundIssues = $false
    
    foreach ($f in $forbiddenFiles) {
        $path = Join-Path $tempDir $f
        if (Test-Path $path) {
            Write-Host "  ❌ FOUND: $f at root level!" -ForegroundColor Red
            Write-Host "     Full path: $path" -ForegroundColor Red
            $foundIssues = $true
        }
    }
    
    if (-not $foundIssues) {
        Write-Host "  ✅ No forbidden files at root level" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "Root level files:" -ForegroundColor Cyan
    Get-ChildItem -Path $tempDir -File -ErrorAction SilentlyContinue | Select-Object Name | Format-Table -AutoSize
    
    Write-Host ""
    Write-Host "Checking app/ directory..." -ForegroundColor Green
    $appDir = Join-Path $tempDir "app"
    if (Test-Path $appDir) {
        foreach ($f in $forbiddenFiles) {
            $found = Get-ChildItem -Path $appDir -Recurse -Filter $f -ErrorAction SilentlyContinue
            if ($found) {
                Write-Host "  ❌ FOUND forbidden files in app/:" -ForegroundColor Red
                foreach ($file in $found) {
                    Write-Host "     - $($file.FullName)" -ForegroundColor Red
                }
                $foundIssues = $true
            }
        }
        
        if (-not $foundIssues) {
            Write-Host "  ✅ No forbidden files in app/" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    if ($foundIssues) {
        Write-Host "❌ ISSUES FOUND IN ZIP!" -ForegroundColor Red
        Write-Host "DO NOT DEPLOY - Fix the issues first!" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "✅ ZIP VERIFICATION PASSED" -ForegroundColor Green
        Write-Host "Safe to deploy!" -ForegroundColor Green
        exit 0
    }
} finally {
    # Safely remove temp directory (check exists first, use SilentlyContinue)
    # This prevents false ItemNotFoundException errors
    if ($tempDir -and (Test-Path $tempDir)) {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

