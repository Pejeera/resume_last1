# สคริปต์ deploy Lambda แบบ zip (ง่ายและเร็ว)
# ใช้: .\deploy_lambda_zip.ps1

param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1"
)

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Deploy Lambda Function (ZIP Method)" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region  : $Region" -ForegroundColor Yellow
Write-Host ""

# ตรวจสอบว่าอยู่ใน directory ที่ถูกต้อง
$currentDir = Get-Location
if (-not (Test-Path "lambda-package")) {
    Write-Host "❌ ไม่พบโฟลเดอร์ lambda-package" -ForegroundColor Red
    Write-Host "   กรุณารันจาก backend directory" -ForegroundColor Yellow
    exit 1
}

# ตรวจสอบว่า lambda-package มีไฟล์ที่จำเป็น
if (-not (Test-Path "lambda-package/lambda_function.py")) {
    Write-Host "❌ ไม่พบ lambda_function.py ใน lambda-package" -ForegroundColor Red
    exit 1
}

Write-Host "[1/3] กำลังสร้าง zip file..." -ForegroundColor Green
$zipFile = "lambda-deployment.zip"

# ลบ zip เก่าถ้ามี
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
    Write-Host "   ลบ zip เก่าแล้ว" -ForegroundColor Gray
}

# เข้าไปใน lambda-package และ zip
Push-Location lambda-package

try {
    # ใช้ PowerShell Compress-Archive
    Compress-Archive -Path * -DestinationPath "..\$zipFile" -Force
    Write-Host "✅ สร้าง zip file สำเร็จ: $zipFile" -ForegroundColor Green
    
    # ตรวจสอบขนาดไฟล์
    $fileSize = (Get-Item "..\$zipFile").Length / 1MB
    Write-Host "   ขนาดไฟล์: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Gray
} catch {
    Write-Host "❌ Error creating zip: $_" -ForegroundColor Red
    Pop-Location
    exit 1
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "[2/3] กำลังอัปเดต Lambda function code..." -ForegroundColor Green

try {
    $result = aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$zipFile" `
        --region $Region `
        --output json | ConvertFrom-Json
    
    if ($result) {
        Write-Host "✅ Deploy สำเร็จ!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Function Details:" -ForegroundColor Yellow
        Write-Host "  Function Name: $($result.FunctionName)" -ForegroundColor White
        Write-Host "  Last Modified: $($result.LastModified)" -ForegroundColor White
        Write-Host "  Code Size: $([math]::Round($result.CodeSize / 1MB, 2)) MB" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host "⚠️  Deploy อาจไม่สำเร็จ - ตรวจสอบ output ด้านบน" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Error deploying Lambda: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 ตรวจสอบ:" -ForegroundColor Cyan
    Write-Host "   1. AWS CLI configured และมี permission" -ForegroundColor White
    Write-Host "   2. Function name ถูกต้อง: $FunctionName" -ForegroundColor White
    Write-Host "   3. Region ถูกต้อง: $Region" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "[3/3] กำลังรอให้ Lambda อัปเดตเสร็จ..." -ForegroundColor Green

# รอให้ Lambda update เสร็จ
$maxWait = 30
$waited = 0
$updateComplete = $false

while ($waited -lt $maxWait -and -not $updateComplete) {
    Start-Sleep -Seconds 2
    $waited += 2
    
    try {
        $status = aws lambda get-function-configuration `
            --function-name $FunctionName `
            --region $Region `
            --query 'LastUpdateStatus' `
            --output text 2>$null
        
        if ($status -eq "Successful") {
            $updateComplete = $true
            Write-Host "✅ Lambda อัปเดตเสร็จแล้ว!" -ForegroundColor Green
        } elseif ($status -eq "InProgress") {
            Write-Host "   กำลังอัปเดต... ($waited/$maxWait seconds)" -ForegroundColor Gray
        } else {
            Write-Host "   Status: $status" -ForegroundColor Gray
        }
    } catch {
        # Ignore errors during status check
    }
}

if (-not $updateComplete) {
    Write-Host "⚠️  Timeout - Lambda อาจยังอัปเดตไม่เสร็จ" -ForegroundColor Yellow
    Write-Host "   ตรวจสอบใน AWS Console" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "✅ Deploy เสร็จสมบูรณ์!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 ทดสอบด้วย:" -ForegroundColor Cyan
Write-Host "   python debug_jobs_s3.py" -ForegroundColor White
Write-Host '   หรือเรียก API: GET /api/jobs/list' -ForegroundColor White
Write-Host ""

