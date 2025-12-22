# Check CloudWatch Logs for OpenSearch errors
param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ตรวจสอบ CloudWatch Logs" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

Write-Host "[1/2] กำลังดึง log streams ล่าสุด..." -ForegroundColor Green
try {
    $logGroup = "/aws/lambda/$FunctionName"
    
    # Get latest log streams
    $logStreams = aws logs describe-log-streams `
        --log-group-name $logGroup `
        --order-by LastEventTime `
        --descending `
        --max-items 5 `
        --region $Region `
        --output json | ConvertFrom-Json
    
    if ($logStreams.logStreams.Count -eq 0) {
        Write-Host "   [WARNING] ไม่พบ log streams" -ForegroundColor Yellow
        exit 0
    }
    
    Write-Host "   พบ $($logStreams.logStreams.Count) log streams" -ForegroundColor White
    Write-Host ""
    
    # Get latest log stream
    $latestStream = $logStreams.logStreams[0]
    Write-Host "[2/2] กำลังดึง logs จาก stream ล่าสุด..." -ForegroundColor Green
    Write-Host "   Stream: $($latestStream.logStreamName)" -ForegroundColor White
    Write-Host "   Last Event: $($latestStream.lastEventTime)" -ForegroundColor White
    Write-Host ""
    
    # Get log events
    $logEvents = aws logs get-log-events `
        --log-group-name $logGroup `
        --log-stream-name $latestStream.logStreamName `
        --limit 50 `
        --region $Region `
        --output json | ConvertFrom-Json
    
    Write-Host "=== Log Events (50 ล่าสุด) ===" -ForegroundColor Cyan
    Write-Host ""
    
    $errorCount = 0
    $opensearchErrors = @()
    
    foreach ($event in $logEvents.events) {
        $message = $event.message
        
        # Check for OpenSearch errors
        if ($message -match "OpenSearch|opensearch|AuthorizationException|403|401") {
            $opensearchErrors += $message
            Write-Host "[ERROR] $message" -ForegroundColor Red
            $errorCount++
        } elseif ($message -match "ERROR|Exception|Traceback") {
            Write-Host "[ERROR] $message" -ForegroundColor Red
            $errorCount++
        } elseif ($message -match "INFO|WARNING") {
            Write-Host "[INFO] $message" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "สรุป" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Total Events: $($logEvents.events.Count)" -ForegroundColor White
    Write-Host "Errors Found: $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })
    Write-Host ""
    
    if ($opensearchErrors.Count -gt 0) {
        Write-Host "OpenSearch Errors:" -ForegroundColor Red
        foreach ($error in $opensearchErrors) {
            Write-Host "  - $error" -ForegroundColor Red
        }
        Write-Host ""
    }
    
} catch {
    Write-Host "[ERROR] ไม่สามารถดึง logs: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "ตรวจสอบว่า:" -ForegroundColor Yellow
    Write-Host "  1. CloudWatch Logs มี logs หรือไม่" -ForegroundColor White
    Write-Host "  2. Lambda function ถูก invoke แล้วหรือยัง" -ForegroundColor White
    Write-Host "  3. มีสิทธิ์เข้าถึง CloudWatch Logs" -ForegroundColor White
}

Write-Host ""
Write-Host "ดู logs ใน AWS Console:" -ForegroundColor Cyan
Write-Host "  https://console.aws.amazon.com/cloudwatch/home?region=$Region#logsV2:log-groups/log-group/$([uri]::EscapeDataString("/aws/lambda/$FunctionName"))" -ForegroundColor White
Write-Host ""

