# Script to check and update OpenSearch Access Policy
param(
    [string]$DomainName = "resume-search-dev",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ตรวจสอบ OpenSearch Access Policy" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Domain: $DomainName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

# Get domain configuration
Write-Host "[1/3] กำลังดึงข้อมูล domain configuration..." -ForegroundColor Green
try {
    $domainInfo = aws opensearch describe-domain `
        --domain-name $DomainName `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $domainStatus = $domainInfo.DomainStatus
    
    Write-Host "   Domain Name: $($domainStatus.DomainName)" -ForegroundColor White
    Write-Host "   Endpoint: $($domainStatus.Endpoint)" -ForegroundColor White
    Write-Host "   DomainId: $($domainStatus.DomainId)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "   [ERROR] ไม่สามารถดึงข้อมูล domain: $_" -ForegroundColor Red
    exit 1
}

# Check Access Policy
Write-Host "[2/3] ตรวจสอบ Access Policy..." -ForegroundColor Green
$accessPolicies = $domainStatus.AccessPolicies

if ($accessPolicies) {
    Write-Host "   Access Policy: มีการตั้งค่า" -ForegroundColor Green
    try {
        $policy = $accessPolicies | ConvertFrom-Json
        Write-Host "   Policy Version: $($policy.Version)" -ForegroundColor White
        
        if ($policy.Statement) {
            Write-Host "   Statements: $($policy.Statement.Count)" -ForegroundColor White
            foreach ($stmt in $policy.Statement) {
                Write-Host "     - Effect: $($stmt.Effect)" -ForegroundColor Gray
                if ($stmt.Principal) {
                    if ($stmt.Principal.AWS) {
                        Write-Host "       Principal: $($stmt.Principal.AWS)" -ForegroundColor Gray
                    } else {
                        Write-Host "       Principal: $($stmt.Principal | ConvertTo-Json -Compress)" -ForegroundColor Gray
                    }
                }
                Write-Host "       Action: $($stmt.Action)" -ForegroundColor Gray
            }
        }
    } catch {
        Write-Host "   [WARNING] ไม่สามารถ parse policy JSON" -ForegroundColor Yellow
        Write-Host "   Policy: $accessPolicies" -ForegroundColor Gray
    }
} else {
    Write-Host "   [WARNING] ไม่มีการตั้งค่า Access Policy" -ForegroundColor Yellow
    Write-Host "   ต้องตั้งค่า Access Policy เพื่อให้เข้าถึงได้" -ForegroundColor Yellow
}

Write-Host ""

# Check Network Configuration
Write-Host "[3/3] ตรวจสอบ Network Configuration..." -ForegroundColor Green
$vpcOptions = $domainStatus.VPCOptions

if ($vpcOptions -and $vpcOptions.VPCId) {
    Write-Host "   [INFO] Domain อยู่ใน VPC: $($vpcOptions.VPCId)" -ForegroundColor Yellow
    Write-Host "   Subnets: $($vpcOptions.SubnetIds -join ', ')" -ForegroundColor White
    Write-Host "   Security Groups: $($vpcOptions.SecurityGroupIds -join ', ')" -ForegroundColor White
    Write-Host ""
    Write-Host "   [NOTE] ถ้า domain อยู่ใน VPC:" -ForegroundColor Cyan
    Write-Host "     - ต้องเข้าถึงผ่าน VPC endpoint หรือ NAT gateway" -ForegroundColor White
    Write-Host "     - Browser ไม่สามารถเข้าถึงได้โดยตรง" -ForegroundColor White
} else {
    Write-Host "   [OK] Domain มี public access" -ForegroundColor Green
    Write-Host "   สามารถเข้าถึงได้จาก internet" -ForegroundColor White
}

# Check Fine-Grained Access Control
Write-Host ""
Write-Host "ตรวจสอบ Fine-Grained Access Control..." -ForegroundColor Green
$advancedSecurity = $domainStatus.AdvancedSecurityOptions

if ($advancedSecurity -and $advancedSecurity.Enabled) {
    Write-Host "   Fine-Grained Access Control: Enabled" -ForegroundColor Green
    Write-Host "   Internal User Database: $($advancedSecurity.InternalUserDatabaseEnabled)" -ForegroundColor White
    
    if ($advancedSecurity.MasterUserOptions) {
        $masterUser = $advancedSecurity.MasterUserOptions
        if ($masterUser.MasterUserARN) {
            Write-Host "   Master User ARN: $($masterUser.MasterUserARN)" -ForegroundColor White
        }
        if ($masterUser.MasterUserName) {
            Write-Host "   Master User Name: $($masterUser.MasterUserName)" -ForegroundColor White
        }
    }
} else {
    Write-Host "   Fine-Grained Access Control: Disabled" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "สรุปและคำแนะนำ" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not $accessPolicies) {
    Write-Host "[ACTION REQUIRED] ต้องตั้งค่า Access Policy:" -ForegroundColor Red
    Write-Host "1. ไปที่ AWS Console > OpenSearch Service" -ForegroundColor Yellow
    Write-Host "2. เลือก domain: $DomainName" -ForegroundColor Yellow
    Write-Host "3. Security configuration > Edit access policy" -ForegroundColor Yellow
    Write-Host "4. ตั้งค่า policy ให้อนุญาตการเข้าถึง" -ForegroundColor Yellow
} elseif ($vpcOptions -and $vpcOptions.VPCId) {
    Write-Host "[INFO] Domain อยู่ใน VPC - ต้องเข้าถึงผ่าน VPC" -ForegroundColor Yellow
    Write-Host "   - ใช้ VPN หรือ Bastion host" -ForegroundColor White
    Write-Host "   - หรือตั้งค่า VPC endpoint" -ForegroundColor White
} else {
    Write-Host "[OK] Network configuration ดูถูกต้อง" -ForegroundColor Green
    Write-Host "   - ตรวจสอบ Access Policy ว่าอนุญาตการเข้าถึงหรือไม่" -ForegroundColor Yellow
}

Write-Host ""
$dashboardsUrl = "https://$($domainStatus.Endpoint)/_dashboards"
Write-Host "URL: $dashboardsUrl" -ForegroundColor Cyan
Write-Host ""

