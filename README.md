# Resume ↔ Job Matching System

ระบบจับคู่ Resume กับ Job ที่ใช้ AI โดยใช้ AWS Bedrock (Embeddings + LLM Rerank) และ OpenSearch (Vector Search)

## 🎯 คุณสมบัติ

### โหมด A: 1 Resume → Top 10 Jobs
- อัปโหลด Resume 1 ไฟล์ (PDF/DOCX/TXT)
- ระบบจะค้นหาตำแหน่งงานที่เหมาะสมที่สุด Top 10
- แสดงผลพร้อมเหตุผล, จุดเด่น, จุดที่ขาด, และคำถามแนะนำสำหรับสัมภาษณ์

### โหมด B: 1 Job → Top 10 Resumes
- กรอก Job Description หรือเลือก Job ID
- อัปโหลด Resumes หลายไฟล์
- ระบบจะค้นหา Resume ที่เหมาะสมที่สุด Top 10
- แสดงผลพร้อมเหตุผล, ความเสี่ยง, และขั้นตอนถัดไป

## 🏗️ สถาปัตยกรรม

```
┌─────────────┐
│   Frontend  │  HTML + Vanilla JS
│  (index.html)│
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────────────────────┐
│      FastAPI Backend                │
│  ┌──────────────────────────────┐  │
│  │  Routers (API Endpoints)      │  │
│  └──────────┬───────────────────┘  │
│             │                        │
│  ┌──────────▼───────────────────┐  │
│  │  Services (Business Logic)    │  │
│  └──────────┬───────────────────┘  │
│             │                        │
│  ┌──────────▼───────────────────┐  │
│  │  Repositories (Data Access)  │  │
│  └──────────┬───────────────────┘  │
└─────────────┼───────────────────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌────────┐ ┌──────────┐ ┌─────────────┐
│   S3   │ │ Bedrock  │ │ OpenSearch  │
│        │ │          │ │             │
│ Files  │ │Embeddings│ │Vector Search│
│        │ │+ Rerank  │ │             │
└────────┘ └──────────┘ └─────────────┘
```

## 📁 โครงสร้างโปรเจกต์

```
resume_last1/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py          # Configuration & Settings
│   │   │   ├── logging.py         # Structured Logging
│   │   │   └── exceptions.py      # Custom Exceptions
│   │   ├── clients/
│   │   │   ├── s3_client.py       # S3 File Storage
│   │   │   ├── bedrock_client.py  # Bedrock Embeddings & LLM
│   │   │   └── opensearch_client.py # OpenSearch Vector Search
│   │   ├── services/
│   │   │   ├── file_processor.py  # PDF/DOCX/TXT Extraction
│   │   │   └── matching_service.py # Core Matching Logic
│   │   ├── repositories/
│   │   │   ├── resume_repository.py # Resume Data Access
│   │   │   └── job_repository.py    # Job Data Access
│   │   └── routers/
│   │       ├── health.py          # Health Check
│   │       ├── resumes.py         # Resume Endpoints
│   │       └── jobs.py           # Job Endpoints
│   ├── main.py                    # FastAPI App Entry Point
│   └── requirements.txt           # Python Dependencies
├── frontend/
│   └── index.html                 # Single Page Application
├── infra/
│   ├── opensearch_index_mapping.json  # OpenSearch Index Schema
│   ├── env.example                # Environment Variables Template
│   └── rerank_prompt_template.md  # Rerank Prompt Documentation
└── README.md                      # This File
```

## 🚀 การติดตั้งและรัน Local

### 1. ติดตั้ง Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables

สร้างไฟล์ `.env` ในโฟลเดอร์ `backend/` จาก `infra/env.example`:

```bash
# สำหรับ Local Development (Mock Mode)
USE_MOCK=true
DEBUG=true

# CORS
CORS_ORIGINS=["*"]

# AWS Configuration (ถ้าไม่ใช้ Mock)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# S3
S3_BUCKET_NAME=resume-matching-bucket
S3_PREFIX=resumes/

# OpenSearch
OPENSEARCH_ENDPOINT=https://your-opensearch-endpoint.es.amazonaws.com
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your_password

# Bedrock
BEDROCK_REGION=ap-southeast-1
BEDROCK_EMBEDDING_MODEL=cohere.embed-multilingual-v3
BEDROCK_RERANK_MODEL=us.amazon.nova-lite-v1:0
```

### 3. รัน Backend Server

