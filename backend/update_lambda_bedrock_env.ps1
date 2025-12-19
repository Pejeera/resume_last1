# อัปเดต Lambda environment variables สำหรับ Bedrock
param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1",
    [string]$BedrockRegion = "us-east-1",
    [string]$BedrockEmbeddingModel = "cohere.embed-multilingual-v3",
    [string]$BedrockRerankModel = "us.amazon.nova-lite-v1:0"
)

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "อัปเดต Lambda Bedrock Configuration" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# ดึง current configuration
Write-Host "[1/2] ดึง Lambda configuration..." -ForegroundColor Green
$currentConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --output json | ConvertFrom-Json

$currentEnv = $currentConfig.Environment.Variables
$envVars = @{}

# คัดลอก existing variables
foreach ($key in $currentEnv.PSObject.Properties.Name) {
    $envVars[$key] = $currentEnv.$key
}

# เพิ่ม Bedrock variables
$envVars["BEDROCK_REGION"] = $BedrockRegion
$envVars["BEDROCK_EMBEDDING_MODEL"] = $BedrockEmbeddingModel
$envVars["BEDROCK_RERANK_MODEL"] = $BedrockRerankModel

Write-Host "Environment Variables to update:" -ForegroundColor Yellow
Write-Host "  BEDROCK_REGION: $BedrockRegion" -ForegroundColor White
Write-Host "  BEDROCK_EMBEDDING_MODEL: $BedrockEmbeddingModel" -ForegroundColor White
Write-Host "  BEDROCK_RERANK_MODEL: $BedrockRerankModel" -ForegroundColor White
Write-Host ""

# Convert to JSON format
$envVarsJson = ($envVars.GetEnumerator() | ForEach-Object { 
    "$($_.Key)=$($_.Value)" 
}) -join ","

Write-Host "[2/2] อัปเดต Lambda..." -ForegroundColor Green
aws lambda update-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --environment "Variables={$envVarsJson}" `
    --output json | ConvertFrom-Json | Select-Object FunctionName, LastModified

Write-Host ""
Write-Host "✅ อัปเดตสำเร็จ!" -ForegroundColor Green
Write-Host ""

