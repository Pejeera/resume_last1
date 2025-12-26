#Requires -Version 5.1
<#
Deploy Lambda with Docker (Lambda Python Base Image)
Uses public.ecr.aws/lambda/python:3.11 to match Lambda environment

Usage:
PS> cd backend
PS> .\deploy_lambda_docker.ps1
#>

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2",
    [string]$BuildDir = "package",
    [string]$ZipFile = "lambda.zip"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploy Lambda with Docker (Lambda Base Image)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region  : $Region" -ForegroundColor Yellow
Write-Host "BuildDir: $BuildDir" -ForegroundColor Yellow
Write-Host ""

# Step 1: Clean old build
Write-Host "[1/5] Cleaning old build directory..." -ForegroundColor Green
if (Test-Path $BuildDir) {
    Remove-Item -Path $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "   Removed $BuildDir" -ForegroundColor Gray
}

if (Test-Path $ZipFile) {
    Remove-Item -Path $ZipFile -Force -ErrorAction SilentlyContinue
    Write-Host "   Removed $ZipFile" -ForegroundColor Gray
}

# Create new build directory
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
Write-Host "   Created $BuildDir" -ForegroundColor Green

# Step 2: Build dependencies with Docker (Lambda Python base image)
Write-Host "[2/5] Building dependencies with Docker (Lambda Python 3.11)..." -ForegroundColor Green

# Check Docker
$dockerAvailable = $false
try {
    docker --version | Out-Null
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerAvailable = $true
        Write-Host "   Docker is available" -ForegroundColor Green
    } else {
        Write-Host "   Docker daemon is not running" -ForegroundColor Red
        Write-Host "   Please start Docker Desktop and try again" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "   Docker not found" -ForegroundColor Red
    Write-Host "   Please install Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Use Lambda Python base image
$projectPath = (Get-Location).Path
$dockerWorkDir = "/var/task"

Write-Host "   Installing dependencies with Lambda Python base image..." -ForegroundColor Gray
Write-Host "   Image: public.ecr.aws/lambda/python:3.11" -ForegroundColor Gray
Write-Host "   Working Directory: $dockerWorkDir" -ForegroundColor Gray

# Build dependencies
# Override entrypoint to run pip directly
docker run --rm `
    -v "${projectPath}:${dockerWorkDir}" `
    -w $dockerWorkDir `
    --entrypoint /bin/bash `
    public.ecr.aws/lambda/python:3.11 `
    -c "pip install -r requirements.txt -t $BuildDir --quiet"

if ($LASTEXITCODE -ne 0) {
    Write-Host "   Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host "   Dependencies installed successfully" -ForegroundColor Green

# Step 3: Copy source code
Write-Host "[3/5] Copying source code..." -ForegroundColor Green

$sourceFiles = @("main.py", "lambda_function.py")
foreach ($file in $sourceFiles) {
    if (Test-Path $file) {
        Copy-Item -Path $file -Destination $BuildDir -Force
        Write-Host "   Copied $file" -ForegroundColor Gray
    } else {
        Write-Host "   File not found: $file" -ForegroundColor Yellow
    }
}

# Copy app/ directory
if (Test-Path "app") {
    Copy-Item -Path "app" -Destination $BuildDir -Recurse -Force
    Write-Host "   Copied app/ directory" -ForegroundColor Gray
} else {
    Write-Host "   Directory not found: app/" -ForegroundColor Yellow
}

# Step 4: Cleanup - Remove unnecessary files
Write-Host "[4/5] Cleanup - Removing unnecessary files..." -ForegroundColor Green

# Remove dist-info, tests, __pycache__
Get-ChildItem -Path $BuildDir -Recurse -Directory -Filter "*.dist-info" -ErrorAction SilentlyContinue | 
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path $BuildDir -Recurse -Directory | Where-Object {
    $_.Name -in @("tests", "test", "__pycache__", ".pytest_cache")
} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path $BuildDir -Recurse -File | Where-Object {
    $_.Extension -in @(".pyc", ".pyo", ".pyd") -or
    ($_.Extension -eq ".txt" -and $_.Name -ne "requirements.txt")
} | Remove-Item -Force -ErrorAction SilentlyContinue

# Remove AWS SDK (already in Lambda runtime)
$awsSdkPkgs = @("boto3", "botocore", "s3transfer")
foreach ($pkg in $awsSdkPkgs) {
    $pkgPath = Join-Path $BuildDir $pkg
    if (Test-Path $pkgPath) {
        Remove-Item -Path $pkgPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "   Removed $pkg (already in Lambda runtime)" -ForegroundColor Gray
    }
}

# Check and remove forbidden files at root level
$forbiddenFiles = @("http.py", "typing.py")
foreach ($file in $forbiddenFiles) {
    $filePath = Join-Path $BuildDir $file
    if (Test-Path $filePath) {
        Write-Host "   Found forbidden file: $filePath" -ForegroundColor Yellow
        Remove-Item -Path $filePath -Force -ErrorAction SilentlyContinue
        Write-Host "   Removed $filePath" -ForegroundColor Green
    }
}

Write-Host "   Cleanup completed" -ForegroundColor Green

# Step 5: Zip and deploy
Write-Host "[5/5] Creating zip and deploying..." -ForegroundColor Green

# Create zip from package directory contents
Push-Location $BuildDir
try {
    $itemsCount = (Get-ChildItem -Recurse).Count
    Write-Host "   Zipping $itemsCount items..." -ForegroundColor Gray
    
    Compress-Archive `
        -Path * `
        -DestinationPath (Join-Path ".." $ZipFile) `
        -Force
} finally {
    Pop-Location
}

if (-not (Test-Path $ZipFile)) {
    Write-Host "   Failed to create zip" -ForegroundColor Red
    exit 1
}

$zipSizeMB = [math]::Round((Get-Item $ZipFile).Length / 1MB, 2)
Write-Host "   Zip created successfully: $ZipFile ($zipSizeMB MB)" -ForegroundColor Green

# Verify zip contents for forbidden files
Write-Host "   Verifying zip contents..." -ForegroundColor Gray
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $ZipFile).Path)

$forbiddenFound = $false
foreach ($entry in $zip.Entries) {
    $fileName = Split-Path $entry.FullName -Leaf
    # Check only root level files
    if ($fileName -in $forbiddenFiles -and $entry.FullName -notmatch '[\\/]') {
        Write-Host "   Found forbidden file at root level: $($entry.FullName)" -ForegroundColor Red
        $forbiddenFound = $true
    }
}
$zip.Dispose()

if ($forbiddenFound) {
    Write-Host "   Zip contains forbidden files - DO NOT DEPLOY!" -ForegroundColor Red
    exit 1
}

Write-Host "   Zip verification passed" -ForegroundColor Green

# Deploy to Lambda
Write-Host ""
Write-Host "Deploying to Lambda..." -ForegroundColor Cyan
aws lambda update-function-code `
    --function-name $FunctionName `
    --zip-file "fileb://$ZipFile" `
    --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "   Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "   Deployment successful!" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Zip file: $ZipFile ($zipSizeMB MB)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Wait ~10-30 seconds for Lambda to initialize" -ForegroundColor Yellow
Write-Host "2. Test API: python test_api_server.py" -ForegroundColor Yellow
Write-Host "3. Check CloudWatch Logs if there are issues" -ForegroundColor Yellow
Write-Host ""
