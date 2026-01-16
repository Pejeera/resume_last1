# Script to configure CORS on API Gateway
# This script helps set up CORS for API Gateway HTTP API

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API Gateway CORS Configuration Guide" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$apiId = "tm0ch5vc2e"  # Your API Gateway ID
$region = "ap-southeast-2"

Write-Host "[IMPORTANT]" -ForegroundColor Yellow
Write-Host "CORS must be configured at BOTH levels:" -ForegroundColor White
Write-Host "  1. Lambda function (already done)" -ForegroundColor Green
Write-Host "  2. API Gateway (must be done manually)" -ForegroundColor Yellow
Write-Host ""

Write-Host "[STEP 1: Enable CORS on API Gateway]" -ForegroundColor Cyan
Write-Host "Go to AWS Console -> API Gateway -> Your API" -ForegroundColor White
Write-Host ""

Write-Host "Option A: Enable CORS for specific route (/api/auth/login)" -ForegroundColor Yellow
Write-Host "  1. Select route: POST /api/auth/login" -ForegroundColor Gray
Write-Host "  2. Click 'Actions' -> 'Enable CORS'" -ForegroundColor Gray
Write-Host "  3. Configure:" -ForegroundColor Gray
Write-Host "     - Access-Control-Allow-Origin: *" -ForegroundColor Gray
Write-Host "     - Access-Control-Allow-Methods: POST, OPTIONS" -ForegroundColor Gray
Write-Host "     - Access-Control-Allow-Headers: Content-Type, Authorization, Accept, X-Requested-With" -ForegroundColor Gray
Write-Host "  4. Click 'Enable CORS and replace existing CORS headers'" -ForegroundColor Gray
Write-Host ""

Write-Host "Option B: Enable CORS for catch-all route (/{proxy+})" -ForegroundColor Yellow
Write-Host "  1. Select route: ANY /{proxy+}" -ForegroundColor Gray
Write-Host "  2. Click 'Actions' -> 'Enable CORS'" -ForegroundColor Gray
Write-Host "  3. Configure same settings as above" -ForegroundColor Gray
Write-Host "  4. Click 'Enable CORS and replace existing CORS headers'" -ForegroundColor Gray
Write-Host ""

Write-Host "[STEP 2: Add OPTIONS method]" -ForegroundColor Cyan
Write-Host "For each route that needs CORS, ensure OPTIONS method exists:" -ForegroundColor White
Write-Host "  1. Select route (e.g., /api/auth/login)" -ForegroundColor Gray
Write-Host "  2. Click 'Actions' -> 'Create Method' -> Select 'OPTIONS'" -ForegroundColor Gray
Write-Host "  3. Integration type: Mock" -ForegroundColor Gray
Write-Host "  4. Integration response: 200 OK" -ForegroundColor Gray
Write-Host "  5. Method response: Add CORS headers" -ForegroundColor Gray
Write-Host ""

Write-Host "[STEP 3: Deploy API]" -ForegroundColor Cyan
Write-Host "After configuring CORS, you MUST deploy the API:" -ForegroundColor White
Write-Host "  1. Click 'Actions' -> 'Deploy API'" -ForegroundColor Gray
Write-Host "  2. Select stage: '$default' or your stage" -ForegroundColor Gray
Write-Host "  3. Click 'Deploy'" -ForegroundColor Gray
Write-Host ""

Write-Host "[STEP 4: Test CORS]" -ForegroundColor Cyan
Write-Host "Test with curl or browser:" -ForegroundColor White
$curlCmd = "curl -X OPTIONS https://$apiId.execute-api.$region.amazonaws.com/api/auth/login -H 'Origin: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com' -H 'Access-Control-Request-Method: POST' -v"
Write-Host "  $curlCmd" -ForegroundColor Yellow
Write-Host ""

Write-Host "[ALTERNATIVE: Use AWS CLI]" -ForegroundColor Cyan
Write-Host "You can also configure CORS using AWS CLI:" -ForegroundColor White
Write-Host ""
Write-Host "# Get API ID" -ForegroundColor Gray
Write-Host "aws apigatewayv2 get-apis --region $region" -ForegroundColor Yellow
Write-Host ""
Write-Host "# Create CORS configuration" -ForegroundColor Gray
Write-Host "# Note: This requires API Gateway v2 (HTTP API)" -ForegroundColor Yellow
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "After completing these steps, test login again!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

