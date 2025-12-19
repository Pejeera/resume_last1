<#
Script to update Lambda environment variables for OpenSearch master user credentials
Usage:
    .\update_opensearch_credentials.ps1 -OpenSearchUsername "admin" `
                                        -OpenSearchPassword "your-password" `
                                        -OpenSearchEndpoint "https://search-xxx.us-east-1.es.amazonaws.com"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OpenSearchUsername,
    
    [Parameter(Mandatory=$true)]
    [string]$OpenSearchPassword,
    
    [Parameter(Mandatory=$true)]
    [string]$OpenSearchEndpoint,
    
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1",
    [string]$AWSRegion = "us-east-1",
    [string]$S3BucketName = "resume-matching-533267343789",
    [string]$S3Prefix = "resumes/",
    [string]$OpenSearchUseSSL = "true",
    [string]$OpenSearchVerifyCerts = "true",
    [string]$UseMock = "false"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Updating Lambda Environment Variables" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region  : $Region" -ForegroundColor Yellow
Write-Host ""

# Get current environment variables
Write-Host "[1/2] Getting current Lambda configuration..." -ForegroundColor Green
$currentConfig = aws lambda get-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --query 'Environment.Variables' `
    --output json | ConvertFrom-Json

# Merge with new variables
$envVars = @{}
foreach ($key in $currentConfig.PSObject.Properties.Name) {
    $envVars[$key] = $currentConfig.$key
}

# Add/Update OpenSearch and S3 variables
$envVars["OPENSEARCH_ENDPOINT"] = $OpenSearchEndpoint
$envVars["OPENSEARCH_USERNAME"] = $OpenSearchUsername
$envVars["OPENSEARCH_PASSWORD"] = $OpenSearchPassword
$envVars["OPENSEARCH_USE_SSL"] = $OpenSearchUseSSL
$envVars["OPENSEARCH_VERIFY_CERTS"] = $OpenSearchVerifyCerts
$envVars["S3_BUCKET_NAME"] = $S3BucketName
$envVars["S3_PREFIX"] = $S3Prefix
$envVars["AWS_REGION"] = $AWSRegion
$envVars["USE_MOCK"] = $UseMock

# Convert to JSON format for AWS CLI
$envVarsJson = ($envVars.GetEnumerator() | ForEach-Object { 
    "$($_.Key)=$($_.Value)" 
}) -join ","

Write-Host "[2/2] Updating Lambda environment variables..." -ForegroundColor Green
$result = aws lambda update-function-configuration `
    --function-name $FunctionName `
    --region $Region `
    --environment "Variables={$envVarsJson}" `
    --output json | ConvertFrom-Json

Write-Host ""
Write-Host "Environment variables updated successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Updated variables:" -ForegroundColor Yellow
Write-Host "  - OPENSEARCH_ENDPOINT: $OpenSearchEndpoint" -ForegroundColor White
Write-Host "  - OPENSEARCH_USERNAME: $OpenSearchUsername" -ForegroundColor White
Write-Host "  - OPENSEARCH_PASSWORD: [HIDDEN]" -ForegroundColor White
Write-Host "  - S3_BUCKET_NAME: $S3BucketName" -ForegroundColor White
Write-Host "  - AWS_REGION: $AWSRegion" -ForegroundColor White
Write-Host "  - USE_MOCK: $UseMock" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Wait ~10 seconds for Lambda to update" -ForegroundColor Yellow
Write-Host "2. Test API: python test_api_server.py" -ForegroundColor Yellow
Write-Host "3. Check CloudWatch Logs if there are issues" -ForegroundColor Yellow
Write-Host ""

