# API Examples

ตัวอย่างการเรียกใช้ API สำหรับทั้ง 2 โหมด

## Mode A: Resume → Jobs

### 1. Upload Resume

```bash
curl -X POST "http://localhost:8000/api/resumes/upload" \
  -F "file=@resume.pdf"
```

**Response:**
```json
{
  "resume_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "s3_url": "s3://resume-matching-bucket/resumes/a1b2c3d4-e5f6-7890-abcd-ef1234567890/resume.pdf",
  "name": "resume.pdf",
  "created_at": "2024-01-15T10:30:00.000000"
}
```

### 2. Search Jobs by Resume

```bash
curl -X POST "http://localhost:8000/api/jobs/search_by_resume" \
  -H "Content-Type: application/json" \
  -d '{
    "resume_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

**Response:**
```json
{
  "resume_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "results": [
    {
      "rank": 1,
      "job_id": "job-001",
      "job_title": "Senior Backend Engineer",
      "match_score": 0.95,
      "rerank_score": 0.92,
      "reasons": "ผู้สมัครมีประสบการณ์ตรงกับตำแหน่งงาน มีทักษะ Python และ FastAPI ที่ตรงกับความต้องการ มีประสบการณ์กับ AWS และ microservices architecture",
      "highlighted_skills": ["Python", "FastAPI", "AWS", "Microservices"],
      "gaps": ["AWS certification", "Kubernetes experience"],
      "recommended_questions_for_interview": [
        "คุณมีประสบการณ์กับ AWS Lambda มากแค่ไหน?",
        "คุณเคยใช้ OpenSearch ในการทำ vector search หรือไม่?",
        "คุณมีประสบการณ์กับ container orchestration หรือไม่?"
      ],
      "metadata": {}
    },
    {
      "rank": 2,
      "job_id": "job-002",
      "job_title": "Full-Stack Developer",
      "match_score": 0.88,
      "rerank_score": 0.85,
      "reasons": "ผู้สมัครมีทักษะทั้ง backend และ frontend แต่ขาดประสบการณ์กับ React",
      "highlighted_skills": ["Python", "FastAPI", "JavaScript"],
      "gaps": ["React", "TypeScript"],
      "recommended_questions_for_interview": [
        "คุณมีประสบการณ์กับ React หรือไม่?",
        "คุณเคยใช้ TypeScript ในการพัฒนา frontend หรือไม่?"
      ],
      "metadata": {}
    }
  ],
  "total": 10
}
```

## Mode B: Job → Resumes

### 1. Create Job (Admin/Mock)

```bash
curl -X POST "http://localhost:8000/api/jobs/create" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Backend Engineer",
    "description": "We are looking for an experienced Backend Engineer with strong Python and FastAPI skills. Experience with AWS, microservices, and vector databases is a plus.",
    "metadata": {
      "location": "Bangkok",
      "salary_range": "100k-150k",
      "experience_required": "5+ years"
    }
  }'
```

**Response:**
```json
{
  "job_id": "job-001",
  "title": "Senior Backend Engineer",
  "created_at": "2024-01-15T10:30:00.000000"
}
```

### 2. Bulk Upload Resumes

```bash
curl -X POST "http://localhost:8000/api/resumes/bulk_upload" \
  -F "files=@resume1.pdf" \
  -F "files=@resume2.docx" \
  -F "files=@resume3.txt"
```

**Response:**
```json
{
  "results": [
    {
      "resume_id": "resume-001",
      "s3_url": "s3://bucket/resumes/resume-001/resume1.pdf",
      "name": "resume1.pdf",
      "created_at": "2024-01-15T10:30:00.000000"
    },
    {
      "resume_id": "resume-002",
      "s3_url": "s3://bucket/resumes/resume-002/resume2.docx",
      "name": "resume2.docx",
      "created_at": "2024-01-15T10:30:01.000000"
    },
    {
      "resume_id": "resume-003",
      "s3_url": "s3://bucket/resumes/resume-003/resume3.txt",
      "name": "resume3.txt",
      "created_at": "2024-01-15T10:30:02.000000"
    }
  ],
  "total": 3,
  "success": 3,
  "failed": 0
}
```

### 3. Search Resumes by Job (using job_description)

```bash
curl -X POST "http://localhost:8000/api/resumes/search_by_job?job_description=We%20are%20looking%20for%20an%20experienced%20Backend%20Engineer" \
  -X POST
```

### 4. Search Resumes by Job (using job_id)

```bash
curl -X POST "http://localhost:8000/api/resumes/search_by_job?job_id=job-001" \
  -X POST
```

**Response:**
```json
{
  "query": {
    "job_id": "job-001",
    "job_description": "We are looking for an experienced Backend Engineer..."
  },
  "results": [
    {
      "rank": 1,
      "resume_id": "resume-001",
      "resume_name": "resume1.pdf",
      "experience_summary": "5 years of experience in backend development with Python, FastAPI, and AWS. Strong background in microservices architecture...",
      "match_score": 0.95,
      "rerank_score": 0.92,
      "fit_reasons": "ผู้สมัครมีประสบการณ์ตรงกับตำแหน่งงาน มีทักษะ Python และ FastAPI ที่ตรงกับความต้องการ มีประสบการณ์กับ AWS และ microservices",
      "risks": ["ไม่มี AWS certification", "ขาดประสบการณ์กับ Kubernetes"],
      "highlighted_skills": ["Python", "FastAPI", "AWS", "Microservices"],
      "suggested_next_step": "ติดต่อเพื่อสัมภาษณ์",
      "metadata": {}
    },
    {
      "rank": 2,
      "resume_id": "resume-002",
      "resume_name": "resume2.docx",
      "experience_summary": "3 years of experience in web development...",
      "match_score": 0.82,
      "rerank_score": 0.78,
      "fit_reasons": "ผู้สมัครมีทักษะพื้นฐานที่จำเป็น แต่ขาดประสบการณ์กับ microservices",
      "risks": ["ประสบการณ์น้อยกว่า 5 ปี", "ขาดประสบการณ์กับ microservices"],
      "highlighted_skills": ["Python", "FastAPI"],
      "suggested_next_step": "พิจารณาเพิ่มเติม",
      "metadata": {}
    }
  ],
  "total": 10
}
```

## Health Check

```bash
curl -X GET "http://localhost:8000/api/health"
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Resume Matching API",
  "version": "1.0.0"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "No file provided"
}
```

### 404 Not Found
```json
{
  "detail": "Resume abc123 not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to generate embedding: ..."
}
```

