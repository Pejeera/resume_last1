# Script to add OpenSearch permissions to Lambda IAM role
param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2",
    [string]$OpenSearchDomainArn = "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "เพิ่ม OpenSearch Permissions ให้ Lambda Role" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get Lambda role
Write-Host "[1/3] กำลังดึงข้อมูล Lambda role..." -ForegroundColor Green
try {
    $lambdaConfig = aws lambda get-function-configuration `
        --function-name $FunctionName `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $roleArn = $lambdaConfig.Role
    $roleName = $roleArn.Split('/')[-1]
    
    Write-Host "   Role ARN: $roleArn" -ForegroundColor White
    Write-Host "   Role Name: $roleName" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "   [ERROR] ไม่สามารถดึงข้อมูล Lambda: $_" -ForegroundColor Red
    exit 1
}

# Option 1: Attach managed policy
Write-Host "[2/3] กำลังเพิ่ม managed policy..." -ForegroundColor Green
try {
    aws iam attach-role-policy `
        --role-name $roleName `
        --policy-arn arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess
    
    Write-Host "   [OK] เพิ่ม AmazonOpenSearchServiceFullAccess policy แล้ว" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   [WARNING] ไม่สามารถเพิ่ม managed policy: $_" -ForegroundColor Yellow
    Write-Host "   (อาจมี policy นี้อยู่แล้ว)" -ForegroundColor Gray
    Write-Host ""
}

# Option 2: Create and attach custom policy
Write-Host "[3/3] กำลังสร้าง custom policy (ถ้ายังไม่มี)..." -ForegroundColor Green
$policyName = "resume-search-api-OpenSearch-Policy"

try {
    # Check if policy exists
    $existingPolicy = aws iam get-role-policy `
        --role-name $roleName `
        --policy-name $policyName `
        --output json 2>$null | ConvertFrom-Json
    
    if ($existingPolicy) {
        Write-Host "   [INFO] Policy $policyName มีอยู่แล้ว" -ForegroundColor Yellow
    }
} catch {
    # Policy doesn't exist, create it
    $policyDocument = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Effect = "Allow"
                Action = @("es:*")
                Resource = "$OpenSearchDomainArn/*"
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $policyFile = "opensearch-policy.json"
    $policyDocument | Out-File -FilePath $policyFile -Encoding utf8
    
    try {
        aws iam put-role-policy `
            --role-name $roleName `
            --policy-name $policyName `
            --policy-document file://$policyFile
        
        Write-Host "   [OK] สร้าง custom policy $policyName แล้ว" -ForegroundColor Green
        Remove-Item $policyFile -ErrorAction SilentlyContinue
    } catch {
        Write-Host "   [ERROR] ไม่สามารถสร้าง custom policy: $_" -ForegroundColor Red
        Remove-Item $policyFile -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "สรุป" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[NEXT STEPS] ตรวจสอบ OpenSearch Access Policy:" -ForegroundColor Yellow
Write-Host "1. ไปที่ AWS Console > OpenSearch Service" -ForegroundColor White
Write-Host "2. เลือก domain: resume-search-dev" -ForegroundColor White
Write-Host "3. Security configuration > Edit access policy" -ForegroundColor White
Write-Host "4. ตรวจสอบว่า policy อนุญาต role: $roleArn" -ForegroundColor White
Write-Host ""
Write-Host "ตัวอย่าง Access Policy:" -ForegroundColor Yellow
Write-Host '{' -ForegroundColor Gray
Write-Host '  "Version": "2012-10-17",' -ForegroundColor Gray
Write-Host '  "Statement": [' -ForegroundColor Gray
Write-Host '    {' -ForegroundColor Gray
Write-Host '      "Effect": "Allow",' -ForegroundColor Gray
Write-Host "      `"Principal`": { `"AWS`": `"$roleArn`" }," -ForegroundColor Gray
Write-Host '      "Action": "es:*",' -ForegroundColor Gray
Write-Host "      `"Resource`": `"$OpenSearchDomainArn/*`"" -ForegroundColor Gray
Write-Host '    }' -ForegroundColor Gray
Write-Host '  ]' -ForegroundColor Gray
Write-Host '}' -ForegroundColor Gray
Write-Host ""
Write-Host "หลังจากแก้ไข:" -ForegroundColor Yellow
Write-Host "  - รอ ~1-2 นาที" -ForegroundColor White
Write-Host "  - ทดสอบ: python backend/test_opensearch_lambda.py" -ForegroundColor White
Write-Host ""

