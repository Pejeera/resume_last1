# Fix and Deploy Lambda - แก้ไขทุกอย่างให้อัตโนมัติ
# Usage: .\fix_and_deploy.ps1

param(
    [string]$FunctionName = "resume-search-api",
    [string]$Region = "ap-southeast-2"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Fix and Deploy Lambda - All-in-One" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Docker
Write-Host "[Step 1/4] Checking Docker..." -ForegroundColor Yellow
$dockerAvailable = $false
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        docker ps 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerAvailable = $true
            Write-Host "[OK] Docker is running" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Docker installed but daemon not running" -ForegroundColor Yellow
            Write-Host "Attempting to start Docker Desktop..." -ForegroundColor Yellow
            Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 10
            docker ps 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $dockerAvailable = $true
                Write-Host "[OK] Docker started successfully" -ForegroundColor Green
            }
        }
    }
} catch {
    Write-Host "[WARN] Docker not available" -ForegroundColor Yellow
}

if (-not $dockerAvailable) {
    Write-Host ""
    Write-Host "[INFO] Docker not available - will use alternative method" -ForegroundColor Cyan
    Write-Host "Using pip to install Linux-compatible wheels..." -ForegroundColor Cyan
}

# Step 2: Add Cognito Permissions (if not already added)
Write-Host ""
Write-Host "[Step 2/4] Checking Cognito permissions..." -ForegroundColor Yellow
$roleName = "resume-search-api-role-828wgmlp"
try {
    $policies = aws iam list-role-policies --role-name $roleName --region $Region 2>&1 | ConvertFrom-Json
    if ($policies.PolicyNames -contains "CognitoAccessPolicy") {
        Write-Host "[OK] Cognito permissions already added" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Adding Cognito permissions..." -ForegroundColor Yellow
        .\add_cognito_permissions.ps1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Cognito permissions added" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[WARN] Could not check Cognito permissions: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "[INFO] Attempting to add Cognito permissions..." -ForegroundColor Yellow
    .\add_cognito_permissions.ps1
}

# Step 3: Build dependencies with Docker or alternative method
Write-Host ""
Write-Host "[Step 3/4] Building Lambda package..." -ForegroundColor Yellow

if ($dockerAvailable) {
    # Use Docker
    Write-Host "[INFO] Using Docker to build Linux-compatible dependencies" -ForegroundColor Cyan
    .\deploy_lambda_clean.ps1 -FunctionName $FunctionName -Region $Region
} else {
    # Alternative: Use pip with --platform flag (if available) or download pre-built wheels
    Write-Host "[INFO] Building without Docker..." -ForegroundColor Cyan
    
    # Clean build directory
    $buildDir = "lambda-package"
    if (Test-Path $buildDir) {
        Remove-Item -Path $buildDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
    $pythonDir = Join-Path $buildDir "python"
    New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null
    
    # Try to use pip with --platform flag (requires pip >= 21.0)
    Write-Host "[INFO] Installing dependencies for Linux platform..." -ForegroundColor Cyan
    Write-Host "Note: This may take a few minutes..." -ForegroundColor Yellow
    
    # Use pip download to get Linux wheels
    $tempDir = "temp-wheels"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        # Download wheels for Linux
        pip download -r requirements.txt `
            --platform manylinux2014_x86_64 `
            --platform linux_x86_64 `
            --only-binary=:all: `
            --dest $tempDir `
            --no-deps 2>&1 | Out-Null
        
        # Install to python directory
        pip install -r requirements.txt `
            --target $pythonDir `
            --platform manylinux2014_x86_64 `
            --platform linux_x86_64 `
            --only-binary=:all: `
            --upgrade 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Dependencies installed" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Platform-specific install failed, trying regular install..." -ForegroundColor Yellow
            pip install -r requirements.txt --target $pythonDir --upgrade 2>&1 | Out-Null
        }
    } catch {
        Write-Host "[WARN] Could not install with platform flag, using regular install..." -ForegroundColor Yellow
        pip install -r requirements.txt --target $pythonDir --upgrade 2>&1 | Out-Null
    } finally {
        if (Test-Path $tempDir) {
            Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Copy source files
    Write-Host "[INFO] Copying source files..." -ForegroundColor Cyan
    Copy-Item -Path "main.py" -Destination $buildDir -Force
    Copy-Item -Path "lambda_handler_mangum.py" -Destination $buildDir -Force
    Copy-Item -Path "app" -Destination $buildDir -Recurse -Force
    
    # Remove AWS SDK (provided by Lambda)
    $awsPackages = @("boto3", "botocore", "s3transfer")
    foreach ($pkg in $awsPackages) {
        $pkgPath = Join-Path $pythonDir $pkg
        if (Test-Path $pkgPath) {
            Remove-Item -Path $pkgPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Create zip
    Write-Host "[INFO] Creating deployment package..." -ForegroundColor Cyan
    $zipFile = "lambda-deployment-clean.zip"
    if (Test-Path $zipFile) {
        Remove-Item -Path $zipFile -Force
    }
    
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($buildDir, $zipFile)
    
    Write-Host "[OK] Package created: $zipFile" -ForegroundColor Green
    
    # Deploy
    Write-Host "[INFO] Deploying to Lambda..." -ForegroundColor Cyan
    aws lambda update-function-code `
        --function-name $FunctionName `
        --region $Region `
        --zip-file "fileb://$zipFile" `
        2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Deployment successful!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
        exit 1
    }
}

# Step 4: Test
Write-Host ""
Write-Host "[Step 4/4] Testing deployment..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] All steps completed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test API: python test_api.py --username 'jeerasee@metrosystems.co.th' --password 'Namwan2546.'" -ForegroundColor Gray
Write-Host "  2. Check logs: aws logs tail /aws/lambda/$FunctionName --follow --region $Region" -ForegroundColor Gray
Write-Host ""

