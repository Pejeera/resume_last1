# PowerShell script to delete all resumes from S3 and OpenSearch
# Run this script to clean up all resume data for testing

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ลบ Resume ทั้งหมดจาก S3 และ OpenSearch" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$backendDir = Join-Path $PSScriptRoot "backend"
if (-not (Test-Path $backendDir)) {
    Write-Host "❌ ไม่พบ backend directory" -ForegroundColor Red
    exit 1
}

Set-Location $backendDir

# Run the Python script
Write-Host "กำลังรันสคริปต์ลบ Resume..." -ForegroundColor Yellow
Write-Host ""

python delete_all_resumes.py

# Return to original directory
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "เสร็จสิ้น" -ForegroundColor Green