```bash
cd backend
python main.py
```

หรือใช้ uvicorn โดยตรง:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server จะรันที่ `http://localhost:8000`

### 4. เปิด Frontend

เปิดไฟล์ `frontend/index.html` ใน browser หรือใช้ local server:

```bash
# ใช้ Python HTTP Server
cd frontend
python -m http.server 8080
```

จากนั้นเปิด `http://localhost:8080` ใน browser

### 5. ดู API Documentation

เปิด `http://localhost:8000/docs` เพื่อดู Swagger UI

## 📡 API Endpoints

### Health Check
```
GET /api/health
```

### Resume Endpoints

#### Upload Resume (Mode A)
```
POST /api/resumes/upload
Content-Type: multipart/form-data
Body: file (PDF/DOCX/TXT)

Response:
{
  "resume_id": "uuid",
  "s3_url": "s3://bucket/path",
  "name": "resume.pdf",
  "created_at": "2024-01-01T00:00:00"
}
```

#### Bulk Upload Resumes (Mode B)
```
POST /api/resumes/bulk_upload
Content-Type: multipart/form-data
Body: files[] (multiple files)

Response:
{
  "results": [...],
  "total": 10,
  "success": 9,
  "failed": 1
}
```

#### Search Resumes by Job (Mode B)
```
POST /api/resumes/search_by_job?job_description=...
หรือ
POST /api/resumes/search_by_job?job_id=...

Response:
{
  "query": {...},
  "results": [
    {
      "rank": 1,
      "resume_id": "uuid",
      "resume_name": "resume.pdf",
      "match_score": 0.95,
      "rerank_score": 0.92,
      "fit_reasons": "เหตุผล...",
      "risks": ["risk1"],
      "highlighted_skills": ["skill1"],
      "suggested_next_step": "ติดต่อเพื่อสัมภาษณ์"
    }
  ],
  "total": 10
}
```

### Job Endpoints

#### Create Job (Admin/Mock)
```
POST /api/jobs/create
Content-Type: application/json
Body:
{
  "title": "Senior Backend Engineer",
  "description": "Job description...",
  "metadata": {}
}

Response:
{
  "job_id": "uuid",
  "title": "Senior Backend Engineer",
  "created_at": "2024-01-01T00:00:00"
}
```

#### Search Jobs by Resume (Mode A)
```
POST /api/jobs/search_by_resume
Content-Type: application/json
Body:
{
  "resume_id": "uuid"
}

Response:
{
  "resume_id": "uuid",
  "results": [
    {
      "rank": 1,
      "job_id": "uuid",
      "job_title": "Senior Backend Engineer",
      "match_score": 0.95,
      "rerank_score": 0.92,
      "reasons": "เหตุผล...",
      "highlighted_skills": ["Python", "FastAPI"],
      "gaps": ["AWS certification"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }
  ],
  "total": 10
}
```

## 🔧 การ Deploy บน AWS Lambda

### 1. สร้าง Lambda Function

```bash
# Package dependencies
cd backend
pip install -r requirements.txt -t .
zip -r lambda_function.zip . -x "*.pyc" "__pycache__/*"
```

### 2. สร้าง Lambda Function ใน AWS Console

- Runtime: Python 3.11
- Handler: `main.handler`
- Timeout: 5 minutes (300 seconds)
- Memory: 1024 MB (หรือมากกว่า)

### 3. ตั้งค่า Environment Variables

ตั้งค่าใน Lambda Console หรือใช้ Secrets Manager:
- `USE_MOCK=false`
- `AWS_REGION=ap-southeast-1`
- `S3_BUCKET_NAME=your-bucket`
- `OPENSEARCH_ENDPOINT=your-endpoint`
- และอื่นๆ ตาม `infra/env.example`

### 4. สร้าง API Gateway

- สร้าง REST API
- เชื่อมต่อกับ Lambda Function
- ตั้งค่า CORS
- ตั้งค่า WAF Rules (ถ้าต้องการ)

### 5. ตั้งค่า IAM Permissions

Lambda Function ต้องมี permissions สำหรับ:
- S3: `s3:PutObject`, `s3:GetObject`
- Bedrock: `bedrock:InvokeModel`
- OpenSearch: `es:ESHttpPost`, `es:ESHttpGet`
- CloudWatch: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- Secrets Manager: `secretsmanager:GetSecretValue` (ถ้าใช้)

### 6. ตั้งค่า OpenSearch Index

