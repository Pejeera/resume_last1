# Add Cognito Permissions to Lambda IAM Role
# Usage: .\add_cognito_permissions.ps1

param(
    [Parameter(Mandatory=$false)]
    [string]$RoleName = "resume-search-api-role-828wgmlp",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-southeast-2",
    
    [Parameter(Mandatory=$false)]
    [string]$UserPoolId = "ap-southeast-2_bKxx54EbY"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Adding Cognito Permissions to Lambda Role" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Role Name: $RoleName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "User Pool ID: $UserPoolId" -ForegroundColor Yellow
Write-Host ""

# Get account ID from role ARN or from AWS
try {
    $roleInfo = aws iam get-role --role-name $RoleName --query 'Role.[Arn,AccountId]' --output json 2>&1 | ConvertFrom-Json
    $accountId = $roleInfo[1]
    if (-not $accountId) {
        # Try to extract from ARN
        $arn = $roleInfo[0]
        if ($arn -match 'arn:aws:iam::(\d+):') {
            $accountId = $matches[1]
        }
    }
} catch {
    # Try alternative method
    $roleArn = aws iam get-role --role-name $RoleName --query 'Role.Arn' --output text 2>&1
    if ($roleArn -match 'arn:aws:iam::(\d+):') {
        $accountId = $matches[1]
    } else {
        Write-Host "ERROR: Could not determine AWS Account ID" -ForegroundColor Red
        exit 1
    }
}

if (-not $accountId) {
    Write-Host "ERROR: Could not determine AWS Account ID" -ForegroundColor Red
    exit 1
}

Write-Host "AWS Account ID: $accountId" -ForegroundColor Green
Write-Host ""

# Create policy document (as JSON string to avoid encoding issues)
$resourceArn = "arn:aws:cognito-idp:${Region}:${accountId}:userpool/${UserPoolId}"
$policyJson = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:InitiateAuth",
        "cognito-idp:AdminGetUser",
        "cognito-idp:DescribeUserPoolClient"
      ],
      "Resource": "$resourceArn"
    }
  ]
}
"@

$policyName = "CognitoAccessPolicy"
$policyFile = "cognito-policy-temp.json"

# Save policy to file (ASCII encoding)
$policyJson | Out-File -FilePath $policyFile -Encoding ASCII -NoNewline

Write-Host "[Step 1] Creating inline policy for Cognito access..." -ForegroundColor Green

try {
    # Try to put inline policy
    aws iam put-role-policy `
        --role-name $RoleName `
        --policy-name $policyName `
        --policy-document "file://$policyFile" `
        2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Policy '$policyName' added successfully!" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Failed to add inline policy. Trying to attach managed policy..." -ForegroundColor Yellow
        
        # Alternative: Create and attach a managed policy
        $managedPolicyArn = "arn:aws:iam::$accountId`:policy/$policyName"
        
        # Check if policy exists
        $existingPolicy = aws iam get-policy --policy-arn $managedPolicyArn 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            # Create new managed policy
            Write-Host "Creating managed policy..." -ForegroundColor Yellow
            $createResult = aws iam create-policy `
                --policy-name $policyName `
                --policy-document "file://$policyFile" `
                --description "Allows Lambda to access Cognito User Pool" `
                2>&1
            
            if ($LASTEXITCODE -eq 0) {
                $managedPolicyArn = ($createResult | ConvertFrom-Json).Policy.Arn
                Write-Host "[OK] Managed policy created: $managedPolicyArn" -ForegroundColor Green
            } else {
                Write-Host "[ERROR] Failed to create managed policy" -ForegroundColor Red
                Write-Host $createResult -ForegroundColor Yellow
                exit 1
            }
        } else {
            # Update existing policy
            Write-Host "Updating existing managed policy..." -ForegroundColor Yellow
            $policyVersion = aws iam create-policy-version `
                --policy-arn $managedPolicyArn `
                --policy-document "file://$policyFile" `
                --set-as-default `
                2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Managed policy updated" -ForegroundColor Green
            }
        }
        
        # Attach policy to role
        Write-Host "Attaching policy to role..." -ForegroundColor Yellow
        aws iam attach-role-policy `
            --role-name $RoleName `
            --policy-arn $managedPolicyArn `
            2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Policy attached to role successfully!" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to attach policy" -ForegroundColor Red
            exit 1
        }
    }
    
    # Clean up temp file
    Remove-Item -Path $policyFile -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "[SUCCESS] Cognito permissions added!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Lambda can now:" -ForegroundColor Yellow
    Write-Host "  - Initiate authentication with Cognito" -ForegroundColor Gray
    Write-Host "  - Get user information from Cognito" -ForegroundColor Gray
    Write-Host "  - Describe Cognito client configuration" -ForegroundColor Gray
    Write-Host ""
    
} catch {
    Write-Host "[ERROR] Failed to add Cognito permissions" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

