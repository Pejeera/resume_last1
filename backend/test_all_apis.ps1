# Test All APIs Script
# Usage: .\test_all_apis.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API Test Suite - Resume Matching API" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get credentials
$username = Read-Host "Enter username (email)"
$password = Read-Host "Enter password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

Write-Host ""
Write-Host "Running API tests..." -ForegroundColor Yellow
Write-Host ""

# Run test script
python test_api.py --username $username --password $passwordPlain

Write-Host ""
Write-Host "Test completed!" -ForegroundColor Green

