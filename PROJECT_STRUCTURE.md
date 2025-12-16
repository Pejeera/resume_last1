# โครงสร้างโปรเจกต์ Resume ↔ Job Matching

## 📁 โครงสร้างไฟล์

```
resume_last1/
│
├── backend/                          # FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   ├── core/                     # Core Configuration
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Settings & Environment Variables
│   │   │   ├── logging.py           # Structured Logging (CloudWatch)
│   │   │   └── exceptions.py        # Custom Exceptions
│   │   │
│   │   ├── clients/                  # AWS Service Clients
│   │   │   ├── __init__.py
│   │   │   ├── s3_client.py         # S3 File Storage
│   │   │   ├── bedrock_client.py    # Bedrock Embeddings + LLM Rerank
│   │   │   └── opensearch_client.py # OpenSearch Vector Search
│   │   │
│   │   ├── services/                 # Business Logic
│   │   │   ├── __init__.py
│   │   │   ├── file_processor.py    # PDF/DOCX/TXT Extraction
│   │   │   └── matching_service.py  # Core Matching Algorithm
│   │   │
│   │   ├── repositories/             # Data Access Layer
│   │   │   ├── __init__.py
│   │   │   ├── resume_repository.py # Resume CRUD Operations
│   │   │   └── job_repository.py    # Job CRUD Operations
│   │   │
│   │   └── routers/                  # API Endpoints
│   │       ├── __init__.py
│   │       ├── health.py            # GET /api/health
│   │       ├── resumes.py           # Resume Endpoints
│   │       └── jobs.py              # Job Endpoints
│   │
│   ├── main.py                       # FastAPI App Entry Point
│   └── requirements.txt              # Python Dependencies
│
├── frontend/                         # Frontend Application
│   └── index.html                   # Single Page Application (HTML + CSS + JS)
│
├── infra/                            # Infrastructure & Configuration
│   ├── opensearch_index_mapping.json # OpenSearch Index Schema
│   ├── env.example                  # Environment Variables Template
│   ├── rerank_prompt_template.md    # Rerank Prompt Documentation
│   └── create_opensearch_indices.py  # Script to Create Indices
│
├── examples/                         # Examples & Documentation
│   └── api_examples.md              # API Usage Examples
│
├── .gitignore                       # Git Ignore Rules
├── README.md                        # Main Documentation
└── PROJECT_STRUCTURE.md             # This File
```

## 🔄 Data Flow

### Mode A: Resume → Jobs

```
User Upload Resume
    ↓
[Frontend] POST /api/resumes/upload
    ↓
[Router] resumes.upload_resume()
    ↓
[Repository] resume_repository.create_resume()
    ├── [S3 Client] Upload file to S3
    ├── [File Processor] Extract text
    ├── [Bedrock Client] Generate embedding
    └── [OpenSearch Client] Index document
    ↓
[Router] jobs.search_by_resume()
    ↓
[Service] matching_service.search_jobs_by_resume()
    ├── [Bedrock Client] Generate resume embedding
    ├── [OpenSearch Client] Vector search (Top 50)
    ├── [Bedrock Client] Rerank with Nova 2 Lite (Top 10)
    └── Format results
    ↓
Return JSON Response
```

### Mode B: Job → Resumes

```
User Upload Multiple Resumes
    ↓
[Frontend] POST /api/resumes/bulk_upload
    ↓
[Router] resumes.bulk_upload_resumes()
    ↓
[Repository] resume_repository.bulk_create_resumes()
    ├── For each resume:
    │   ├── [S3 Client] Upload to S3
    │   ├── [File Processor] Extract text
    │   ├── [Bedrock Client] Generate embedding
    │   └── [OpenSearch Client] Index document
    ↓
User Search with Job Description
    ↓
[Frontend] POST /api/resumes/search_by_job
    ↓
[Router] resumes.search_resumes_by_job()
    ↓
[Service] matching_service.search_resumes_by_job()
    ├── [Bedrock Client] Generate job embedding
    ├── [OpenSearch Client] Vector search (Top 100)
    ├── [Bedrock Client] Rerank with Nova 2 Lite (Top 10)
    └── Format results
    ↓
Return JSON Response
```

## 🏗️ Architecture Layers

### 1. Presentation Layer (Routers)
- **File**: `app/routers/*.py`
- **Responsibility**: 
  - Handle HTTP requests/responses
  - Request validation
  - Error handling
  - Status codes

### 2. Business Logic Layer (Services)
- **File**: `app/services/*.py`
- **Responsibility**:
  - Core matching algorithms
  - File processing
  - Orchestration of clients

### 3. Data Access Layer (Repositories)
- **File**: `app/repositories/*.py`
- **Responsibility**:
  - CRUD operations
  - Data transformation
  - Integration with storage

### 4. Infrastructure Layer (Clients)
- **File**: `app/clients/*.py`
- **Responsibility**:
  - AWS service integration
  - API calls to external services
  - Error handling for external services

## 🔌 API Endpoints Summary

| Method | Endpoint | Description | Mode |
|--------|----------|-------------|------|
| GET | `/api/health` | Health check | - |
| POST | `/api/resumes/upload` | Upload single resume | A |
| POST | `/api/resumes/bulk_upload` | Upload multiple resumes | B |
| POST | `/api/resumes/search_by_job` | Search resumes by job | B |
| POST | `/api/jobs/create` | Create job posting | Admin |
| POST | `/api/jobs/search_by_resume` | Search jobs by resume | A |

## 📦 Dependencies

### Core
- `fastapi==0.104.1` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `mangum==0.17.0` - Lambda adapter

### AWS
- `boto3==1.29.7` - AWS SDK
- `opensearch-py==2.4.2` - OpenSearch client

### File Processing
- `PyPDF2==3.0.1` - PDF extraction
- `python-docx==1.1.0` - DOCX extraction

### Utilities
- `pydantic==2.5.0` - Data validation
- `pydantic-settings==2.1.0` - Settings management
- `python-multipart==0.0.6` - File upload support
- `python-json-logger==2.0.7` - Structured logging
- `watchtower==3.0.1` - CloudWatch logging

## 🔐 Security Features

1. **Secrets Management**: AWS Secrets Manager integration
2. **Input Validation**: Pydantic models for all inputs
3. **Error Handling**: Custom exceptions with proper status codes
4. **CORS**: Configurable CORS origins
5. **Rate Limiting**: Configurable rate limits (concept)
6. **WAF**: AWS WAF integration (concept)

## 🚀 Deployment Options

### Option 1: Lambda (Recommended)
- Use Mangum adapter
- Deploy via API Gateway
- Serverless, auto-scaling

### Option 2: EC2/ECS
- Run uvicorn directly
- Use load balancer
- More control over resources

## 📊 Monitoring & Logging

- **CloudWatch Logs**: Structured JSON logs
- **Error Tracking**: Custom exception handling
- **Performance**: Logging of operation times
- **Metrics**: Request counts, error rates (concept)

## 🧪 Testing Strategy

### Mock Mode
- Set `USE_MOCK=true`
- All AWS services return mock data
- Useful for local development

### Integration Testing
- Test with real AWS services
- Use test credentials
- Clean up test data

## 📝 Notes

- All file paths are relative to project root
- Environment variables loaded from `.env` file
- OpenSearch indices created via script or manually
- Frontend is a single HTML file (no build step required)

