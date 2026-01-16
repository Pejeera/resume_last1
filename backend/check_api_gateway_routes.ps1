# Check API Gateway Routes and provide instructions
# This script helps identify missing routes in API Gateway

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API Gateway Route Checker" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[PROBLEM IDENTIFIED]" -ForegroundColor Red
Write-Host "The /api/resumes/upload endpoint is NOT visible in API Gateway Routes" -ForegroundColor Yellow
Write-Host ""

Write-Host "[ANALYSIS]" -ForegroundColor Cyan
Write-Host "From the Routes view, we can see:" -ForegroundColor White
Write-Host "  - /api/jobs/search_by_resume (OPTIONS)" -ForegroundColor Gray
Write-Host "  - /api/jobs/list (OPTIONS)" -ForegroundColor Gray
Write-Host "  - /api/resumes/search_by_job (OPTIONS)" -ForegroundColor Gray
Write-Host "  - /api/resumes/list (OPTIONS)" -ForegroundColor Gray
Write-Host "  - /api/auth/login (OPTIONS, POST)" -ForegroundColor Gray
Write-Host "  - /{proxy+} (ANY)" -ForegroundColor Gray
Write-Host ""
Write-Host "  MISSING: /api/resumes/upload" -ForegroundColor Red
Write-Host "  MISSING: /api/resumes/upload_to_s3" -ForegroundColor Red
Write-Host ""

Write-Host "[SOLUTION]" -ForegroundColor Cyan
Write-Host "The /{proxy+} route should catch all requests, but you need to:" -ForegroundColor White
Write-Host ""
Write-Host "1. Add explicit route for /api/resumes/upload in API Gateway:" -ForegroundColor Yellow
Write-Host "   - Go to API Gateway Console" -ForegroundColor Gray
Write-Host "   - Select your API (ResumeMatchAPI)" -ForegroundColor Gray
Write-Host "   - Click 'Create' under Routes" -ForegroundColor Gray
Write-Host "   - Method: POST" -ForegroundColor Gray
Write-Host "   - Path: /api/resumes/upload" -ForegroundColor Gray
Write-Host "   - Integration: Lambda Function" -ForegroundColor Gray
Write-Host "   - Select your Lambda function" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Add OPTIONS method for CORS preflight:" -ForegroundColor Yellow
Write-Host "   - Create another route: OPTIONS /api/resumes/upload" -ForegroundColor Gray
Write-Host "   - Integration: Mock or CORS" -ForegroundColor Gray
Write-Host "   - Response: 200 OK with CORS headers" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Configure Binary Media Types:" -ForegroundColor Yellow
Write-Host "   - Go to API Gateway Settings" -ForegroundColor Gray
Write-Host "   - Add 'multipart/form-data' to Binary Media Types" -ForegroundColor Gray
Write-Host "   - This is required for file uploads" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Enable CORS on the route:" -ForegroundColor Yellow
Write-Host "   - Select the route" -ForegroundColor Gray
Write-Host "   - Click 'Actions' -> 'Enable CORS'" -ForegroundColor Gray
Write-Host "   - Configure CORS settings:" -ForegroundColor Gray
Write-Host "     * Access-Control-Allow-Origin: *" -ForegroundColor Gray
Write-Host "     * Access-Control-Allow-Methods: POST, OPTIONS" -ForegroundColor Gray
Write-Host "     * Access-Control-Allow-Headers: Content-Type, Authorization" -ForegroundColor Gray
Write-Host "   - Deploy the API" -ForegroundColor Gray
Write-Host ""

Write-Host "[ALTERNATIVE: Use Proxy Integration]" -ForegroundColor Cyan
Write-Host "If /{proxy+} is configured correctly, it should work." -ForegroundColor White
Write-Host "But you still need to:" -ForegroundColor Yellow
Write-Host "  1. Configure Binary Media Types (multipart/form-data)" -ForegroundColor Gray
Write-Host "  2. Enable CORS on /{proxy+} route" -ForegroundColor Gray
Write-Host "  3. Ensure Lambda function has proper timeout (file uploads take time)" -ForegroundColor Gray
Write-Host ""

Write-Host "[TESTING]" -ForegroundColor Cyan
Write-Host "After configuration, test with:" -ForegroundColor White
Write-Host "  .\test_upload_curl.ps1" -ForegroundColor Yellow
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan

