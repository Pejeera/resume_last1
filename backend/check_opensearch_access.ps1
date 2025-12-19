# Script to check if OpenSearch is accessible without VPC
# This helps verify if OpenSearch can be used from Lambda outside VPC

param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Check OpenSearch Access Configuration" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get Lambda VPC config
Write-Host "[1/3] Checking Lambda VPC configuration..." -ForegroundColor Green
$lambdaConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query '{VpcId:VpcConfig.VpcId, Subnets:VpcConfig.SubnetIds}' `
    --output json | ConvertFrom-Json

if ($lambdaConfig.VpcId) {
    Write-Host "   [X] Lambda is in VPC: $($lambdaConfig.VpcId)" -ForegroundColor Red
    Write-Host "   Subnets: $($lambdaConfig.Subnets -join ', ')" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   [WARNING] Lambda in VPC can only access:" -ForegroundColor Yellow
    Write-Host "      - Resources in the same VPC" -ForegroundColor White
    Write-Host "      - Public endpoints (if OpenSearch is public)" -ForegroundColor White
    Write-Host "      - VPC Endpoints (if configured)" -ForegroundColor White
} else {
    Write-Host "   [OK] Lambda is NOT in VPC" -ForegroundColor Green
    Write-Host "   Lambda can access public endpoints" -ForegroundColor White
}

Write-Host ""

# Get OpenSearch endpoint from Lambda env vars
Write-Host "[2/3] Checking OpenSearch endpoint configuration..." -ForegroundColor Green
$envVars = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query 'Environment.Variables' `
    --output json | ConvertFrom-Json

$opensearchEndpoint = $envVars.OPENSEARCH_ENDPOINT
$useMock = $envVars.USE_MOCK

if ($useMock -eq "true") {
    Write-Host "   [WARNING] USE_MOCK is enabled - OpenSearch is not being used" -ForegroundColor Yellow
} else {
    if ($opensearchEndpoint) {
        Write-Host "   OpenSearch Endpoint: $opensearchEndpoint" -ForegroundColor White
        
        # Check if endpoint is public or VPC
        if ($opensearchEndpoint -match '\.(es|aoss)\.amazonaws\.com$') {
            Write-Host "   [OK] Endpoint format suggests AWS OpenSearch Service" -ForegroundColor Green
            Write-Host ""
            Write-Host "   [INFO] To verify OpenSearch access type:" -ForegroundColor Cyan
            Write-Host "      1. Go to AWS Console > OpenSearch Service" -ForegroundColor White
            Write-Host "      2. Check your domain's 'Network' configuration" -ForegroundColor White
            Write-Host "      3. Look for 'Public access' or 'VPC' setting" -ForegroundColor White
        } else {
            Write-Host "   [WARNING] Custom endpoint - verify access manually" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   [ERROR] OPENSEARCH_ENDPOINT not configured" -ForegroundColor Red
    }
}

Write-Host ""

# Summary
Write-Host "[3/3] Summary and Recommendations" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

if (-not $lambdaConfig.VpcId) {
    Write-Host ""
    Write-Host "[OK] Lambda is OUTSIDE VPC" -ForegroundColor Green
    Write-Host "   -> Can access public OpenSearch endpoints" -ForegroundColor White
    Write-Host "   -> Cannot access VPC-only OpenSearch" -ForegroundColor White
    Write-Host ""
    Write-Host "[INFO] To use OpenSearch without VPC:" -ForegroundColor Cyan
    Write-Host "   1. Ensure OpenSearch domain has 'Public access' enabled" -ForegroundColor White
    Write-Host "   2. Configure fine-grained access control (FGAC) for security" -ForegroundColor White
    Write-Host "   3. Use resource-based or identity-based policies" -ForegroundColor White
    Write-Host "   4. Set OPENSEARCH_ENDPOINT to public endpoint URL" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "[WARNING] Lambda is IN VPC" -ForegroundColor Yellow
    Write-Host "   -> To use OpenSearch without VPC:" -ForegroundColor White
    Write-Host "     1. Run: .\remove_lambda_from_vpc.ps1" -ForegroundColor Yellow
    Write-Host "     2. Ensure OpenSearch has public access enabled" -ForegroundColor Yellow
    Write-Host "     3. Configure proper security policies" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[SECURITY] Security Note:" -ForegroundColor Cyan
Write-Host "   Public OpenSearch requires proper authentication and" -ForegroundColor White
Write-Host "   fine-grained access control. Never expose without security!" -ForegroundColor White
Write-Host ""

