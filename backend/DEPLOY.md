# 🚀 Deploy FastAPI to AWS Lambda

## 1. โครงสร้างไฟล์ที่ถูกต้อง

```
backend/
├── lambda_function.py      # Lambda entry point
├── main.py                 # FastAPI app (ไม่มี handler)
├── app/
│   ├── routers/
│   │   ├── health.py       # GET /api/health
│   │   ├── jobs.py         # GET /api/jobs/list, POST /api/jobs/create
│   │   └── resumes.py
│   └── ...
├── requirements.txt
└── ...
```

## 2. main.py (FastAPI App)

```python
# main.py - FastAPI app only, NO handler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(...)

# CORS middleware
app.add_middleware(CORSMiddleware, ...)

# Routes under /api/*
app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api/jobs")
app.include_router(resumes.router, prefix="/api/resumes")

# NO handler here - only for local dev
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 3. lambda_function.py (Lambda Entry Point)

```python
# lambda_function.py - Lambda entry point
from mangum import Mangum
from main import app

# Handler name: lambda_function.handler
handler = Mangum(app, lifespan="off")
```

## 4. API Gateway Configuration

### REST API (v1) - Lambda Proxy Integration

**Resource Setup:**
```
/{proxy+}  (ANY method)
```

**Integration:**
- Type: **Lambda Proxy Integration** ✅
- Lambda Function: `ResumeMatchAPI`
- Use Proxy Integration: ✅ Yes

**Methods:**
- ANY (หรือ GET, POST, OPTIONS, PUT, DELETE แยก)

**Path:**
- API Gateway path: `/{proxy+}`
- FastAPI routes: `/api/health`, `/api/jobs/list`, etc.
- Full URL: `https://api-id.execute-api.region.amazonaws.com/prod/api/health`

### HTTP API (v2) - Lambda Integration

**Route Setup:**
```
$default  (ANY /{proxy+})
```

**Integration:**
- Type: **Lambda**
- Lambda Function: `ResumeMatchAPI`
- Payload version: 2.0

**Methods:**
- ANY

## 5. Deploy แบบ ZIP

### Step 1: Install dependencies locally

```bash
cd backend
pip install -r requirements.txt -t .
```

### Step 2: Create deployment package

```bash
# Windows PowerShell
cd backend
Compress-Archive -Path app,*.py,*.txt -DestinationPath lambda-deployment.zip -Force

# หรือ Linux/Mac
cd backend
zip -r lambda-deployment.zip . \
  -x "*.pyc" \
  -x "__pycache__/*" \
  -x "*.git/*" \
  -x "test_*.py" \
  -x "*.md" \
  -x ".env" \
  -x "*.log"
```

### Step 3: Upload to Lambda

```bash
# Using AWS CLI
aws lambda update-function-code \
  --function-name ResumeMatchAPI \
  --zip-file fileb://lambda-deployment.zip \
  --region ap-southeast-1

# หรือใช้ AWS Console
# Lambda Console → Function → Upload from → .zip file
```

### Step 4: Verify Handler

**Lambda Console:**
- Runtime: Python 3.11
- Handler: `lambda_function.handler` ✅

### Step 5: Test

```bash
# Test via API Gateway
curl https://your-api-id.execute-api.region.amazonaws.com/prod/api/health

# หรือ Test via Lambda Console
# Use test event from lambda_test_events.json
```

## ✅ Checklist

- [ ] `main.py` ไม่มี `handler = Mangum(...)`
- [ ] `lambda_function.py` มี `handler = Mangum(app, lifespan="off")`
- [ ] Handler name ใน Lambda = `lambda_function.handler`
- [ ] API Gateway Resource = `/{proxy+}` (ANY method)
- [ ] API Gateway Integration = Lambda Proxy Integration
- [ ] Deploy code ใหม่ไปยัง Lambda
- [ ] Test endpoint `/api/health`

## 🔍 Troubleshooting

**405 Method Not Allowed:**
- ตรวจสอบ API Gateway Resource path = `/{proxy+}`
- ตรวจสอบ Integration type = Lambda Proxy
- ตรวจสอบ Lambda handler = `lambda_function.handler`

**404 Not Found:**
- ตรวจสอบ path ใน API Gateway = `/api/health` (ไม่ใช่ `/health`)
- ตรวจสอบ FastAPI routes มี prefix `/api`

**500 Internal Server Error:**
- ตรวจสอบ CloudWatch Logs
- ตรวจสอบ Lambda timeout และ memory
- ตรวจสอบ VPC configuration (ถ้าใช้ OpenSearch)

