<#
ตรวจสอบไฟล์ต้องห้ามที่ชนกับ Python stdlib
รันจากโฟลเดอร์ backend
#>

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Checking for Forbidden Files (stdlib conflicts)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$foundIssues = $false

# 1. ตรวจสอบไฟล์ http.py หรือ typing.py ใน source code (ไม่รวม dependencies)
Write-Host "[1/3] Checking for http.py and typing.py in source code..." -ForegroundColor Green

$sourceDirs = @("app", "main.py", "lambda_function.py")
$forbiddenFiles = @("http.py", "typing.py")

foreach ($dir in $sourceDirs) {
    if (Test-Path $dir) {
        if ($dir -like "*.py") {
            # ไฟล์เดียว
            $fileName = Split-Path $dir -Leaf
            if ($fileName -in $forbiddenFiles) {
                Write-Host "  ❌ FOUND: $dir" -ForegroundColor Red
                $foundIssues = $true
            }
        } else {
            # โฟลเดอร์
            foreach ($forbidden in $forbiddenFiles) {
                $found = Get-ChildItem -Path $dir -Recurse -Filter $forbidden -ErrorAction SilentlyContinue | 
                    Where-Object { $_.FullName -notmatch 'lambda-package|__pycache__' }
                
                if ($found) {
                    foreach ($f in $found) {
                        Write-Host "  ❌ FOUND: $($f.FullName)" -ForegroundColor Red
                        $foundIssues = $true
                    }
                }
            }
        }
    }
}

if (-not $foundIssues) {
    Write-Host "  ✅ No forbidden files found in source code" -ForegroundColor Green
}

Write-Host ""

# 2. ตรวจสอบ import statements ที่ชนกับ stdlib
Write-Host "[2/3] Checking for problematic import statements..." -ForegroundColor Green

$problematicImports = @()
$sourceFiles = Get-ChildItem -Path "app" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | 
    Where-Object { $_.FullName -notmatch 'lambda-package|__pycache__' }

$sourceFiles += Get-Item "main.py", "lambda_function.py" -ErrorAction SilentlyContinue

foreach ($file in $sourceFiles) {
    if (Test-Path $file) {
        $content = Get-Content $file.FullName -ErrorAction SilentlyContinue
        foreach ($line in $content) {
            if ($line -match '^\s*import\s+(http|typing)\s*$') {
                $problematicImports += "$($file.Name): $line"
            }
        }
    }
}

if ($problematicImports.Count -gt 0) {
    Write-Host "  ❌ Found problematic imports:" -ForegroundColor Red
    foreach ($imp in $problematicImports) {
        Write-Host "    - $imp" -ForegroundColor Red
    }
    $foundIssues = $true
} else {
    Write-Host "  ✅ No problematic imports found (all use 'from typing import ...')" -ForegroundColor Green
}

Write-Host ""

# 3. ตรวจสอบไฟล์ที่ root level ของ lambda-package (ถ้ามี)
Write-Host "[3/3] Checking lambda-package root level (if exists)..." -ForegroundColor Green

if (Test-Path "lambda-package") {
    foreach ($forbidden in $forbiddenFiles) {
        $path = Join-Path "lambda-package" $forbidden
        if (Test-Path $path) {
            Write-Host "  ❌ FOUND at root: $path" -ForegroundColor Red
            $foundIssues = $true
        }
    }
    
    if (-not $foundIssues) {
        Write-Host "  ✅ No forbidden files at lambda-package root" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️  lambda-package directory not found (not built yet)" -ForegroundColor Yellow
}

Write-Host ""

# สรุปผล
Write-Host "==========================================" -ForegroundColor Cyan
if ($foundIssues) {
    Write-Host "❌ ISSUES FOUND - Please fix before deployment!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Action items:" -ForegroundColor Yellow
    Write-Host "  1. Rename any http.py or typing.py files" -ForegroundColor Yellow
    Write-Host "  2. Change 'import http' or 'import typing' to 'from typing import ...'" -ForegroundColor Yellow
    Write-Host "  3. Update all imports that reference renamed files" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "✅ ALL CHECKS PASSED - No forbidden files or imports found!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your source code is safe to deploy." -ForegroundColor Green
    exit 0
}