ใช้ mapping จาก `infra/opensearch_index_mapping.json`:

```bash
# สร้าง jobs_index
curl -X PUT "https://your-opensearch-endpoint/jobs_index" \
  -H "Content-Type: application/json" \
  -u admin:password \
  -d @infra/opensearch_index_mapping.json

# สร้าง resumes_index
curl -X PUT "https://your-opensearch-endpoint/resumes_index" \
  -H "Content-Type: application/json" \
  -u admin:password \
  -d @infra/opensearch_index_mapping.json
```

## 🔐 Security Best Practices

1. **Secrets Management**: ใช้ AWS Secrets Manager เก็บ credentials
2. **WAF Rules**: ตั้งค่า rate limiting และ IP filtering
3. **CORS**: จำกัด origins ที่อนุญาต
4. **Validation**: ตรวจสอบ input ทุก endpoint
5. **Error Handling**: ไม่เปิดเผย sensitive information ใน error messages

## 📊 การไหลของข้อมูล

### Mode A: Resume → Jobs

```
1. User uploads resume → S3
2. Extract text from resume
3. Generate embedding (Bedrock)
4. Vector search in jobs_index (OpenSearch) → Top 50
5. Rerank with Bedrock Nova 2 Lite → Top 10
6. Return results with reasons
```

### Mode B: Job → Resumes

```
1. User uploads multiple resumes → S3
2. Extract text + generate embeddings for each
3. Index resumes in resumes_index (OpenSearch)
4. Generate embedding for job description (Bedrock)
5. Vector search in resumes_index (OpenSearch) → Top 100
6. Rerank with Bedrock Nova 2 Lite → Top 10
7. Return results with reasons
```

## 🧪 ตัวอย่างการใช้งาน

### ตัวอย่าง Request/Response (Mode A)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/resumes/upload" \
  -F "file=@resume.pdf"
```

**Response:**
```json
{
  "resume_id": "abc123",
  "s3_url": "s3://bucket/resumes/abc123/resume.pdf",
  "name": "resume.pdf",
  "created_at": "2024-01-01T00:00:00"
}
```

**Search Request:**
```bash
curl -X POST "http://localhost:8000/api/jobs/search_by_resume" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": "abc123"}'
```

**Search Response:**
```json
{
  "resume_id": "abc123",
  "results": [
    {
      "rank": 1,
      "job_id": "job123",
      "job_title": "Senior Backend Engineer",
      "match_score": 0.95,
      "rerank_score": 0.92,
      "reasons": "ผู้สมัครมีประสบการณ์ตรงกับตำแหน่งงาน มีทักษะ Python และ FastAPI ที่ตรงกับความต้องการ",
      "highlighted_skills": ["Python", "FastAPI", "AWS"],
      "gaps": ["AWS certification"],
      "recommended_questions_for_interview": [
        "คุณมีประสบการณ์กับ AWS Lambda มากแค่ไหน?",
        "คุณเคยใช้ OpenSearch ในการทำ vector search หรือไม่?"
      ]
    }
  ],
  "total": 10
}
```

## 📝 Rerank Prompt

ดูรายละเอียด rerank prompt และ JSON schema ได้ที่ `infra/rerank_prompt_template.md`

## 🐛 Troubleshooting

### ปัญหา: Mock mode ไม่ทำงาน
- ตรวจสอบว่า `USE_MOCK=true` ใน `.env`
- ตรวจสอบ logs ใน console

### ปัญหา: OpenSearch connection error
- ตรวจสอบ endpoint และ credentials
- ตรวจสอบ network connectivity
- ตรวจสอบ SSL certificate settings

### ปัญหา: Bedrock invocation error
- ตรวจสอบว่า model ID ถูกต้อง
- ตรวจสอบ IAM permissions
- ตรวจสอบ region settings

## 📚 Tech Stack

- **Backend**: Python 3.11, FastAPI, Mangum
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **AWS Services**: 
  - S3 (File Storage)
  - Bedrock (Embeddings + LLM Rerank)
  - OpenSearch (Vector Search)
  - CloudWatch (Logging)
  - Secrets Manager (Credentials)
  - API Gateway + Lambda (Deployment)
- **Libraries**: 
  - boto3 (AWS SDK)
  - opensearch-py (OpenSearch Client)
  - PyPDF2, python-docx (File Processing)

## 📄 License

MIT License

## 👥 Contributors

Created by Senior Full-Stack Engineer + AWS Solution Architect
