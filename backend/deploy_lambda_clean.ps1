<# 
Clean deploy script for AWS Lambda (Python 3.11) using Docker

เป้าหมาย:
- ติดตั้ง dependencies ลงในโฟลเดอร์แยก `lambda-package/`
- ลบไฟล์/โฟลเดอร์ที่ชนกับ Python built‑in modules
- รวม source code (main.py, lambda_function.py, app/) เข้าไปใน package
- zip เฉพาะเนื้อหาภายใน (ไม่ให้มีโฟลเดอร์ lambda-package ซ้อนใน zip)
- deploy ด้วย `aws lambda update-function-code`

การใช้งาน:
PS> cd backend
PS> .\deploy_lambda_clean.ps1
#>

param(
    [string]$FunctionName = "ResumeMatchAPI",
    [string]$Region = "us-east-1",
    [string]$BuildDir = "lambda-package",
    [string]$ZipFile = "lambda-deployment-clean.zip"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying Lambda Function (CLEAN, Docker)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Function: $FunctionName" -ForegroundColor Yellow
Write-Host "Region  : $Region" -ForegroundColor Yellow
Write-Host "BuildDir: $BuildDir" -ForegroundColor Yellow
Write-Host ""

<# Step 0: ตรวจสอบ Docker ว่าใช้งานได้จริงๆ #>
Write-Host "[0/6] Checking Docker..." -ForegroundColor Green
$dockerAvailable = $false
try {
    docker --version | Out-Null
    # ตรวจสอบว่า Docker daemon พร้อมใช้งานจริงๆ
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerAvailable = $true
        Write-Host "Docker is available and running." -ForegroundColor Green
    } else {
        Write-Host "WARNING: Docker command exists but daemon is not running." -ForegroundColor Yellow
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Attempting fallback: using existing dependencies in current directory..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: Docker is not available." -ForegroundColor Yellow
    Write-Host "Attempting fallback: using existing dependencies in current directory..." -ForegroundColor Yellow
}

<# Step 1: ลบโฟลเดอร์ build เดิม และ zip เดิม (ถ้ามี) #>
Write-Host "[1/6] Cleaning previous build artifacts..." -ForegroundColor Green
if (Test-Path $BuildDir) {
    Write-Host "Removing existing build directory: $BuildDir" -ForegroundColor DarkYellow
    Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $BuildDir | Out-Null

if (Test-Path $ZipFile) {
    Write-Host "Removing existing zip file: $ZipFile" -ForegroundColor DarkYellow
    Remove-Item $ZipFile -Force -ErrorAction SilentlyContinue
}

<# Step 2: ติดตั้ง dependencies ลงในโฟลเดอร์ lambda-package/python/ (AWS Best Practice) #>
# สร้างโฟลเดอร์ python/ สำหรับ dependencies
$pythonDir = Join-Path $BuildDir "python"
New-Item -ItemType Directory -Path $pythonDir -Force | Out-Null

if ($dockerAvailable) {
    Write-Host "[2/6] Installing dependencies into '$pythonDir/' using Docker (Linux env)..." -ForegroundColor Green

    $projectPath = (Get-Location).Path
    # บน Windows ให้ใช้ path แบบเต็มในการ mount
    $dockerWorkDir = "/var/task"
    $volumePath = $projectPath + ":" + $dockerWorkDir

    docker run --rm `
        -v "$volumePath" `
        -w $dockerWorkDir `
        python:3.11-slim `
        /bin/bash -c "pip install -r requirements.txt -t $BuildDir/python/ --quiet"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies via Docker." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[2/6] Using existing dependencies from current directory..." -ForegroundColor Yellow
    Write-Host "WARNING: This will copy Windows-compatible dependencies which may not work in Lambda (Linux)." -ForegroundColor Yellow
    Write-Host "For production, please use Docker to get Linux-compatible dependencies." -ForegroundColor Yellow
    Write-Host ""
    
    # คัดลอก dependencies ที่มีอยู่แล้ว (ถ้ามี) ไปไว้ใน python/
    $dependenciesToCopy = @(
        "fastapi", "mangum", "starlette", "pydantic", "pydantic_core", "pydantic_settings",
        "opensearchpy", "multipart", "PyPDF2", "docx", "pythonjsonlogger", "watchtower",
        "h11", "anyio", "sniffio", "idna", "certifi", "charset_normalizer", "urllib3",
        "requests", "click", "colorama", "dateutil", "jmespath", "six.py", "typing_extensions.py",
        "yaml", "_yaml", "dotenv", "httptools", "lxml"
    )
    
    $copiedCount = 0
    foreach ($dep in $dependenciesToCopy) {
        $depPath = Join-Path "." $dep
        if (Test-Path $depPath) {
            $destPath = Join-Path $pythonDir $dep
            Write-Host "Copying dependency: $dep -> python/" -ForegroundColor Gray
            Copy-Item -Path $depPath -Destination $destPath -Recurse -Force -ErrorAction SilentlyContinue
            $copiedCount++
        }
    }
    
    if ($copiedCount -eq 0) {
        Write-Host "ERROR: No dependencies found in current directory." -ForegroundColor Red
        Write-Host "Please either:" -ForegroundColor Yellow
        Write-Host "  1. Start Docker Desktop and run this script again, OR" -ForegroundColor Yellow
        Write-Host "  2. Install dependencies first: pip install -r requirements.txt" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Copied $copiedCount dependencies to python/ directory." -ForegroundColor Green
    Write-Host "WARNING: These are Windows dependencies. Lambda may fail at runtime." -ForegroundColor Yellow
}

<# Step 3: Cleanup - ลบไฟล์ต้องห้ามที่ root level (ถ้ามี) #>
Write-Host "[3/6] Cleaning up root level (removing forbidden files if any)..." -ForegroundColor Green

# REMOVE forbidden Python built-in shadowing files (ROOT LEVEL ONLY)
# หมายเหตุ: ไฟล์ใน python/ (เช่น fastapi/security/http.py) ต้องเก็บไว้
$rootForbidden = @("http.py", "typing.py")

foreach ($f in $rootForbidden) {
    $path = Join-Path $BuildDir $f
    if (Test-Path $path) {
        Write-Host "Removing ROOT forbidden file: $path" -ForegroundColor Red
        Remove-Item $path -Force
    }
}

<# Step 3.1: ลบ dependencies ที่ใช้เฉพาะตอนพัฒนา (ไม่จำเป็นใน Lambda + Mangum) #>
Write-Host "[3.1/6] Removing dev-only dependencies to reduce package size..." -ForegroundColor Green

# ชุดแพ็กเกจที่มักใช้เฉพาะตอนรันเว็บเซิร์ฟเวอร์/auto-reload ภายนอก Lambda
$devPackages = @(
    "uvicorn",
    "uvloop",
    "watchfiles",
    "websockets"
)

foreach ($pkg in $devPackages) {
    # ลบโฟลเดอร์ package หลัก (ใน python/)
    $pkgPath = Join-Path $pythonDir $pkg
    if (Test-Path $pkgPath) {
        Write-Host "Removing dev package directory: $pkgPath" -ForegroundColor Yellow
        Remove-Item $pkgPath -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ลบ *.dist-info ที่เกี่ยวข้อง
    Get-ChildItem -Path $pythonDir -Recurse -Directory -Filter "$pkg-*.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Removing dev package metadata: $($_.FullName)" -ForegroundColor Yellow
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

<# Step 3.2: Cleanup ทั่วไป (ลดขนาด ZIP: dist-info, tests, __pycache__, *.pyc ฯลฯ) #>
Write-Host "[3.2/6] Cleaning up metadata, cache, and test files..." -ForegroundColor Green

# ลบ dist-info ทั้งหมด (ไม่จำเป็นตอน runtime) - ใน python/ เท่านั้น
Get-ChildItem -Path $pythonDir -Recurse -Directory -Filter "*.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Removing dist-info: $($_.FullName)" -ForegroundColor DarkYellow
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

# ลบโฟลเดอร์ tests / testing / __pycache__ - ใน python/ เท่านั้น
Get-ChildItem -Path $pythonDir -Recurse -Directory -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -in @("tests", "test", "testing", "__pycache__")
} | ForEach-Object {
    Write-Host "Removing test/cache directory: $($_.FullName)" -ForegroundColor DarkYellow
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

# ลบไฟล์ cache และไฟล์ doc ที่ไม่จำเป็น - ใน python/ เท่านั้น
Get-ChildItem -Path $pythonDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -in @(".pyc", ".pyo", ".pyd", ".txt", ".md", ".rst") -and $_.Name -ne "requirements.txt"
} | ForEach-Object {
    Write-Host "Removing extra file: $($_.FullName)" -ForegroundColor DarkYellow
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}

<# Step 3.3: ลบ AWS SDK (boto3, botocore, s3transfer) ซึ่งมีอยู่แล้วใน Lambda runtime #>
Write-Host "[3.3/6] Removing AWS SDK packages provided by Lambda runtime (boto3, botocore, s3transfer)..." -ForegroundColor Green

$awsSdkPkgs = @(
    "boto3",
    "botocore",
    "s3transfer"
)

foreach ($pkg in $awsSdkPkgs) {
    $pkgPath = Join-Path $pythonDir $pkg
    if (Test-Path $pkgPath) {
        Write-Host "Removing AWS SDK directory: $pkgPath" -ForegroundColor Yellow
        Remove-Item $pkgPath -Recurse -Force -ErrorAction SilentlyContinue
    }

    Get-ChildItem -Path $pythonDir -Recurse -Directory -Filter "$pkg-*.dist-info" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Removing AWS SDK metadata: $($_.FullName)" -ForegroundColor Yellow
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

<# Step 4: copy source code (main.py, lambda_function.py, app/) เข้าไปใน package #>
Write-Host "[4/6] Copying application source files into build directory..." -ForegroundColor Green

# ตรวจสอบก่อน copy ว่า source code ไม่มีไฟล์ต้องห้ามที่ root level และใน app/
Write-Host "Checking source code for forbidden files..." -ForegroundColor Gray
$forbiddenInSource = @("http.py", "typing.py")
$foundInSource = @()

# ตรวจสอบที่ root level
foreach ($f in $forbiddenInSource) {
    if (Test-Path $f) {
        Write-Host "WARNING: Found forbidden file in source: $f" -ForegroundColor Yellow
        $foundInSource += $f
    }
}

# ตรวจสอบใน app/ directory (recursive)
if (Test-Path "app") {
    foreach ($f in $forbiddenInSource) {
        $found = Get-ChildItem -Path "app" -Recurse -Filter $f -ErrorAction SilentlyContinue | 
            Where-Object { $_.FullName -notmatch 'lambda-package|__pycache__' }
        
        if ($found) {
            foreach ($file in $found) {
                Write-Host "WARNING: Found forbidden file in app/: $($file.FullName)" -ForegroundColor Yellow
                $foundInSource += $file.FullName
            }
        }
    }
}

if ($foundInSource.Count -gt 0) {
    Write-Host "ERROR: Source code contains forbidden files (http.py or typing.py):" -ForegroundColor Red
    foreach ($f in $foundInSource) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    Write-Host "" -ForegroundColor Red
    Write-Host "SOLUTION: Rename these files to avoid conflicts with Python stdlib:" -ForegroundColor Yellow
    Write-Host "  - http.py -> http_utils.py or http_routes.py" -ForegroundColor Yellow
    Write-Host "  - typing.py -> types.py or typing_utils.py" -ForegroundColor Yellow
    Write-Host "Then update all imports that reference these files." -ForegroundColor Yellow
    exit 1
}

# ตรวจสอบ import statements ที่อาจมีปัญหา
Write-Host "Checking for problematic import statements..." -ForegroundColor Gray
$problematicImports = @()
$sourceFiles = @("main.py", "lambda_function.py")
if (Test-Path "app") {
    $sourceFiles += Get-ChildItem -Path "app" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | 
        Where-Object { $_.FullName -notmatch 'lambda-package|__pycache__' } | 
        Select-Object -ExpandProperty FullName
}

foreach ($filePath in $sourceFiles) {
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -ErrorAction SilentlyContinue
        $lineNum = 0
        foreach ($line in $content) {
            $lineNum++
            # ตรวจสอบ import http หรือ import typing (ไม่ใช่ from typing import ...)
            if ($line -match '^\s*import\s+(http|typing)\s*$') {
                $problematicImports += "$filePath (line $lineNum): $line"
            }
        }
    }
}

if ($problematicImports.Count -gt 0) {
    Write-Host "ERROR: Found problematic import statements:" -ForegroundColor Red
    foreach ($imp in $problematicImports) {
        Write-Host "  - $imp" -ForegroundColor Red
    }
    Write-Host "" -ForegroundColor Red
    Write-Host "SOLUTION: Change 'import http' or 'import typing' to:" -ForegroundColor Yellow
    Write-Host "  - 'from typing import List, Dict, ...' (for typing)" -ForegroundColor Yellow
    Write-Host "  - 'from http import ...' or use fully qualified imports" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "OK: No problematic imports found (all use 'from typing import ...')" -ForegroundColor Green
}

$sources = @("main.py", "lambda_function.py", "app")
foreach ($src in $sources) {
    if (Test-Path $src) {
        Write-Host "Copying '$src' -> '$BuildDir'" -ForegroundColor Gray
        Copy-Item -Path $src -Destination $BuildDir -Recurse -Force
    } else {
        Write-Host "WARNING: Source '$src' not found in current directory." -ForegroundColor Yellow
    }
}

<# Step 4.1: Final cleanup - Remove any conflicting files (ROOT LEVEL ONLY) AFTER copying everything #>
Write-Host "[4.1/6] Final cleanup: Removing conflicting files at root level..." -ForegroundColor Green

# REMOVE forbidden Python built-in shadowing files (ROOT LEVEL ONLY)
# หมายเหตุ: ไฟล์ใน python/ (เช่น fastapi/security/http.py, pydantic/typing.py) ต้องเก็บไว้
$rootForbidden = @("http.py", "typing.py")

foreach ($f in $rootForbidden) {
    $path = Join-Path $BuildDir $f
    if (Test-Path $path) {
        Write-Host "CRITICAL: Found forbidden file at root: $path" -ForegroundColor Red
        Write-Host "Removing ROOT forbidden file: $path" -ForegroundColor Red
        Remove-Item $path -Force -ErrorAction Stop
        if (Test-Path $path) {
            Write-Host "ERROR: Failed to remove $path" -ForegroundColor Red
            exit 1
        } else {
            Write-Host "Successfully removed: $path" -ForegroundColor Green
        }
    }
}

<# Step 4.2: Final verification before zip - Check ROOT LEVEL and python/ directory #>
Write-Host "[4.2/6] Final verification before zip..." -ForegroundColor Green

# ตรวจสอบเฉพาะ ROOT ของ zip - ต้องไม่มีไฟล์ต้องห้าม (ใช้ Test-Path อย่างชัดเจน)
Write-Host "Checking for forbidden files at root level..." -ForegroundColor Gray
$httpPyPath = Join-Path $BuildDir "http.py"
$typingPyPath = Join-Path $BuildDir "typing.py"

$httpPyExists = Test-Path $httpPyPath
$typingPyExists = Test-Path $typingPyPath

if ($httpPyExists -or $typingPyExists) {
    Write-Host "CRITICAL ERROR: Forbidden files found at ROOT level (MUST NOT DEPLOY):" -ForegroundColor Red
    if ($httpPyExists) {
        Write-Host "  FOUND: $httpPyPath" -ForegroundColor Red
    }
    if ($typingPyExists) {
        Write-Host "  FOUND: $typingPyPath" -ForegroundColor Red
    }
    Write-Host "" -ForegroundColor Red
    Write-Host "Attempting to remove..." -ForegroundColor Yellow
    
    if ($httpPyExists) {
        Remove-Item $httpPyPath -Force -ErrorAction Stop
        Write-Host "  Removed: $httpPyPath" -ForegroundColor Yellow
    }
    if ($typingPyExists) {
        Remove-Item $typingPyPath -Force -ErrorAction Stop
        Write-Host "  Removed: $typingPyPath" -ForegroundColor Yellow
    }
    
    # Verify again after removal
    $httpPyStillExists = Test-Path $httpPyPath
    $typingPyStillExists = Test-Path $typingPyPath
    
    if ($httpPyStillExists -or $typingPyStillExists) {
        Write-Host "" -ForegroundColor Red
        Write-Host "CRITICAL ERROR: Forbidden files still present after removal attempt!" -ForegroundColor Red
        Write-Host "Deployment ABORTED. Please check file permissions." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "OK: All forbidden files removed successfully" -ForegroundColor Green
    }
} else {
    Write-Host "OK: No forbidden files found at root level" -ForegroundColor Green
    Write-Host "  Test-Path lambda-package/http.py: False" -ForegroundColor Gray
    Write-Host "  Test-Path lambda-package/typing.py: False" -ForegroundColor Gray
}

# ตรวจสอบไฟล์ที่ root level ว่ามีแค่ lambda_function.py และ main.py
Write-Host "Checking root level files..." -ForegroundColor Gray
$rootFiles = Get-ChildItem -Path $BuildDir -File | Select-Object -ExpandProperty Name
Write-Host "Root level files: $($rootFiles -join ', ')" -ForegroundColor Gray

$expectedRootFiles = @("lambda_function.py", "main.py")
$unexpectedRootFiles = $rootFiles | Where-Object { $_ -notin $expectedRootFiles -and $_ -notlike "*.pyc" }

if ($unexpectedRootFiles) {
    Write-Host "WARNING: Unexpected .py files at root level: $($unexpectedRootFiles -join ', ')" -ForegroundColor Yellow
    # ตรวจสอบว่าเป็นไฟล์ต้องห้ามหรือไม่
    $forbiddenFound = $unexpectedRootFiles | Where-Object { $_ -in @("http.py", "typing.py") }
    if ($forbiddenFound) {
        Write-Host "ERROR: Forbidden files still present: $($forbiddenFound -join ', ')" -ForegroundColor Red
        Write-Host "Deployment ABORTED." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "OK: Root level contains only expected files (lambda_function.py, main.py)" -ForegroundColor Green
}

# ตรวจสอบว่า python/ มี dependencies อยู่
Write-Host "Checking python/ directory..." -ForegroundColor Gray
if (Test-Path $pythonDir) {
    $pythonDirs = Get-ChildItem -Path $pythonDir -Directory | Select-Object -ExpandProperty Name
    if ($pythonDirs) {
        Write-Host "OK: python/ contains dependencies: $($pythonDirs -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "WARNING: python/ directory is empty!" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: python/ directory not found!" -ForegroundColor Red
    exit 1
}

<# Step 5: zip เฉพาะ contents ภายใน lambda-package (ไม่ให้มีโฟลเดอร์ซ้อน) #>
Write-Host "[5/6] Creating deployment zip (contents of '$BuildDir' only)..." -ForegroundColor Green

Push-Location $BuildDir

try {
    # รวมทุกอย่างใน build dir เป็น root ของ zip
    $itemsToZip = Get-ChildItem -Recurse
    if (-not $itemsToZip) {
        Write-Host "ERROR: Build directory '$BuildDir' is empty, nothing to zip." -ForegroundColor Red
        Pop-Location
        exit 1
    }

    # ใช้ relative path ทั้งหมดเวลา zip
    $itemsToZip | Compress-Archive -DestinationPath (Join-Path ".." $ZipFile) -Force
} finally {
    Pop-Location
}

if (-not (Test-Path $ZipFile)) {
    Write-Host "ERROR: Failed to create deployment zip '$ZipFile'." -ForegroundColor Red
    exit 1
}

$zipSizeMB = [math]::Round((Get-Item $ZipFile).Length / 1MB, 2)
Write-Host "Created: $ZipFile ($zipSizeMB MB)" -ForegroundColor Green

<# แสดงโครงสร้าง package ภายใน build dir เพื่อยืนยันว่าโครงสร้าง import ถูกต้อง #>
Write-Host ""
Write-Host "Package contents (inside '$BuildDir'):" -ForegroundColor Cyan
Get-ChildItem -Recurse $BuildDir | `
    Select-Object FullName, Length | `
    Format-Table -AutoSize

Write-Host ""
Write-Host "Zip root should contain (at least):" -ForegroundColor Cyan
Write-Host "- lambda_function.py" -ForegroundColor Gray
Write-Host "- main.py" -ForegroundColor Gray
Write-Host "- app/ (FastAPI project)" -ForegroundColor Gray
Write-Host "- python/ (dependencies - AWS will auto-add to sys.path)" -ForegroundColor Gray

<# Step 6: deploy ด้วย aws lambda update-function-code #>
Write-Host ""
Write-Host "[6/6] Updating Lambda function code via AWS CLI..." -ForegroundColor Green

aws lambda update-function-code `
    --function-name $FunctionName `
    --zip-file "fileb://$ZipFile" `
    --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to update Lambda function '$FunctionName'." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "- Verify Lambda runtime: Python 3.11" -ForegroundColor Yellow
Write-Host "- Verify handler: lambda_function.handler" -ForegroundColor Yellow
Write-Host "- Test API: /api/health via API Gateway" -ForegroundColor Yellow


