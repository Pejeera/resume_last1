# Build Lambda package with Docker (Linux-compatible)
# Usage: .\build_with_docker.ps1

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building Lambda Package with Docker" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "[1/3] Checking Docker..." -ForegroundColor Yellow
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Docker daemon is not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Attempting to start Docker Desktop..." -ForegroundColor Cyan
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
        Write-Host "Waiting 30 seconds for Docker to start..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        
        docker ps 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Docker still not running. Please start it manually." -ForegroundColor Red
            exit 1
        }
    }
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not installed or not accessible" -ForegroundColor Red
    exit 1
}

# Clean build directory
Write-Host ""
Write-Host "[2/3] Cleaning build directory..." -ForegroundColor Yellow
$buildDir = "lambda-package"
if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$pythonDir = Join-Path $buildDir "python"
New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null

# Build with Docker
Write-Host ""
Write-Host "[3/3] Building with Docker (Linux Python 3.10)..." -ForegroundColor Yellow
$projectPath = (Get-Location).Path
$dockerWorkDir = "/var/task"
$volumePath = "${projectPath}:${dockerWorkDir}"

Write-Host "Installing dependencies in Docker container..." -ForegroundColor Cyan
docker run --rm `
    -v "${volumePath}" `
    -w $dockerWorkDir `
    python:3.10-slim `
    /bin/bash -c "pip install -r requirements.txt -t $buildDir/python/ --quiet --no-cache-dir"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install dependencies via Docker" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# Copy source files
Write-Host "Copying source files..." -ForegroundColor Cyan
Copy-Item -Path "main.py" -Destination $buildDir -Force
Copy-Item -Path "lambda_handler_mangum.py" -Destination $buildDir -Force
Copy-Item -Path "app" -Destination $buildDir -Recurse -Force

# Remove AWS SDK (provided by Lambda)
Write-Host "Removing AWS SDK (provided by Lambda runtime)..." -ForegroundColor Cyan
$awsPackages = @("boto3", "botocore", "s3transfer")
foreach ($pkg in $awsPackages) {
    $pkgPath = Join-Path $pythonDir $pkg
    if (Test-Path $pkgPath) {
        Remove-Item -Path $pkgPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Remove __pycache__ directories
Write-Host "Cleaning up cache files..." -ForegroundColor Cyan
Get-ChildItem -Path $buildDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Create zip
Write-Host "Creating deployment package..." -ForegroundColor Cyan
$zipFile = "lambda-deployment-clean.zip"
if (Test-Path $zipFile) {
    Remove-Item -Path $zipFile -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($buildDir, $zipFile)

$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host "[OK] Package created: $zipFile ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green

# Deploy
Write-Host ""
Write-Host "Deploying to Lambda..." -ForegroundColor Cyan
aws lambda update-function-code `
    --function-name $FunctionName `
    --region $Region `
    --zip-file "fileb://$zipFile" `
    2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Waiting 5 seconds for Lambda to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "[SUCCESS] Build and deployment completed!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    exit 1
}

