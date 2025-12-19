# Copy updated files to lambda-package
Copy-Item -Path "backend\app\routers\resumes.py" -Destination "backend\lambda-package\app\routers\resumes.py" -Force
Copy-Item -Path "backend\app\services\matching_service.py" -Destination "backend\lambda-package\app\services\matching_service.py" -Force
Write-Host "Files copied to lambda-package"

