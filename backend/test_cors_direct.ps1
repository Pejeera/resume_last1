# Test CORS directly
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing CORS Configuration" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$apiUrl = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/auth/login"

Write-Host "[Test 1: OPTIONS Preflight Request]" -ForegroundColor Yellow
try {
    $headers = @{
        'Origin' = 'https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com'
        'Access-Control-Request-Method' = 'POST'
        'Access-Control-Request-Headers' = 'content-type,authorization'
    }
    
    $response = Invoke-WebRequest -Uri $apiUrl -Method OPTIONS -Headers $headers -ErrorAction Stop
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response Headers:" -ForegroundColor Cyan
    foreach ($header in $response.Headers.GetEnumerator()) {
        if ($header.Key -like '*Access-Control*') {
            Write-Host "  $($header.Key): $($header.Value)" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Response Headers:" -ForegroundColor Cyan
        $_.Exception.Response.Headers | Get-Member -MemberType NoteProperty | ForEach-Object {
            $headerName = $_.Name
            $headerValue = $_.Exception.Response.Headers[$headerName]
            if ($headerName -like '*Access-Control*') {
                Write-Host "  $headerName : $headerValue" -ForegroundColor Green
            }
        }
    }
}

Write-Host ""
Write-Host "[Test 2: POST Request]" -ForegroundColor Yellow
try {
    $body = @{
        username = "jeerasee@metrosystems.co.th"
        password = "Namwan2546."
    } | ConvertTo-Json
    
    $headers = @{
        'Content-Type' = 'application/json'
        'Origin' = 'https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com'
    }
    
    $response = Invoke-WebRequest -Uri $apiUrl -Method POST -Headers $headers -Body $body -ErrorAction Stop
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response Headers:" -ForegroundColor Cyan
    foreach ($header in $response.Headers.GetEnumerator()) {
        if ($header.Key -like '*Access-Control*') {
            Write-Host "  $($header.Key): $($header.Value)" -ForegroundColor Green
        }
    }
    Write-Host ""
    Write-Host "Response Body:" -ForegroundColor Cyan
    Write-Host $response.Content -ForegroundColor White
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Response Headers:" -ForegroundColor Cyan
        $_.Exception.Response.Headers | Get-Member -MemberType NoteProperty | ForEach-Object {
            $headerName = $_.Name
            $headerValue = $_.Exception.Response.Headers[$headerName]
            if ($headerName -like '*Access-Control*') {
                Write-Host "  $headerName : $headerValue" -ForegroundColor Green
            }
        }
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan

