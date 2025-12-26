# สคริปต์แก้ไข Lambda configuration เพื่อให้อ่าน jobs จาก S3 ได้
# ใช้: .\fix_lambda_s3_config.ps1

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2",
    [string]$S3BucketName = "resume-matching-533267343789",
    [string]$S3Prefix = "resumes/",
    [string]$UseMock = "false"
)

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "แก้ไข Lambda Configuration สำหรับ S3" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# 1. ดึง current configuration
Write-Host "[1/3] ดึง Lambda configuration..." -ForegroundColor Green
try {
    $currentConfig = aws lambda get-function-configuration `
        --function-name $FunctionName `
        --region $Region `
        --output json | ConvertFrom-Json
    
    if (-not $currentConfig) {
        Write-Host "❌ ไม่พบ Lambda function: $FunctionName" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ พบ Lambda function: $FunctionName" -ForegroundColor Green
    Write-Host ""
    
    # แสดง current environment variables
    Write-Host "Current Environment Variables:" -ForegroundColor Yellow
    $currentEnv = $currentConfig.Environment.Variables
    Write-Host "  USE_MOCK: $($currentEnv.USE_MOCK)" -ForegroundColor White
    Write-Host "  S3_BUCKET_NAME: $($currentEnv.S3_BUCKET_NAME)" -ForegroundColor White
    Write-Host "  S3_PREFIX: $($currentEnv.S3_PREFIX)" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
}

# 2. สร้าง environment variables ใหม่
Write-Host "[2/3] สร้าง environment variables..." -ForegroundColor Green
$envVars = @{}

# คัดลอก existing variables
foreach ($key in $currentEnv.PSObject.Properties.Name) {
    $envVars[$key] = $currentEnv.$key
}

# อัปเดตค่าที่ต้องการ
$envVars["USE_MOCK"] = $UseMock
$envVars["S3_BUCKET_NAME"] = $S3BucketName
$envVars["S3_PREFIX"] = $S3Prefix

# แสดงค่าที่จะอัปเดต
Write-Host "Values to update:" -ForegroundColor Yellow
Write-Host "  USE_MOCK: $UseMock" -ForegroundColor White
Write-Host "  S3_BUCKET_NAME: $S3BucketName" -ForegroundColor White
Write-Host "  S3_PREFIX: $S3Prefix" -ForegroundColor White
Write-Host ""

# 3. อัปเดต Lambda
Write-Host "[3/3] อัปเดต Lambda environment variables..." -ForegroundColor Green

# Convert to JSON format for AWS CLI
$envVarsJson = ($envVars.GetEnumerator() | ForEach-Object { 
    "$($_.Key)=$($_.Value)" 
}) -join ","

try {
    $result = aws lambda update-function-configuration `
        --function-name $FunctionName `
        --region $Region `
        --environment "Variables={$envVarsJson}" `
        --output json | ConvertFrom-Json
    
    Write-Host "✅ อัปเดตสำเร็จ!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Updated Environment Variables:" -ForegroundColor Yellow
    Write-Host "  USE_MOCK: $UseMock" -ForegroundColor White
    Write-Host "  S3_BUCKET_NAME: $S3BucketName" -ForegroundColor White
    Write-Host "  S3_PREFIX: $S3Prefix" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 หลังจากอัปเดตแล้ว:" -ForegroundColor Cyan
    Write-Host "   1. รอสักครู่ให้ Lambda อัปเดต configuration" -ForegroundColor White
    Write-Host "   2. ทดสอบด้วย: python debug_jobs_s3.py" -ForegroundColor White
    Write-Host "   3. หรือเรียก API: GET /api/jobs/list" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host "❌ Error updating Lambda: $_" -ForegroundColor Red
    exit 1
}

Write-Host "=" * 60 -ForegroundColor Cyan

