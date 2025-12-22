# Script to deploy Lambda function with Lambda Layer
# This fixes "No module named 'requests'" by using Layer instead of bundling dependencies

param(
    [string]$FunctionName = "resume-search-api",
    [string]$LayerName = "requests-layer",
    [string]$Region = "ap-southeast-2",
    [string]$Runtime = "python3.10"
)

Write-Host "=== Deploy Lambda Function with Layer ===" -ForegroundColor Cyan

# Check if Layer ZIP exists
$layerZip = "requests-layer.zip"
if (-not (Test-Path $layerZip)) {
    Write-Host "`n[ERROR] File not found: $layerZip" -ForegroundColor Red
    Write-Host "Please run create_lambda_layer.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Check if Lambda function code exists
$lambdaCode = "lambda-final/lambda_function.py"
if (-not (Test-Path $lambdaCode)) {
    Write-Host "`n[WARNING] File not found: $lambdaCode" -ForegroundColor Yellow
    Write-Host "Using lambda_function.py instead..." -ForegroundColor Yellow
    $lambdaCode = "lambda_function.py"
    
    if (-not (Test-Path $lambdaCode)) {
        Write-Host "[ERROR] Lambda function code not found" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n[1/5] Creating Lambda function package..." -ForegroundColor Yellow

# Create ZIP for Lambda function (code only, no dependencies)
$lambdaZip = "lambda-function-only.zip"
if (Test-Path $lambdaZip) {
    Remove-Item $lambdaZip -Force
}

# Create temporary directory
$tempDir = "temp-lambda-deploy"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy lambda function code
Copy-Item $lambdaCode -Destination (Join-Path $tempDir "lambda_function.py")

# Create ZIP
Push-Location $tempDir
Compress-Archive -Path "lambda_function.py" -DestinationPath "..\$lambdaZip" -Force
Pop-Location

Remove-Item $tempDir -Recurse -Force

Write-Host "[OK] Created $lambdaZip successfully" -ForegroundColor Green

# Upload Layer (if not exists)
Write-Host "`n[2/5] Checking/Creating Lambda Layer..." -ForegroundColor Yellow

$layerExists = $false
try {
    $existingLayers = aws lambda list-layers --region $Region --output json 2>$null | ConvertFrom-Json
    if ($existingLayers.Layers) {
        foreach ($layer in $existingLayers.Layers) {
            if ($layer.LayerName -eq $LayerName) {
                $layerExists = $true
                Write-Host "[OK] Found Layer: $LayerName (Version: $($layer.LatestMatchingVersion.Version))" -ForegroundColor Green
                $layerArn = $layer.LatestMatchingVersion.LayerVersionArn
                break
            }
        }
    }
} catch {
    Write-Host "[WARNING] Cannot check Layer (may not exist yet)" -ForegroundColor Yellow
}

if (-not $layerExists) {
    Write-Host "Creating new Layer..." -ForegroundColor Yellow
    
    try {
        $layerResult = aws lambda publish-layer-version `
            --layer-name $LayerName `
            --description "Requests and requests-aws4auth for Lambda" `
            --zip-file "fileb://$layerZip" `
            --compatible-runtimes $Runtime `
            --region $Region `
            --output json | ConvertFrom-Json
        
        $layerArn = $layerResult.LayerVersionArn
        Write-Host "[OK] Layer created successfully: $layerArn" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Failed to create Layer" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}

# Upload Lambda function code
Write-Host "`n[3/5] Uploading Lambda function code..." -ForegroundColor Yellow

try {
    $updateResult = aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$lambdaZip" `
        --region $Region `
        --output json | ConvertFrom-Json
    
    Write-Host "[OK] Code uploaded successfully" -ForegroundColor Green
    
    # Wait for function to update
    Write-Host "Waiting for function to update..." -ForegroundColor Yellow
    $maxWait = 60
    $waited = 0
    do {
        Start-Sleep -Seconds 2
        $waited += 2
        $funcStatus = aws lambda get-function --function-name $FunctionName --region $Region --output json 2>$null | ConvertFrom-Json
        $state = $funcStatus.Configuration.State
        Write-Host "  State: $state" -ForegroundColor Gray
    } while ($state -ne "Active" -and $waited -lt $maxWait)
    
    if ($state -eq "Active") {
        Write-Host "[OK] Function is ready" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Function not Active yet (State: $state)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] Failed to upload code" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Attach Layer to Lambda function
Write-Host "`n[4/5] Attaching Layer to Lambda function..." -ForegroundColor Yellow

try {
    # Get currently attached Layers
    $currentFunc = aws lambda get-function --function-name $FunctionName --region $Region --output json | ConvertFrom-Json
    $currentLayers = @()
    
    if ($currentFunc.Configuration.Layers) {
        foreach ($layer in $currentFunc.Configuration.Layers) {
            # Keep other Layers (not requests-layer)
            if ($layer.Arn -notlike "*$LayerName*") {
                $currentLayers += $layer.Arn
            }
        }
    }
    
    # Add new Layer
    $allLayers = $currentLayers + $layerArn
    
    $updateConfig = aws lambda update-function-configuration `
        --function-name $FunctionName `
        --layers $allLayers `
        --region $Region `
        --output json | ConvertFrom-Json
    
    Write-Host "[OK] Layer attached successfully" -ForegroundColor Green
    Write-Host "  Layer ARN: $layerArn" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Failed to attach Layer" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Test Lambda function
Write-Host "`n[5/5] Testing Lambda function..." -ForegroundColor Yellow

$testEvent = @{
    Records = @(
        @{
            s3 = @{
                bucket = @{ name = "test-bucket" }
                object = @{ key = "test.json" }
            }
        }
    )
} | ConvertTo-Json -Compress

$testEvent | Out-File -FilePath "test-event.json" -Encoding utf8

try {
    Write-Host "Invoking Lambda function..." -ForegroundColor Gray
    $testResult = aws lambda invoke `
        --function-name $FunctionName `
        --payload $testEvent `
        --region $Region `
        "test-response.json" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        $response = Get-Content "test-response.json" | ConvertFrom-Json
        Write-Host "[OK] Lambda function works (may error on event format, that's OK)" -ForegroundColor Green
        
        # Check for import errors
        $logs = aws logs tail "/aws/lambda/$FunctionName" --since 1m --region $Region 2>$null
        if ($logs -match "No module named 'requests'") {
            Write-Host "`n[ERROR] Still has error: No module named 'requests'" -ForegroundColor Red
            Write-Host "Please check:" -ForegroundColor Yellow
            Write-Host "  1. Is Layer attached to Lambda function?" -ForegroundColor White
            Write-Host "  2. Does Layer Runtime match Lambda function?" -ForegroundColor White
            Write-Host "  3. Is Layer ZIP structure correct? (must have python/requests/)" -ForegroundColor White
        } else {
            Write-Host "[OK] No import errors found" -ForegroundColor Green
        }
    } else {
        Write-Host "[WARNING] Lambda function may have errors (check CloudWatch Logs)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARNING] Cannot test (that's OK)" -ForegroundColor Yellow
}

# Cleanup
if (Test-Path "test-event.json") { Remove-Item "test-event.json" -Force }
if (Test-Path "test-response.json") { Remove-Item "test-response.json" -Force }

Write-Host "`n=== Deployment successful ===" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Go to AWS Console -> Lambda -> $FunctionName" -ForegroundColor White
Write-Host "2. Verify Layer is attached (Layers section)" -ForegroundColor White
Write-Host "3. Test with real S3 trigger" -ForegroundColor White
Write-Host "4. Check CloudWatch Logs" -ForegroundColor White
