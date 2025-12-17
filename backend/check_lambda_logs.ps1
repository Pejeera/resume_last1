# Quick script to check Lambda logs
$functionName = "ResumeMatchAPI"
$region = "us-east-1"

Write-Host "Checking Lambda logs for: $functionName" -ForegroundColor Cyan
Write-Host ""

aws logs tail "/aws/lambda/$functionName" `
    --region $region `
    --since 10m `
    --format short `
    --follow

