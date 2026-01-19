# Fix S3 Delete Permission for Lambda IAM Role
# This script adds s3:DeleteObject permission to the Lambda IAM role

param(
    [string]$RoleName = "resume-search-api-role-828wgmlp",
    [string]$BucketName = "resume-matching-533267343789",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Fix S3 Delete Permission for Lambda Role" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Role Name: $RoleName" -ForegroundColor Yellow
Write-Host "Bucket Name: $BucketName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host ""

# Get current role policy
Write-Host "[Step 1] Getting current IAM role policy..." -ForegroundColor Cyan
try {
    $role = aws iam get-role --role-name $RoleName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   [ERROR] Role not found: $RoleName" -ForegroundColor Red
        Write-Host "   Please check the role name" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "   [OK] Role found" -ForegroundColor Green
} catch {
    Write-Host "   [ERROR] Failed to get role: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Get attached policies
Write-Host ""
Write-Host "[Step 2] Checking attached policies..." -ForegroundColor Cyan
try {
    $attachedPolicies = aws iam list-attached-role-policies --role-name $RoleName 2>&1 | ConvertFrom-Json
    Write-Host "   Found $($attachedPolicies.AttachedPolicies.Count) attached policy(ies)" -ForegroundColor Green
    
    foreach ($policy in $attachedPolicies.AttachedPolicies) {
        Write-Host "   - $($policy.PolicyName) ($($policy.PolicyArn))" -ForegroundColor Gray
    }
} catch {
    Write-Host "   [WARNING] Failed to list attached policies: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Get inline policies
Write-Host ""
Write-Host "[Step 3] Checking inline policies..." -ForegroundColor Cyan
try {
    $inlinePolicies = aws iam list-role-policies --role-name $RoleName 2>&1 | ConvertFrom-Json
    Write-Host "   Found $($inlinePolicies.PolicyNames.Count) inline policy(ies)" -ForegroundColor Green
    
    foreach ($policyName in $inlinePolicies.PolicyNames) {
        Write-Host "   - $policyName" -ForegroundColor Gray
    }
} catch {
    Write-Host "   [WARNING] Failed to list inline policies: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[Step 4] Creating/Updating inline policy with S3 delete permission..." -ForegroundColor Cyan

# Create policy document
$policyDocument = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Effect = "Allow"
            Action = @(
                "s3:DeleteObject",
                "s3:DeleteObjectVersion"
            )
            Resource = "arn:aws:s3:::$BucketName/resumes/*"
        }
    )
} | ConvertTo-Json -Depth 10

# Save to temp file
$tempPolicyFile = "s3-delete-policy-$(Get-Date -Format 'yyyyMMddHHmmss').json"
$policyDocument | Out-File -FilePath $tempPolicyFile -Encoding utf8

Write-Host "   Policy document:" -ForegroundColor Gray
Write-Host $policyDocument -ForegroundColor Gray
Write-Host ""

# Apply policy
$policyName = "S3DeleteObjectPolicy"
try {
    Write-Host "   Applying policy as inline policy: $policyName" -ForegroundColor Yellow
    aws iam put-role-policy `
        --role-name $RoleName `
        --policy-name $policyName `
        --policy-document "file://$tempPolicyFile" `
        2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Policy applied successfully!" -ForegroundColor Green
    } else {
        Write-Host "   [ERROR] Failed to apply policy" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   [ERROR] Failed to apply policy: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    # Clean up temp file
    if (Test-Path $tempPolicyFile) {
        Remove-Item $tempPolicyFile -Force
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ S3 Delete Permission Added!" -ForegroundColor Green
Write-Host ""
Write-Host "The Lambda function can now delete objects from S3." -ForegroundColor Yellow
Write-Host "Note: It may take a few seconds for the permission to propagate." -ForegroundColor Gray
Write-Host ""
Write-Host "To verify, check the role in AWS Console:" -ForegroundColor Yellow
Write-Host "https://console.aws.amazon.com/iam/home?region=$Region#/roles/$RoleName" -ForegroundColor White
Write-Host ""
