# Vector AI Testing Guide

## โหมดที่ใช้งานได้

### 1. Mode A: Resume → Jobs (ค้นหา Jobs จาก Resume)

**Endpoint:** `POST /api/jobs/search_by_resume`

**การทำงาน:**
1. รับ `resume_key` หรือ `resume_id` จาก request
2. ดึงไฟล์ Resume จาก S3
3. สร้าง **embedding** จากข้อความใน Resume (ใช้ Cohere Embed Multilingual v3)
4. ค้นหาใน `jobs_index` ด้วย **Vector Search** (KNN)
5. เลือก Top 3 jobs จาก embedding score
6. **Rerank** ด้วย Nova Lite v1 เพื่อให้เหตุผลและคะแนนที่ละเอียดขึ้น
7. คืน Top 3 jobs พร้อม:
   - `match_score`: คะแนนจาก vector similarity (0-100%)
   - `rerank_score`: คะแนนจาก Nova Lite (0.0-1.0)
   - `reasons`: เหตุผลว่าทำไมเหมาะ
   - `highlighted_skills`: ทักษะที่โดดเด่น
   - `gaps`: จุดที่ขาด
   - `recommended_questions_for_interview`: คำถามแนะนำสำหรับสัมภาษณ์

**Request:**
```json
{
  "resume_key": "resumes/Candidate/resume.pdf"
}
```

**Response:**
```json
{
  "resume_id": "resumes/Candidate/resume.pdf",
  "results": [
    {
      "rank": 1,
      "job_id": "job_123",
      "job_title": "Software Engineer",
      "match_score": 85.5,
      "rerank_score": 0.92,
      "reasons": "Resume มีประสบการณ์ตรงกับตำแหน่ง...",
      "highlighted_skills": ["Python", "AWS", "Docker"],
      "gaps": ["Kubernetes"],
      "recommended_questions_for_interview": ["คำถาม1", "คำถาม2"]
    }
  ],
  "total": 3
}
```

---

### 2. Mode B: Job → Resumes (ค้นหา Resumes จาก Job)

**Endpoint:** `POST /api/resumes/search_by_job?job_id={job_id}`

**การทำงาน:**
1. รับ `job_id` จาก query string และ `resume_keys` จาก request body
2. ดึง Job จาก OpenSearch
3. สร้าง **embedding** จาก Job description (ใช้ Cohere Embed Multilingual v3)
4. ค้นหาใน `resumes_index` ด้วย **Vector Search** (KNN) - กรองเฉพาะ resumes ที่ระบุ
5. เลือก Top 3 resumes จาก embedding score
6. **Rerank** ด้วย Nova Lite v1
7. คืน Top 3 resumes พร้อมข้อมูลเหมือน Mode A

**Request:**
```json
{
  "resume_keys": [
    "resumes/Candidate/resume1.pdf",
    "resumes/Candidate/resume2.pdf",
    "resumes/Candidate/resume3.pdf"
  ]
}
```

**Response:**
```json
{
  "query": {
    "job_id": "job_123",
    "job_description": "Software Engineer position..."
  },
  "results": [
    {
      "rank": 1,
      "resume_id": "resume1",
      "resume_name": "resume1.pdf",
      "match_score": 90.2,
      "rerank_score": 0.95,
      "reasons": "Resume มีทักษะตรงกับ Job...",
      "highlighted_skills": ["Python", "AWS"],
      "gaps": [],
      "recommended_questions_for_interview": ["คำถาม1"]
    }
  ],
  "total": 3
}
```

---

## Sync Endpoints (สร้าง Embeddings)

### 3. Sync Jobs from S3 to OpenSearch

**Endpoint:** `POST /api/jobs/sync_from_s3`

**การทำงาน:**
- อ่านไฟล์ Jobs จาก S3 (`resumes/jobs/*.json`)
- สร้าง embedding สำหรับแต่ละ Job
- เก็บใน OpenSearch index `jobs_index` พร้อม embeddings

**Response:**
```json
{
  "message": "Successfully synced 10 jobs from S3 to OpenSearch",
  "synced": 10,
  "skipped": 0,
  "total": 10
}
```

---

### 4. Sync Resumes from S3 to OpenSearch

**Endpoint:** `POST /api/resumes/sync_from_s3`

**การทำงาน:**
- อ่านไฟล์ Resumes จาก S3 (`resumes/Candidate/*.pdf`)
- สร้าง embedding สำหรับแต่ละ Resume
- เก็บใน OpenSearch index `resumes_index` พร้อม embeddings

**Response:**
```json
{
  "message": "Successfully synced 5 resumes from S3 to OpenSearch",
  "synced": 5,
  "skipped": 0,
  "total": 5
}
```

---

## List Endpoints

### 5. List Jobs

**Endpoint:** `GET /api/jobs` หรือ `GET /api/jobs/list`

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job_123",
      "title": "Software Engineer",
      "description": "Job description...",
      "created_at": "2024-01-01"
    }
  ],
  "total": 10
}
```

---

### 6. List Resumes

**Endpoint:** `GET /api/resumes` หรือ `GET /api/resumes/list`

**Response:**
```json
{
  "resumes": [
    {
      "key": "resumes/Candidate/resume.pdf",
      "filename": "resume.pdf",
      "size": 102400,
      "last_modified": "2024-01-01T00:00:00"
    }
  ]
}
```

---

## Vector AI Models ใช้

1. **Embedding Model:** `cohere.embed-multilingual-v3`
   - Dimension: 1024
   - ใช้สร้าง embeddings สำหรับทั้ง Jobs และ Resumes
   - รองรับภาษาไทยและหลายภาษา

2. **Rerank Model:** `amazon.nova-lite-v1:0`
   - ใช้ rerank Top 3 results
   - ให้เหตุผลและคะแนนละเอียดขึ้น
   - รองรับภาษาไทย

---

## การทดสอบ

### วิธีที่ 1: ใช้สคริปต์ทดสอบ

```bash
cd backend
python test_vector_ai.py
```

### วิธีที่ 2: ทดสอบด้วย curl

**Test Mode A:**
```bash
curl -X POST https://your-api-url/api/jobs/search_by_resume \
  -H "Content-Type: application/json" \
  -d '{"resume_key": "resumes/Candidate/resume.pdf"}'
```

**Test Mode B:**
```bash
curl -X POST "https://your-api-url/api/resumes/search_by_job?job_id=job_123" \
  -H "Content-Type: application/json" \
  -d '{"resume_keys": ["resumes/Candidate/resume1.pdf", "resumes/Candidate/resume2.pdf"]}'
```

### วิธีที่ 3: ใช้ Frontend

เปิด `frontend/index.html` ใน browser และทดสอบผ่าน UI

---

## หมายเหตุ

- **Vector Search** ใช้ KNN (k-nearest neighbors) ใน OpenSearch
- **Embeddings** ถูกเก็บใน field `embeddings` (type: `knn_vector`, dimension: 1024)
- **Top 3** ถูกเลือกจาก embedding score ก่อน rerank
- **Rerank** ใช้ Nova Lite เพื่อให้ผลลัพธ์ละเอียดและมีเหตุผลมากขึ้น
- ถ้า vector search ล้มเหลว จะ fallback เป็น text-based search

