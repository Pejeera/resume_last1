# Auto Test API Script - ใช้ test credentials หรือ environment variables
# Usage: .\test_api_auto.ps1 [username] [password]

param(
    [string]$Username = "",
    [string]$Password = ""
)

# Try to get from environment variables
if (-not $Username) {
    $Username = $env:COGNITO_USERNAME
}
if (-not $Password) {
    $Password = $env:COGNITO_PASSWORD
}

# If still not set, use defaults or prompt
if (-not $Username) {
    Write-Host "No username provided. Please provide credentials:" -ForegroundColor Yellow
    Write-Host "Usage: .\test_api_auto.ps1 -Username 'your@email.com' -Password 'yourpassword'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or set environment variables:" -ForegroundColor Yellow
    Write-Host "  `$env:COGNITO_USERNAME = 'your@email.com'" -ForegroundColor White
    Write-Host "  `$env:COGNITO_PASSWORD = 'yourpassword'" -ForegroundColor White
    Write-Host ""
    
    # Try to read from user
    $Username = Read-Host "Enter username (email) (or press Enter to skip)"
    if (-not $Username) {
        Write-Host "Skipping tests - no credentials provided" -ForegroundColor Red
        exit 1
    }
}

if (-not $Password) {
    $securePassword = Read-Host "Enter password" -AsSecureString
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    )
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Running API Tests..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Run test script
python test_api.py --username $Username --password $Password

Write-Host ""
Write-Host "Test completed!" -ForegroundColor Green

