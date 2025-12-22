# Check OpenSearch Master User configuration
param(
    [string]$DomainName = "resume-search-dev",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ตรวจสอบ Master User Configuration" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Domain: $DomainName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

try {
    $domainInfo = aws opensearch describe-domain `
        --domain-name $DomainName `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $domainStatus = $domainInfo.DomainStatus
    $advancedSecurity = $domainStatus.AdvancedSecurityOptions
    
    Write-Host "[1/2] Master User Configuration:" -ForegroundColor Green
    Write-Host ""
    
    if ($advancedSecurity -and $advancedSecurity.Enabled) {
        Write-Host "   Fine-Grained Access Control: Enabled" -ForegroundColor Green
        
        $masterUserOptions = $advancedSecurity.MasterUserOptions
        
        if ($masterUserOptions.MasterUserARN) {
            Write-Host "   Master User Type: IAM" -ForegroundColor Yellow
            Write-Host "   Master User ARN: $($masterUserOptions.MasterUserARN)" -ForegroundColor White
            Write-Host ""
            Write-Host "   [INFO] ต้องใช้ IAM credentials เพื่อ login:" -ForegroundColor Cyan
            Write-Host "     1. ใช้ AWS CLI credentials (aws configure)" -ForegroundColor White
            Write-Host "     2. หรือใช้ IAM user ที่มีสิทธิ์เข้าถึง OpenSearch" -ForegroundColor White
            Write-Host "     3. หรือใช้ browser extension ที่ sign in ด้วย AWS" -ForegroundColor White
        } elseif ($masterUserOptions.MasterUserName) {
            Write-Host "   Master User Type: Internal user database" -ForegroundColor Yellow
            Write-Host "   Master User Name: $($masterUserOptions.MasterUserName)" -ForegroundColor White
            Write-Host ""
            Write-Host "   [INFO] ต้องใช้ username/password ที่ตั้งค่าไว้ตอนสร้าง domain" -ForegroundColor Cyan
            Write-Host "     - Username: $($masterUserOptions.MasterUserName)" -ForegroundColor White
            Write-Host "     - Password: (ตั้งค่าไว้ตอนสร้าง domain)" -ForegroundColor White
        } else {
            Write-Host "   [WARNING] ไม่พบ Master User configuration" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   Fine-Grained Access Control: Disabled" -ForegroundColor Yellow
        Write-Host "   [INFO] ไม่ต้อง login - ใช้ Access Policy เท่านั้น" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "[2/2] วิธี Login:" -ForegroundColor Green
    Write-Host ""
    
    if ($masterUserOptions.MasterUserARN) {
        Write-Host "   วิธีที่ 1: ใช้ AWS CLI credentials" -ForegroundColor Yellow
        Write-Host "     1. ตั้งค่า AWS CLI: aws configure" -ForegroundColor White
        Write-Host "     2. ใช้ browser extension: AWS Sign-In" -ForegroundColor White
        Write-Host "     3. หรือใช้ IAM user ที่มีสิทธิ์" -ForegroundColor White
        Write-Host ""
        Write-Host "   วิธีที่ 2: ใช้ IAM User" -ForegroundColor Yellow
        Write-Host "     1. สร้าง IAM user ใหม่" -ForegroundColor White
        Write-Host "     2. Attach policy: AmazonOpenSearchServiceFullAccess" -ForegroundColor White
        Write-Host "     3. ใช้ credentials ของ IAM user นี้" -ForegroundColor White
        Write-Host ""
        Write-Host "   วิธีที่ 3: ใช้ IAM Role (ถ้ามี)" -ForegroundColor Yellow
        Write-Host "     - ใช้ role ที่มีสิทธิ์เข้าถึง OpenSearch" -ForegroundColor White
    } else {
        Write-Host "   ใช้ username/password ที่ตั้งค่าไว้ตอนสร้าง domain" -ForegroundColor White
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "URL: https://$($domainStatus.Endpoint)/_dashboards" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    
} catch {
    Write-Host "[ERROR] ไม่สามารถดึงข้อมูล: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "ตรวจสอบว่า:" -ForegroundColor Yellow
    Write-Host "  1. AWS CLI configured และมี permission" -ForegroundColor White
    Write-Host "  2. Domain name และ region ถูกต้อง" -ForegroundColor White
}

