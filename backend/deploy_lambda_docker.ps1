# Deploy Lambda using Docker to install Linux-compatible dependencies
$functionName = "ResumeMatchAPI"
$region = "us-east-1"
$zipFile = "lambda-deployment.zip"
$tempDir = "lambda-package"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Lambda Function (Docker)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $functionName" -ForegroundColor Yellow
Write-Host "Region: $region" -ForegroundColor Yellow
Write-Host ""

# Check if Docker is available
Write-Host "[0/5] Checking Docker..." -ForegroundColor Green
try {
    docker --version | Out-Null
    Write-Host "Docker is available" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker is not available. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Step 1: Clean up temp directory
Write-Host "[1/5] Cleaning up..." -ForegroundColor Green
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Step 2: Copy source files
Write-Host "[2/5] Copying source files..." -ForegroundColor Green
Copy-Item -Path "app" -Destination $tempDir -Recurse -Force
Copy-Item -Path "*.py" -Destination $tempDir -Force
Copy-Item -Path "requirements.txt" -Destination $tempDir -Force

# Step 3: Install dependencies using Docker (Linux)
Write-Host "[3/5] Installing dependencies (Linux) using Docker..." -ForegroundColor Green
$currentPath = (Get-Location).Path
$volumePath = "$currentPath\$tempDir"
docker run --rm `
    -v "${volumePath}:/var/task" `
    -w /var/task `
    --entrypoint /bin/bash `
    public.ecr.aws/lambda/python:3.11 `
    -c "pip install -r requirements.txt -t . --quiet"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Step 4: Create ZIP file (exclude unnecessary files)
Write-Host "[4/5] Creating deployment package..." -ForegroundColor Green
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force -ErrorAction SilentlyContinue
}

Set-Location $tempDir

# Exclude unnecessary files to reduce size
# IMPORTANT: Exclude files that conflict with Python built-in modules
$excludeFiles = @(
    "typing.py",      # Conflicts with built-in typing module
    "http.py",        # Conflicts with built-in http module
    "urllib.py",      # Conflicts with built-in urllib
    "email.py",       # Conflicts with built-in email
    "json.py",        # Conflicts with built-in json
    "collections.py", # Conflicts with built-in collections
    "six.py"          # Can cause issues
)

$excludePatterns = @(
    "*.dist-info",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "bin",
    "*.so",
    "*.a",
    "*.h",
    "*.c",
    "*.cpp",
    "*.hpp",
    "*.txt",  # Exclude README, LICENSE, etc. but keep requirements.txt
    "*.md",
    "*.rst",
    "*.in",
    "*.cfg",
    "*.toml",
    "*.yml",
    "*.yaml",
    "*.json",  # Exclude package.json, etc. but keep our configs
    "tests",
    "test",
    "*.test",
    "*.spec",
    "*.egg-info"
)

# Get all files excluding patterns
$filesToZip = Get-ChildItem -Recurse | Where-Object {
    $item = $_
    $exclude = $false
    
    # Always include requirements.txt
    if ($item.Name -eq "requirements.txt") {
        return $true
    }
    
    # Exclude conflicting files
    if ($excludeFiles -contains $item.Name) {
        Write-Host "Excluding conflicting file: $($item.Name)" -ForegroundColor Yellow
        return $false
    }
    
    # Check exclude patterns
    foreach ($pattern in $excludePatterns) {
        if ($item.Name -like $pattern -or $item.FullName -like "*\$pattern\*") {
            $exclude = $true
            break
        }
    }
    
    return -not $exclude
}

$filesToZip | Compress-Archive -DestinationPath "..\$zipFile" -Force
Set-Location ..

$zipSizeMB = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
Write-Host "Created: $zipFile ($zipSizeMB MB)" -ForegroundColor Green

if ($zipSizeMB -gt 50) {
    Write-Host "WARNING: ZIP file is large. Consider using S3 upload for files > 50MB" -ForegroundColor Yellow
}

# Step 5: Upload to Lambda (use S3 if file > 50MB)
Write-Host "[5/5] Uploading to Lambda..." -ForegroundColor Green
$zipSizeMB = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)

if ($zipSizeMB -gt 50) {
    Write-Host "File size > 50MB, using S3 upload method..." -ForegroundColor Yellow
    
    # Upload to S3 first
    $bucketName = "lambda-deployment-$(Get-Random -Minimum 1000 -Maximum 9999)"
    $s3Key = "lambda-deployments/$functionName-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
    
    Write-Host "Creating temporary S3 bucket: $bucketName" -ForegroundColor Yellow
    aws s3 mb "s3://$bucketName" --region $region 2>$null
    
    Write-Host "Uploading to S3..." -ForegroundColor Yellow
    aws s3 cp $zipFile "s3://$bucketName/$s3Key" --region $region
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to upload to S3" -ForegroundColor Red
        exit 1
    }
    
    # Update Lambda from S3
    Write-Host "Updating Lambda from S3..." -ForegroundColor Yellow
    aws lambda update-function-code `
        --function-name $functionName `
        --s3-bucket $bucketName `
        --s3-key $s3Key `
        --region $region
    
    # Cleanup S3
    Write-Host "Cleaning up S3..." -ForegroundColor Yellow
    aws s3 rm "s3://$bucketName/$s3Key" --region $region
    aws s3 rb "s3://$bucketName" --region $region 2>$null
} else {
    # Direct upload for smaller files
    aws lambda update-function-code `
        --function-name $functionName `
        --zip-file "fileb://$zipFile" `
        --region $region
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to update Lambda" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "Waiting for Lambda to update..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Test: python test_api_routes.py" -ForegroundColor Yellow
Write-Host "2. Check CloudWatch Logs if needed" -ForegroundColor Yellow

# Cleanup
Write-Host ""
Write-Host "Cleaning up temp directory..." -ForegroundColor Green
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

