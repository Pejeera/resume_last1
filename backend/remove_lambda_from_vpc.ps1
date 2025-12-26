# Script to remove Lambda from VPC (quick fix for network timeout)

$FunctionName = "resume-search-api"
$Region = "ap-southeast-2"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Remove Lambda from VPC" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""
Write-Host "WARNING: This will remove Lambda from VPC!" -ForegroundColor Red
Write-Host "Lambda will have internet access automatically." -ForegroundColor Yellow
Write-Host ""

# Get current VPC config
Write-Host "[1/2] Checking current VPC configuration..." -ForegroundColor Green
$currentConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query 'VpcConfig' `
    --output json | ConvertFrom-Json

if ($currentConfig.VpcId) {
    Write-Host "   Current VPC: $($currentConfig.VpcId)" -ForegroundColor Yellow
    Write-Host "   Subnets: $($currentConfig.SubnetIds -join ', ')" -ForegroundColor Yellow
    Write-Host ""
    
    # Confirm
    $confirm = Read-Host "Remove Lambda from VPC? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
    
    Write-Host ""
    Write-Host "[2/2] Removing Lambda from VPC..." -ForegroundColor Green
    aws lambda update-function-configuration `
        --function-name $FunctionName `
        --region $Region `
        --vpc-config SubnetIds=[],SecurityGroupIds=[] `
        --output json | ConvertFrom-Json | Select-Object FunctionName, VpcConfig, LastModified
    
    Write-Host ""
    Write-Host "Lambda removed from VPC successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Wait ~30 seconds for Lambda to update" -ForegroundColor Yellow
    Write-Host "2. Test API: python test_jobs_api.py" -ForegroundColor Yellow
    Write-Host "3. Lambda will now have internet access" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "   Lambda is not in VPC" -ForegroundColor Green
    Write-Host "   No action needed" -ForegroundColor Green
}

Write-Host ""

