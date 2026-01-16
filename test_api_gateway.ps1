# Test API Gateway
# Usage: .\test_api_gateway.ps1

param(
    [Parameter(Mandatory=$false)]
    [string]$Username = "jeerasee@metrosystems.co.th",
    
    [Parameter(Mandatory=$false)]
    [string]$Password = "Namwan2546.",
    
    [Parameter(Mandatory=$false)]
    [string]$ApiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing API Gateway" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API URL: $ApiUrl" -ForegroundColor Yellow
Write-Host ""

# Test 1: Health endpoint (should require auth)
Write-Host "Test 1: Health endpoint (without auth)" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$ApiUrl/health" -Method GET -ErrorAction Stop
    Write-Host "✅ Health endpoint: OK (Status: $($response.StatusCode))" -ForegroundColor Green
    Write-Host "Response: $($response.Content)" -ForegroundColor Gray
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "❌ Health endpoint: Failed (Status: $statusCode)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody" -ForegroundColor Gray
    }
}
Write-Host ""

# Test 2: Login endpoint
Write-Host "Test 2: Login endpoint" -ForegroundColor Yellow
try {
    $loginBody = @{
        username = $Username
        password = $Password
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$ApiUrl/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -ErrorAction Stop
    Write-Host "✅ Login: OK (Status: $($response.StatusCode))" -ForegroundColor Green
    
    $loginData = $response.Content | ConvertFrom-Json
    $token = $loginData.idToken
    Write-Host "Token received: $($token.Substring(0, 50))..." -ForegroundColor Gray
    Write-Host ""
    
    # Test 3: Health endpoint with auth
    Write-Host "Test 3: Health endpoint (with auth)" -ForegroundColor Yellow
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        $response = Invoke-WebRequest -Uri "$ApiUrl/health" -Method GET -Headers $headers -ErrorAction Stop
        Write-Host "✅ Health endpoint with auth: OK (Status: $($response.StatusCode))" -ForegroundColor Green
        Write-Host "Response: $($response.Content)" -ForegroundColor Gray
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "❌ Health endpoint with auth: Failed (Status: $statusCode)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "Response: $responseBody" -ForegroundColor Gray
        }
    }
    Write-Host ""
    
    # Test 4: Jobs list endpoint
    Write-Host "Test 4: Jobs list endpoint (with auth)" -ForegroundColor Yellow
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        $response = Invoke-WebRequest -Uri "$ApiUrl/jobs/list" -Method GET -Headers $headers -ErrorAction Stop
        Write-Host "✅ Jobs list: OK (Status: $($response.StatusCode))" -ForegroundColor Green
        $jobsData = $response.Content | ConvertFrom-Json
        $jobsCount = ($jobsData.jobs | Measure-Object).Count
        Write-Host "Found $jobsCount jobs" -ForegroundColor Gray
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "❌ Jobs list: Failed (Status: $statusCode)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "Response: $responseBody" -ForegroundColor Gray
        }
    }
    Write-Host ""
    
    # Test 5: Resumes list endpoint
    Write-Host "Test 5: Resumes list endpoint (with auth)" -ForegroundColor Yellow
    $resumeKey = $null
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        $response = Invoke-WebRequest -Uri "$ApiUrl/resumes/list" -Method GET -Headers $headers -ErrorAction Stop
        Write-Host "✅ Resumes list: OK (Status: $($response.StatusCode))" -ForegroundColor Green
        $resumesData = $response.Content | ConvertFrom-Json
        $resumesCount = ($resumesData.resumes | Measure-Object).Count
        Write-Host "Found $resumesCount resumes" -ForegroundColor Gray
        if ($resumesCount -gt 0) {
            $resumeKey = $resumesData.resumes[0].s3_key
            if (-not $resumeKey) { $resumeKey = $resumesData.resumes[0].key }
            Write-Host "Using resume key: $resumeKey" -ForegroundColor Gray
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "❌ Resumes list: Failed (Status: $statusCode)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Host "Response: $responseBody" -ForegroundColor Gray
        }
    }
    Write-Host ""
    
    # Test 6: POST - Search jobs by resume
    Write-Host "Test 6: POST /jobs/search_by_resume" -ForegroundColor Yellow
    if ($resumeKey) {
        try {
            $headers = @{
                "Authorization" = "Bearer $token"
                "Content-Type" = "application/json"
            }
            
            # Try with resume_key
            Write-Host "  Trying with resume_key..." -ForegroundColor Gray
            $searchBody = @{
                resume_key = $resumeKey
            } | ConvertTo-Json -Depth 10
            
            Write-Host "  Request body: $searchBody" -ForegroundColor Gray
            $response = Invoke-WebRequest -Uri "$ApiUrl/jobs/search_by_resume" -Method POST -Body $searchBody -Headers $headers -ErrorAction Stop
            Write-Host "✅ Search jobs by resume: OK (Status: $($response.StatusCode))" -ForegroundColor Green
            $searchData = $response.Content | ConvertFrom-Json
            $resultsCount = ($searchData.results | Measure-Object).Count
            Write-Host "Found $resultsCount matching jobs" -ForegroundColor Gray
        } catch {
            $statusCode = $_.Exception.Response.StatusCode.value__
            Write-Host "❌ Search jobs by resume: Failed (Status: $statusCode)" -ForegroundColor Red
            if ($_.Exception.Response) {
                try {
                    $stream = $_.Exception.Response.GetResponseStream()
                    $reader = New-Object System.IO.StreamReader($stream)
                    $responseBody = $reader.ReadToEnd()
                    $reader.Close()
                    $stream.Close()
                    Write-Host "Error Response: $responseBody" -ForegroundColor Red
                    try {
                        $errorData = $responseBody | ConvertFrom-Json
                        if ($errorData.detail) {
                            Write-Host "Detail: $($errorData.detail)" -ForegroundColor Red
                        }
                        if ($errorData.message) {
                            Write-Host "Message: $($errorData.message)" -ForegroundColor Red
                        }
                    } catch {
                        Write-Host "Could not parse error response as JSON" -ForegroundColor Yellow
                    }
                } catch {
                    Write-Host "Could not read error response: $($_.Exception.Message)" -ForegroundColor Yellow
                }
            }
            Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "Exception Type: $($_.Exception.GetType().FullName)" -ForegroundColor Gray
        }
    } else {
        Write-Host "⚠️ Skipping: No resume available for testing" -ForegroundColor Yellow
    }
    Write-Host ""
    
    # Test 7: POST - Search resumes by job
    Write-Host "Test 7: POST /resumes/search_by_job" -ForegroundColor Yellow
    $jobId = $null
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        $response = Invoke-WebRequest -Uri "$ApiUrl/jobs/list" -Method GET -Headers $headers -ErrorAction Stop
        $jobsData = $response.Content | ConvertFrom-Json
        if (($jobsData.jobs | Measure-Object).Count -gt 0) {
            $jobId = $jobsData.jobs[0].id
            if (-not $jobId) { $jobId = $jobsData.jobs[0].job_id }
            Write-Host "Using job ID: $jobId" -ForegroundColor Gray
            
            if ($resumeKey) {
                $searchBody = @{
                    resume_keys = @($resumeKey)
                } | ConvertTo-Json -Depth 10
                
                Write-Host "  Request body: $searchBody" -ForegroundColor Gray
                Write-Host "  URL: $ApiUrl/resumes/search_by_job?job_id=$([System.Web.HttpUtility]::UrlEncode($jobId))" -ForegroundColor Gray
                
                $response = Invoke-WebRequest -Uri "$ApiUrl/resumes/search_by_job?job_id=$([System.Web.HttpUtility]::UrlEncode($jobId))" -Method POST -Body $searchBody -Headers $headers -ErrorAction Stop
                Write-Host "✅ Search resumes by job: OK (Status: $($response.StatusCode))" -ForegroundColor Green
                $searchData = $response.Content | ConvertFrom-Json
                $resultsCount = ($searchData.results | Measure-Object).Count
                Write-Host "Found $resultsCount matching resumes" -ForegroundColor Gray
            } else {
                Write-Host "⚠️ Skipping: No resume key available" -ForegroundColor Yellow
            }
        } else {
            Write-Host "⚠️ Skipping: No jobs available for testing" -ForegroundColor Yellow
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "❌ Search resumes by job: Failed (Status: $statusCode)" -ForegroundColor Red
        if ($_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $responseBody = $reader.ReadToEnd()
                $reader.Close()
                $stream.Close()
                Write-Host "Error Response: $responseBody" -ForegroundColor Red
                try {
                    $errorData = $responseBody | ConvertFrom-Json
                    if ($errorData.detail) {
                        Write-Host "Detail: $($errorData.detail)" -ForegroundColor Red
                    }
                    if ($errorData.error) {
                        Write-Host "Error: $($errorData.error)" -ForegroundColor Red
                    }
                    if ($errorData.message) {
                        Write-Host "Message: $($errorData.message)" -ForegroundColor Red
                    }
                } catch {
                    Write-Host "Could not parse error response as JSON" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "Could not read error response: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
        Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Exception Type: $($_.Exception.GetType().FullName)" -ForegroundColor Gray
    }
    Write-Host ""
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host "❌ Login: Failed (Status: $statusCode)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "⚠️ Cannot continue tests without login token" -ForegroundColor Yellow
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

