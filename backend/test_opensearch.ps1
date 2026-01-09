# Test OpenSearch Connection
# สคริปต์ทดสอบการเชื่อมต่อ OpenSearch

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OpenSearch Connection Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Run Python test script
Write-Host "Running OpenSearch test..." -ForegroundColor Yellow
Write-Host ""

try {
    python test_opensearch.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ OpenSearch test completed successfully!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ OpenSearch test failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "❌ Error running test: $_" -ForegroundColor Red
    exit 1
}

