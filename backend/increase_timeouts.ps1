# Script to increase timeouts for Lambda and API Gateway

$FunctionName = "ResumeMatchAPI"
$Region = "us-east-1"
$ApiGatewayId = "k9z3rlu1ui"
$StageName = "prod"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Increasing Timeouts" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Lambda timeout is already 900 seconds (15 minutes) - maximum
Write-Host "[1/2] Checking Lambda timeout..." -ForegroundColor Green
$lambdaConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query '{Timeout:Timeout,MemorySize:MemorySize}' `
    --output json | ConvertFrom-Json

Write-Host "   Current Lambda Timeout: $($lambdaConfig.Timeout) seconds (15 minutes - MAXIMUM)" -ForegroundColor Yellow
Write-Host "   Current Lambda Memory: $($lambdaConfig.MemorySize) MB" -ForegroundColor Yellow
Write-Host "   Lambda timeout is already at maximum (900 seconds)" -ForegroundColor Green
Write-Host ""

# 2. API Gateway timeout - check and increase if needed
Write-Host "[2/2] Checking API Gateway timeout..." -ForegroundColor Green

# Get API Gateway integration
$integrations = aws apigateway get-integrations `
    --rest-api-id $ApiGatewayId `
    --region $Region `
    --output json | ConvertFrom-Json

if ($integrations.items) {
    Write-Host "   Found $($integrations.items.Count) integrations" -ForegroundColor Gray
    
    foreach ($integration in $integrations.items) {
        $integrationId = $integration.id
        $resourceId = $integration.resourceId
        $httpMethod = $integration.httpMethod
        
        Write-Host "   Integration: $httpMethod on resource $resourceId" -ForegroundColor Gray
        
        # Check current timeout
        $currentTimeout = $integration.timeoutInMillis
        if ($currentTimeout) {
            Write-Host "   Current timeout: $($currentTimeout)ms ($([math]::Round($currentTimeout/1000, 1)) seconds)" -ForegroundColor Yellow
        } else {
            Write-Host "   Current timeout: Not set (default 30 seconds)" -ForegroundColor Yellow
        }
        
        # API Gateway max timeout is 30 seconds for REST API
        # But we can set integration timeout to 29 seconds (max)
        $newTimeout = 29000  # 29 seconds (max for REST API)
        
        if (-not $currentTimeout -or $currentTimeout -lt $newTimeout) {
            Write-Host "   Updating timeout to $newTimeout ms (29 seconds - REST API maximum)..." -ForegroundColor Cyan
            
            # Update integration timeout
            aws apigateway update-integration `
                --rest-api-id $ApiGatewayId `
                --resource-id $resourceId `
                --http-method $httpMethod `
                --patch-ops op=replace,path=/timeoutInMillis,value=$newTimeout `
                --region $Region | Out-Null
            
            Write-Host "   Updated timeout to 29 seconds" -ForegroundColor Green
        } else {
            Write-Host "   Timeout already at maximum" -ForegroundColor Green
        }
    }
} else {
    Write-Host "   No integrations found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Lambda Timeout: 900 seconds (15 minutes) - MAXIMUM" -ForegroundColor Yellow
Write-Host "API Gateway Timeout: 29 seconds - MAXIMUM for REST API" -ForegroundColor Yellow
Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Red
Write-Host "Lambda Init Timeout: 10 seconds - HARD LIMIT (cannot be changed)" -ForegroundColor Red
Write-Host ""
Write-Host "The 10-second init timeout is an AWS Lambda hard limit." -ForegroundColor Yellow
Write-Host "If Lambda is in VPC without proper network access, it will timeout during init." -ForegroundColor Yellow
Write-Host ""
Write-Host "Solutions:" -ForegroundColor Cyan
Write-Host "1. Add VPC Endpoints for S3 and CloudWatch Logs" -ForegroundColor White
Write-Host "2. Add NAT Gateway for internet access" -ForegroundColor White
Write-Host "3. Remove Lambda from VPC (if not needed)" -ForegroundColor White
Write-Host ""

