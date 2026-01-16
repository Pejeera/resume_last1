# Check if OpenSearch client fix is deployed
# This script helps verify that the fixed code is in the deployment package

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Check - OpenSearch Client Fix" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$lambdaPackagePath = "lambda-package\app\clients\opensearch_client.py"

if (Test-Path $lambdaPackagePath) {
    Write-Host "[CHECK] Found opensearch_client.py in lambda-package" -ForegroundColor Green
    Write-Host ""
    
    # Check for critical fixes
    $content = Get-Content $lambdaPackagePath -Raw
    
    $checks = @{
        "Port 443" = $content -match "port = 443"
        "use_ssl=True" = $content -match "use_ssl=True"
        "verify_certs=True" = $content -match "verify_certs=True"
        "session_token" = $content -match "session_token=credentials.token"
        "RequestsHttpConnection" = $content -match "RequestsHttpConnection"
    }
    
    Write-Host "[VERIFICATION] Checking critical fixes:" -ForegroundColor Cyan
    Write-Host ""
    
    $allPassed = $true
    foreach ($check in $checks.GetEnumerator()) {
        if ($check.Value) {
            Write-Host "  [OK] $($check.Key)" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $($check.Key)" -ForegroundColor Red
            $allPassed = $false
        }
    }
    
    Write-Host ""
    
    if ($allPassed) {
        Write-Host "[RESULT] All fixes are present in deployment package!" -ForegroundColor Green
        Write-Host ""
        Write-Host "[NEXT STEP] Deploy the Lambda function:" -ForegroundColor Yellow
        Write-Host "  .\deploy_lambda_clean.ps1" -ForegroundColor White
    } else {
        Write-Host "[RESULT] Some fixes are missing!" -ForegroundColor Red
        Write-Host ""
        Write-Host "[ACTION] Copy the fixed file to lambda-package:" -ForegroundColor Yellow
        Write-Host "  Copy-Item app\clients\opensearch_client.py lambda-package\app\clients\opensearch_client.py -Force" -ForegroundColor White
    }
    
} else {
    Write-Host "[ERROR] opensearch_client.py not found in lambda-package!" -ForegroundColor Red
    Write-Host ""
    Write-Host "[ACTION] You need to:" -ForegroundColor Yellow
    Write-Host "  1. Run deployment script to copy files" -ForegroundColor White
    Write-Host "  2. Or manually copy: Copy-Item -Recurse app lambda-package\" -ForegroundColor White
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan

