# Quick API Test - ทดสอบ API โดยไม่ต้องใส่ credentials (เฉพาะ endpoints ที่ไม่ต้อง auth)
# หรือใช้ credentials ที่มีอยู่

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Quick API Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test Health endpoint (อาจต้อง auth ขึ้นอยู่กับ API Gateway config)
Write-Host "Testing Health Endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health" -Method Get -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✓ Health check passed!" -ForegroundColor Green
    Write-Host "  Status: $($response.status)" -ForegroundColor White
    Write-Host "  Service: $($response.service)" -ForegroundColor White
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "✗ Health endpoint requires authentication" -ForegroundColor Yellow
        Write-Host "  (This is normal if API Gateway requires auth for all endpoints)" -ForegroundColor Gray
    } else {
        Write-Host "✗ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  To test all APIs, you need credentials:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run one of these commands:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Interactive mode (will prompt for credentials):" -ForegroundColor White
Write-Host "   .\test_all_apis.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. With credentials as parameters:" -ForegroundColor White
Write-Host '   .\test_api_auto.ps1 -Username "your@email.com" -Password "yourpassword"' -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Set environment variables first:" -ForegroundColor White
Write-Host '   $env:COGNITO_USERNAME = "your@email.com"' -ForegroundColor Gray
Write-Host '   $env:COGNITO_PASSWORD = "yourpassword"' -ForegroundColor Gray
Write-Host "   .\test_api_auto.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. Direct Python command:" -ForegroundColor White
Write-Host '   python test_api.py --username "your@email.com" --password "yourpassword"' -ForegroundColor Cyan
Write-Host ""
