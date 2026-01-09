# Check Lambda CloudWatch Logs
# Usage: .\check_lambda_logs.ps1

param(
    [Parameter(Mandatory=$false)]
    [string]$FunctionName = "resume-search-api",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-southeast-2",
    
    [Parameter(Mandatory=$false)]
    [int]$Minutes = 15
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking Lambda CloudWatch Logs" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Time Range: Last $Minutes minutes" -ForegroundColor Yellow
Write-Host ""

# Get log group name
$logGroup = "/aws/lambda/$FunctionName"

Write-Host "Fetching recent logs..." -ForegroundColor Green
Write-Host ""

try {
    # Get logs from last N minutes
    $startTime = (Get-Date).AddMinutes(-$Minutes).ToUniversalTime()
    $startTimeUnix = [Math]::Floor((New-TimeSpan -Start (Get-Date "1970-01-01") -End $startTime).TotalSeconds) * 1000
    
    aws logs tail $logGroup `
        --region $Region `
        --since "${Minutes}m" `
        --format short `
        --follow false
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Logs retrieved successfully" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To follow logs in real-time, run:" -ForegroundColor Yellow
    Write-Host "  aws logs tail $logGroup --follow --region $Region" -ForegroundColor Gray
    
} catch {
    Write-Host "ERROR: Failed to retrieve logs" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure:" -ForegroundColor Yellow
    Write-Host "  1. AWS CLI is installed and configured" -ForegroundColor Gray
    Write-Host "  2. You have permissions to read CloudWatch logs" -ForegroundColor Gray
    Write-Host "  3. Lambda function name is correct: $FunctionName" -ForegroundColor Gray
}

