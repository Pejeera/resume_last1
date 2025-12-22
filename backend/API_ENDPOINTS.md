# API Endpoints สำหรับทดสอบ

Base URL: `https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com`

## 🔍 Health Check & Root

### 1. Root Endpoint
```
GET https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/
```
**Response:**
```json
{
  "message": "Resume Matching API is running",
  "version": "1.0.0"
}
```

### 2. Health Check
```
GET https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "Resume Matching API",
  "version": "1.0.0"
}
```

## 📋 Jobs Endpoints

### 3. List All Jobs
```
GET https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list
```
**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job_123",
      "title": "Software Engineer",
      "description": "Job description...",
      "created_at": "2025-12-19T00:00:00"
    }
  ],
  "total": 1
}
```

### 4. Create Job
```
POST https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/create
Content-Type: application/json

{
  "title": "Software Engineer",
  "description": "We are looking for a software engineer...",
  "metadata": {
    "location": "Bangkok",
    "salary": "50000-70000"
  }
}
```

### 5. Sync Jobs from S3
```
POST https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/sync_from_s3
```
**Note:** ใช้ได้เฉพาะเมื่อ USE_MOCK=false

### 6. Search Jobs by Resume
```
POST https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/search_by_resume
Content-Type: application/json

{
  "resume_id": "resume_123"
}
```

## 🧪 วิธีทดสอบ

### ใช้ Browser
เปิดลิงก์เหล่านี้ใน browser:
- Health Check: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health
- List Jobs: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list

### ใช้ curl (Command Line)
```bash
# Health Check
curl https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health

# List Jobs
curl https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list

# Create Job
curl -X POST https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/create \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Job","description":"Test description"}'
```

### ใช้ PowerShell
```powershell
# Health Check
Invoke-RestMethod -Uri "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health"

# List Jobs
Invoke-RestMethod -Uri "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list"

# Create Job
$body = @{
    title = "Test Job"
    description = "Test description"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/create" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

### ใช้ Python Script
```python
import requests

# Health Check
response = requests.get("https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health")
print(response.json())

# List Jobs
response = requests.get("https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list")
print(response.json())
```

## 📝 หมายเหตุ

- API Gateway timeout: 30 seconds (default)
- Lambda timeout: 900 seconds (15 minutes)
- หาก timeout อาจเป็นเพราะ:
  - Lambda cold start
  - OpenSearch connection issues
  - Network latency

## 🔗 Quick Links

- **Health Check**: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/health
- **List Jobs**: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api/jobs/list
- **Root**: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/

