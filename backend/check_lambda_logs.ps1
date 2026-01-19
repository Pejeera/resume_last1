# Check Lambda Function Logs
# Usage: .\check_lambda_logs.ps1 [-FunctionName "resume-search-api"] [-Minutes 5]

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2",
    [int]$Minutes = 5
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Lambda Function Logs Checker" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Time Range: Last $Minutes minutes" -ForegroundColor Yellow
Write-Host ""

# Get log group name
$logGroupName = "/aws/lambda/$FunctionName"

Write-Host "[Step 1] Checking log group..." -ForegroundColor Cyan
try {
    $logGroup = aws logs describe-log-groups --log-group-name-prefix $logGroupName --region $Region 2>&1 | ConvertFrom-Json
    if ($logGroup.logGroups.Count -eq 0) {
        Write-Host "   [WARNING] Log group not found: $logGroupName" -ForegroundColor Yellow
        Write-Host "   This might mean the function hasn't been invoked yet." -ForegroundColor Gray
        exit 0
    }
    Write-Host "   [OK] Log group found" -ForegroundColor Green
} catch {
    Write-Host "   [ERROR] Failed to check log group: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Calculate time range
$endTime = Get-Date
$startTime = $endTime.AddMinutes(-$Minutes)
$startTimeUnix = [Math]::Floor([decimal](Get-Date $startTime -UFormat %s))
$endTimeUnix = [Math]::Floor([decimal](Get-Date $endTime -UFormat %s))

Write-Host "[Step 2] Fetching recent logs..." -ForegroundColor Cyan
Write-Host "   Time range: $startTime to $endTime" -ForegroundColor Gray
Write-Host ""

try {
    $logs = aws logs filter-log-events `
        --log-group-name $logGroupName `
        --start-time ($startTimeUnix * 1000) `
        --end-time ($endTimeUnix * 1000) `
        --region $Region `
        --max-items 50 `
        2>&1 | ConvertFrom-Json
    
    if ($logs.events.Count -eq 0) {
        Write-Host "   [INFO] No logs found in the last $Minutes minutes" -ForegroundColor Yellow
        Write-Host "   Try increasing the time range with -Minutes parameter" -ForegroundColor Gray
        exit 0
    }
    
    Write-Host "   Found $($logs.events.Count) log entries" -ForegroundColor Green
    Write-Host ""
    Write-Host "   " + ("=" * 70) -ForegroundColor Gray
    Write-Host ""
    
    foreach ($event in $logs.events) {
        $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).LocalDateTime
        $message = $event.message
        
        # Color code by log level
        if ($message -match "ERROR|Exception|Traceback|Failed") {
            Write-Host "   [$timestamp] $message" -ForegroundColor Red
        } elseif ($message -match "WARNING|WARN") {
            Write-Host "   [$timestamp] $message" -ForegroundColor Yellow
        } elseif ($message -match "INFO") {
            Write-Host "   [$timestamp] $message" -ForegroundColor Cyan
        } else {
            Write-Host "   [$timestamp] $message" -ForegroundColor White
        }
    }
    
    Write-Host ""
    Write-Host "   " + ("=" * 70) -ForegroundColor Gray
    Write-Host ""
    
    # Check for common errors
    $errorCount = ($logs.events | Where-Object { $_.message -match "ERROR|Exception|Traceback|Failed" }).Count
    if ($errorCount -gt 0) {
        Write-Host "   [SUMMARY] Found $errorCount error(s) in logs" -ForegroundColor Red
        Write-Host ""
        Write-Host "   [COMMON ISSUES]" -ForegroundColor Yellow
        Write-Host "   - OpenSearch connection: Check OPENSEARCH_ENDPOINT and IAM permissions" -ForegroundColor Gray
        Write-Host "   - Missing dependencies: Check if all packages are in deployment package" -ForegroundColor Gray
        Write-Host "   - Import errors: Check if all modules are available" -ForegroundColor Gray
    } else {
        Write-Host "   [SUMMARY] No errors found in recent logs" -ForegroundColor Green
    }
    
} catch {
    Write-Host "   [ERROR] Failed to fetch logs: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "   [TROUBLESHOOTING]" -ForegroundColor Yellow
    Write-Host "   - Check AWS CLI is configured: aws configure list" -ForegroundColor Gray
    Write-Host "   - Check you have permissions: aws logs describe-log-groups" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "To view logs in AWS Console:" -ForegroundColor Yellow
Write-Host "https://console.aws.amazon.com/cloudwatch/home?region=$Region#logsV2:log-groups/log-group/$([System.Web.HttpUtility]::UrlEncode($logGroupName))" -ForegroundColor White
Write-Host ""