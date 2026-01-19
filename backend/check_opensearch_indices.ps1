# OpenSearch Index Checker Script
# Usage: .\check_opensearch_indices.ps1 [resume_id] [index_name]

param(
    [string]$ResumeId = "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7",
    [string]$IndexName = "resumes_index",
    [string]$OpenSearchEndpoint = ""
)

# Load environment variables from .env file
$envPath = Join-Path $PSScriptRoot "..\infra\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^([^#][^=]*)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# Get OpenSearch endpoint from environment or parameter
if ([string]::IsNullOrEmpty($OpenSearchEndpoint)) {
    $OpenSearchEndpoint = $env:OPENSEARCH_ENDPOINT
}

if ([string]::IsNullOrEmpty($OpenSearchEndpoint)) {
    Write-Host "[ERROR] OpenSearch endpoint not found. Please set OPENSEARCH_ENDPOINT in .env file or pass as parameter." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "OpenSearch Index Checker" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  - OpenSearch Endpoint: $OpenSearchEndpoint"
Write-Host "  - Index Name: $IndexName"
Write-Host "  - Resume ID: $ResumeId"
Write-Host ""

# Extract host from endpoint
$host = $OpenSearchEndpoint -replace 'https?://', '' -replace '/$', ''
if ($host -match ':') {
    $host = $host -replace ':\d+', ''
}

# Get AWS credentials
$awsRegion = $env:AWS_REGION
if ([string]::IsNullOrEmpty($awsRegion)) {
    $awsRegion = "ap-southeast-1"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "1. ตรวจสอบ indices ที่มีอยู่" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. List all indices
try {
    $indicesUrl = "$OpenSearchEndpoint/_cat/indices?v&format=json"
    Write-Host "GET $indicesUrl" -ForegroundColor Gray
    
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    # Use AWS CLI to sign the request
    $response = aws es describe-elasticsearch-domain --domain-name resume-search-dev --region $awsRegion 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] AWS CLI available" -ForegroundColor Green
    }
    
    # Try using Invoke-WebRequest with AWS signing
    try {
        $response = Invoke-WebRequest -Uri $indicesUrl -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
        $indices = $response.Content | ConvertFrom-Json
        Write-Host ""
        Write-Host "พบ $($indices.Count) indices:" -ForegroundColor Green
        foreach ($idx in $indices) {
            Write-Host "  - $($idx.index) (docs: $($idx.'docs.count'), size: $($idx.'store.size'))"
        }
        
        $resumeIndices = $indices | Where-Object { $_.index -like "*resume*" }
        if ($resumeIndices) {
            Write-Host ""
            Write-Host "[OK] พบ resume indices:" -ForegroundColor Green
            foreach ($idx in $resumeIndices) {
                Write-Host "  - $($idx.index)"
            }
            $IndexName = $resumeIndices[0].index
        }
    } catch {
        Write-Host "[WARNING] ไม่สามารถเชื่อมต่อ OpenSearch โดยตรงได้" -ForegroundColor Yellow
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "ลองใช้ AWS CLI หรือ curl แทน:" -ForegroundColor Yellow
        Write-Host "  aws es describe-elasticsearch-domain --domain-name <domain> --region $awsRegion" -ForegroundColor Gray
    }
} catch {
    Write-Host "[ERROR] Error checking indices: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "2. ตรวจสอบว่า resume_id อยู่ใน $IndexName หรือไม่" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Resume ID: $ResumeId" -ForegroundColor Yellow
Write-Host ""

# 2. Check if resume exists
try {
    $searchUrl = "$OpenSearchEndpoint/$IndexName/_search"
    $searchBody = @{
        query = @{
            term = @{
                "resume_id.keyword" = $ResumeId
            }
        }
    } | ConvertTo-Json -Depth 10
    
    Write-Host "POST $searchUrl" -ForegroundColor Gray
    Write-Host "Body: $searchBody" -ForegroundColor Gray
    Write-Host ""
    
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    try {
        $response = Invoke-WebRequest -Uri $searchUrl -Method POST -Headers $headers -Body $searchBody -UseBasicParsing -ErrorAction Stop
        $result = $response.Content | ConvertFrom-Json
        $total = $result.hits.total.value
        
        if ($total -gt 0) {
            Write-Host "[OK] พบ resume (total: $total)" -ForegroundColor Green
            Write-Host ""
            Write-Host "Document:" -ForegroundColor Yellow
            $result.hits.hits[0]._source | ConvertTo-Json -Depth 10
        } else {
            Write-Host "[NO] ไม่พบ resume (total: 0)" -ForegroundColor Red
            Write-Host ""
            Write-Host "ลองใช้ match query แทน..." -ForegroundColor Yellow
            
            $searchBodyMatch = @{
                query = @{
                    match = @{
                        resume_id = $ResumeId
                    }
                }
            } | ConvertTo-Json -Depth 10
            
            $responseMatch = Invoke-WebRequest -Uri $searchUrl -Method POST -Headers $headers -Body $searchBodyMatch -UseBasicParsing -ErrorAction Stop
            $resultMatch = $responseMatch.Content | ConvertFrom-Json
            $totalMatch = $resultMatch.hits.total.value
            
            if ($totalMatch -gt 0) {
                Write-Host "[OK] พบ resume ด้วย match query (total: $totalMatch)" -ForegroundColor Green
                Write-Host ""
                Write-Host "Document:" -ForegroundColor Yellow
                $resultMatch.hits.hits[0]._source | ConvertTo-Json -Depth 10
            } else {
                Write-Host "[NO] ไม่พบ resume แม้ใช้ match query" -ForegroundColor Red
            }
        }
    } catch {
        Write-Host "[ERROR] Error searching: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "คำแนะนำ:" -ForegroundColor Yellow
        Write-Host "  1. ตรวจสอบว่า OpenSearch endpoint ถูกต้อง" -ForegroundColor Gray
        Write-Host "  2. ตรวจสอบ AWS credentials และ permissions" -ForegroundColor Gray
        Write-Host "  3. ใช้ AWS CLI: aws es describe-elasticsearch-domain --domain-name <domain>" -ForegroundColor Gray
    }
} catch {
    Write-Host "[ERROR] Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "3. ตรวจสอบว่า $IndexName มี vector fields หรือไม่" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 3. Check vector fields
try {
    $searchUrl = "$OpenSearchEndpoint/$IndexName/_search"
    $searchBody = @{
        _source = @("resume_id", "embedding", "embeddings", "vector", "resume_vector", "content")
        query = @{
            match_all = @{}
        }
        size = 1
    } | ConvertTo-Json -Depth 10
    
    try {
        $response = Invoke-WebRequest -Uri $searchUrl -Method POST -Headers $headers -Body $searchBody -UseBasicParsing -ErrorAction Stop
        $result = $response.Content | ConvertFrom-Json
        $total = $result.hits.total.value
        
        if ($total -gt 0) {
            $doc = $result.hits.hits[0]._source
            Write-Host "Fields ใน document:" -ForegroundColor Yellow
            foreach ($key in $doc.PSObject.Properties.Name) {
                $value = $doc.$key
                $type = if ($value -is [Array]) { "array[$($value.Length)]" } else { $value.GetType().Name }
                Write-Host "  - $key : $type"
            }
            
            $vectorFields = @("embedding", "embeddings", "vector", "resume_vector")
            $foundVectorFields = $vectorFields | Where-Object { $doc.PSObject.Properties.Name -contains $_ }
            
            if ($foundVectorFields) {
                Write-Host ""
                Write-Host "[OK] พบ vector fields: $($foundVectorFields -join ', ')" -ForegroundColor Green
                foreach ($field in $foundVectorFields) {
                    $value = $doc.$field
                    if ($value -is [Array]) {
                        Write-Host "  - $field : array with $($value.Length) dimensions"
                    } else {
                        Write-Host "  - $field : $($value.GetType().Name)"
                    }
                }
            } else {
                Write-Host ""
                Write-Host "[NO] ไม่พบ vector fields ใน document" -ForegroundColor Red
                Write-Host "   (ตรวจสอบ: $($vectorFields -join ', '))" -ForegroundColor Gray
            }
        } else {
            Write-Host "[NO] ไม่มี documents ใน index นี้" -ForegroundColor Red
        }
    } catch {
        Write-Host "[ERROR] Error: $($_.Exception.Message)" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "4. ตรวจสอบ mapping ของ $IndexName" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 4. Check mapping
try {
    $mappingUrl = "$OpenSearchEndpoint/$IndexName/_mapping"
    Write-Host "GET $mappingUrl" -ForegroundColor Gray
    Write-Host ""
    
    try {
        $response = Invoke-WebRequest -Uri $mappingUrl -Method GET -Headers $headers -UseBasicParsing -ErrorAction Stop
        $mapping = $response.Content | ConvertFrom-Json
        $indexMapping = $mapping.$IndexName.mappings.properties
        
        Write-Host "Mapping fields:" -ForegroundColor Yellow
        $vectorFields = @{}
        foreach ($fieldName in $indexMapping.PSObject.Properties.Name) {
            $fieldConfig = $indexMapping.$fieldName
            $fieldType = $fieldConfig.type
            Write-Host "  - $fieldName : $fieldType"
            
            if ($fieldType -in @("knn_vector", "dense_vector")) {
                $dimension = $fieldConfig.dimension
                Write-Host "    [OK] Vector field! (dimension: $dimension)" -ForegroundColor Green
                $vectorFields[$fieldName] = @{
                    type = $fieldType
                    dimension = $dimension
                }
            }
        }
        
        if ($vectorFields.Count -gt 0) {
            Write-Host ""
            Write-Host "[OK] พบ vector fields ใน mapping:" -ForegroundColor Green
            foreach ($fieldName in $vectorFields.Keys) {
                $config = $vectorFields[$fieldName]
                Write-Host "  - $fieldName : $($config.type) (dimension: $($config.dimension))"
            }
        } else {
            Write-Host ""
            Write-Host "[NO] ไม่พบ vector fields ใน mapping" -ForegroundColor Red
            Write-Host "   (ตรวจสอบ: knn_vector หรือ dense_vector)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "[ERROR] Error: $($_.Exception.Message)" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "สรุปผล" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Index: $IndexName"
Write-Host ""

