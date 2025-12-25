# การทดสอบ Vector AI

## โหมดที่ใช้งานได้

### ✅ Mode A: Resume → Jobs
ค้นหา Jobs ที่เหมาะกับ Resume โดยใช้ Vector AI

### ✅ Mode B: Job → Resumes  
ค้นหา Resumes ที่เหมาะกับ Job โดยใช้ Vector AI

## วิธีทดสอบ

### 1. ทดสอบแบบ Interactive (แนะนำ)

```bash
cd backend
python test_vector_ai_interactive.py
```

สคริปต์จะให้คุณเลือก:
- Mode A หรือ Mode B
- เลือก Resume/Job ที่ต้องการทดสอบ
- แสดงผลลัพธ์พร้อมรายละเอียด

### 2. ทดสอบแบบอัตโนมัติ

```bash
cd backend
python test_vector_ai.py
```

สคริปต์จะทดสอบทุก endpoint อัตโนมัติ

### 3. ตั้งค่า API URL

แก้ไขในไฟล์ `.env` หรือตั้งค่า environment variable:

```bash
export API_BASE_URL=https://your-api-url.execute-api.ap-southeast-2.amazonaws.com
```

หรือแก้ไขในไฟล์ `test_vector_ai.py` หรือ `test_vector_ai_interactive.py`:

```python
API_BASE_URL = 'https://your-api-url.execute-api.ap-southeast-2.amazonaws.com'
```

## Endpoints ที่ทดสอบ

1. ✅ `GET /api/health` - Health check
2. ✅ `GET /api/jobs` - List jobs
3. ✅ `GET /api/resumes` - List resumes
4. ✅ `POST /api/jobs/sync_from_s3` - Sync jobs with embeddings
5. ✅ `POST /api/resumes/sync_from_s3` - Sync resumes with embeddings
6. ✅ `POST /api/jobs/search_by_resume` - Mode A: Search jobs by resume
7. ✅ `POST /api/resumes/search_by_job` - Mode B: Search resumes by job

## Vector AI Models

- **Embedding:** `cohere.embed-multilingual-v3` (1024 dimensions)
- **Rerank:** `amazon.nova-lite-v1:0`

## ดูเอกสารเพิ่มเติม

ดู `TEST_VECTOR_AI.md` สำหรับรายละเอียดเพิ่มเติม

