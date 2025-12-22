# Script to check Lambda IAM role permissions for OpenSearch
param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1",
    [string]$OpenSearchDomainArn = "arn:aws:es:ap-southeast-2:533267343789:domain/resume-search-dev"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ตรวจสอบ Lambda IAM Role Permissions" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get Lambda function configuration
Write-Host "[1/3] กำลังดึงข้อมูล Lambda function..." -ForegroundColor Green
try {
    $lambdaConfig = aws lambda get-function-configuration `
        --function-name $FunctionName `
        --region $Region `
        --output json | ConvertFrom-Json
    
    $roleArn = $lambdaConfig.Role
    Write-Host "   Lambda Role ARN: $roleArn" -ForegroundColor White
    
    # Extract role name from ARN
    $roleName = $roleArn.Split('/')[-1]
    Write-Host "   Role Name: $roleName" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "   [ERROR] ไม่สามารถดึงข้อมูล Lambda: $_" -ForegroundColor Red
    exit 1
}

# Get IAM role policies
Write-Host "[2/3] กำลังตรวจสอบ IAM Role policies..." -ForegroundColor Green
try {
    # Get attached policies
    $attachedPolicies = aws iam list-attached-role-policies `
        --role-name $roleName `
        --output json | ConvertFrom-Json
    
    Write-Host "   Attached Policies:" -ForegroundColor Yellow
    foreach ($policy in $attachedPolicies.AttachedPolicies) {
        Write-Host "     - $($policy.PolicyName) ($($policy.PolicyArn))" -ForegroundColor White
        
        # Get policy document
        $policyDoc = aws iam get-policy `
            --policy-arn $policy.PolicyArn `
            --output json | ConvertFrom-Json
        
        $policyVersion = aws iam get-policy-version `
            --policy-arn $policy.PolicyArn `
            --version-id $policyDoc.Policy.DefaultVersionId `
            --output json | ConvertFrom-Json
        
        $policyDocument = $policyVersion.PolicyVersion.Document | ConvertFrom-Json
        
        # Check if policy allows es:* actions
        $hasOpenSearchAccess = $false
        foreach ($statement in $policyDocument.Statement) {
            if ($statement.Effect -eq "Allow") {
                $actions = if ($statement.Action) { 
                    if ($statement.Action -is [array]) { $statement.Action } else { @($statement.Action) }
                } else { @() }
                
                $resources = if ($statement.Resource) {
                    if ($statement.Resource -is [array]) { $statement.Resource } else { @($statement.Resource) }
                } else { @() }
                
                foreach ($action in $actions) {
                    if ($action -match "es:\*" -or $action -match "es:.*") {
                        foreach ($resource in $resources) {
                            if ($resource -match "opensearch" -or $resource -match "es:" -or $resource -eq "*") {
                                $hasOpenSearchAccess = $true
                                Write-Host "       [OK] Policy allows: $action on $resource" -ForegroundColor Green
                            }
                        }
                    }
                }
            }
        }
        
        if (-not $hasOpenSearchAccess) {
            Write-Host "       [WARNING] Policy ไม่มีสิทธิ์เข้าถึง OpenSearch" -ForegroundColor Yellow
        }
    }
    
    Write-Host ""
    
    # Get inline policies
    $inlinePolicies = aws iam list-role-policies `
        --role-name $roleName `
        --output json | ConvertFrom-Json
    
    if ($inlinePolicies.PolicyNames.Count -gt 0) {
        Write-Host "   Inline Policies:" -ForegroundColor Yellow
        foreach ($policyName in $inlinePolicies.PolicyNames) {
            Write-Host "     - $policyName" -ForegroundColor White
            
            $inlinePolicyDoc = aws iam get-role-policy `
                --role-name $roleName `
                --policy-name $policyName `
                --output json | ConvertFrom-Json
            
            $policyDocument = $inlinePolicyDoc.PolicyDocument | ConvertFrom-Json
            
            # Check for OpenSearch permissions
            $hasOpenSearchAccess = $false
            foreach ($statement in $policyDocument.Statement) {
                if ($statement.Effect -eq "Allow") {
                    $actions = if ($statement.Action) { 
                        if ($statement.Action -is [array]) { $statement.Action } else { @($statement.Action) }
                    } else { @() }
                    
                    foreach ($action in $actions) {
                        if ($action -match "es:\*" -or $action -match "es:.*") {
                            $hasOpenSearchAccess = $true
                            Write-Host "       [OK] Inline policy allows: $action" -ForegroundColor Green
                        }
                    }
                }
            }
            
            if (-not $hasOpenSearchAccess) {
                Write-Host "       [WARNING] Inline policy ไม่มีสิทธิ์เข้าถึง OpenSearch" -ForegroundColor Yellow
            }
        }
    }
    
    Write-Host ""
} catch {
    Write-Host "   [ERROR] ไม่สามารถตรวจสอบ IAM policies: $_" -ForegroundColor Red
}

# Recommendations
Write-Host "[3/3] คำแนะนำ:" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "ถ้า Lambda IAM role ไม่มีสิทธิ์เข้าถึง OpenSearch:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. เพิ่ม policy ให้ Lambda role:" -ForegroundColor White
Write-Host "   aws iam attach-role-policy \" -ForegroundColor Gray
Write-Host "     --role-name $roleName \" -ForegroundColor Gray
Write-Host "     --policy-arn arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess" -ForegroundColor Gray
Write-Host ""
Write-Host "   หรือสร้าง custom policy:" -ForegroundColor White
Write-Host "   {" -ForegroundColor Gray
Write-Host "     \"Version\": \"2012-10-17\"," -ForegroundColor Gray
Write-Host "     \"Statement\": [" -ForegroundColor Gray
Write-Host "       {" -ForegroundColor Gray
Write-Host "         \"Effect\": \"Allow\"," -ForegroundColor Gray
Write-Host "         \"Action\": \"es:*\"," -ForegroundColor Gray
Write-Host "         \"Resource\": \"$OpenSearchDomainArn/*\"" -ForegroundColor Gray
Write-Host "       }" -ForegroundColor Gray
Write-Host "     ]" -ForegroundColor Gray
Write-Host "   }" -ForegroundColor Gray
Write-Host ""
Write-Host "2. ตรวจสอบ OpenSearch Access Policy:" -ForegroundColor White
Write-Host "   - ต้องอนุญาต Lambda role ARN: $roleArn" -ForegroundColor Gray
Write-Host ""
Write-Host "3. หลังจากเพิ่ม permissions:" -ForegroundColor White
Write-Host "   - รอ ~1-2 นาที" -ForegroundColor Gray
Write-Host "   - ทดสอบอีกครั้ง: python backend/test_opensearch_lambda.py" -ForegroundColor Gray
Write-Host ""

