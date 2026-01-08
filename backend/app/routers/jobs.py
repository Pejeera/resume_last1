"""
Job Router
Handles job creation and search operations
"""
import json
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.repositories.job_repository import job_repository
from app.services.matching_service import matching_service
from app.repositories.resume_repository import resume_repository
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class JobCreateRequest(BaseModel):
    """Request model สำหรับสร้างงาน"""
    title: str = Field(..., description="ตำแหน่งงาน")
    description: str = Field(..., description="รายละเอียดงาน")
    metadata: Optional[dict] = Field(None, description="ข้อมูลเพิ่มเติม (metadata)")


class JobCreateResponse(BaseModel):
    """Response model สำหรับการสร้างงาน"""
    job_id: str = Field(..., description="ID ของงานที่สร้าง")
    title: str = Field(..., description="ตำแหน่งงาน")
    created_at: str = Field(..., description="วันที่และเวลาที่สร้าง")


class SearchByResumeRequest(BaseModel):
    """Request model สำหรับค้นหางานตามเรซูเม่"""
    resume_id: str = Field(..., description="ID ของเรซูเม่")


@router.get("/list")
async def list_jobs():
    """
    📋 แสดงรายการงานทั้งหมด
    
    แสดงรายการงานทั้งหมดที่มีในระบบ (โหลดจาก S3)
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เรียกใช้ Endpoint
    - คลิก "Try it out" และ "Execute"
    - ไม่ต้องส่ง parameters
    
    ### 2. รับผลลัพธ์
    - Response จะมี:
      - `jobs` - รายการงานทั้งหมด (แต่ละงานมี job_id, title, description, created_at)
      - `total` - จำนวนงานทั้งหมด
    
    ### 3. ใช้ job_id ต่อไป
    - เก็บ `job_id` ที่ต้องการ
    - ใช้กับ endpoint `/api/resumes/search_by_job` เพื่อค้นหาเรซูเม่ตามงาน
    - หรือใช้กับ endpoint `/api/jobs/search_by_resume` เพื่อดูรายละเอียดงาน
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "jobs": [
        {
          "job_id": "job-123",
          "title": "Senior Software Engineer",
          "description": "We are looking for an experienced software engineer...",
          "created_at": "2024-01-15T10:00:00"
        },
        {
          "job_id": "job-456",
          "title": "Data Scientist",
          "description": "Join our data science team to work on...",
          "created_at": "2024-01-15T11:00:00"
        }
      ],
      "total": 2
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - ข้อมูลโหลดจาก S3 โดยตรง (ไม่ผ่าน OpenSearch) เพื่อความเร็ว
    - ถ้ายังไม่มีงานในระบบ ให้ใช้ `/api/jobs/create` เพื่อสร้างงานใหม่
    - หรือใช้ `/api/jobs/sync_from_s3` เพื่อซิงค์งานจาก S3 ไปยัง OpenSearch
    """
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        
        result = []
        
        # Load directly from S3 directory: resumes/jobs/
        logger.info("Loading jobs from S3 directory: resumes/jobs/")
        try:
            jobs_data = s3_client.load_jobs_data()
            if jobs_data and len(jobs_data) > 0:
                result = [
                    {
                        "job_id": job.get("_id", job.get("id", job.get("job_id", ""))),
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", ""))[:200],
                        "created_at": job.get("created_at", "")
                    }
                    for job in jobs_data
                ]
                logger.info(f"Loaded {len(result)} jobs from S3 directory: resumes/jobs/")
            else:
                logger.warning("No jobs found in S3 directory: resumes/jobs/ (directory may be empty or not exist)")
                # Clear mock storage if in mock mode
                if settings.USE_MOCK:
                    from app.clients.opensearch_client import opensearch_client
                    opensearch_client._mock_data_storage["jobs_index"] = []
                    logger.info("Cleared mock storage jobs_index")
        except Exception as s3_error:
            logger.error(f"Error loading jobs from S3: {s3_error}")
            # Clear mock storage if in mock mode
            if settings.USE_MOCK:
                from app.clients.opensearch_client import opensearch_client
                opensearch_client._mock_data_storage["jobs_index"] = []
                logger.info("Cleared mock storage jobs_index due to error")
        
        logger.info(f"Listed {len(result)} jobs")
        return {
            "jobs": result,
            "total": len(result)
        }
        
    except Exception as e:
        logger.error(f"List jobs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.post("/create", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    """
    ➕ สร้างงานใหม่
    
    สร้างงานใหม่ในระบบ (สำหรับ Admin หรือการทดสอบ)
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมข้อมูลงาน
    - `title` - ตำแหน่งงาน (required)
    - `description` - รายละเอียดงาน (required)
    - `metadata` - ข้อมูลเพิ่มเติม (optional, เช่น salary, location, etc.)
    
    ### 2. เรียกใช้ Endpoint
    - คลิก "Try it out"
    - ใส่ข้อมูลใน request body
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมี `job_id` - เก็บไว้ใช้สำหรับค้นหาเรซูเม่
    - `title` - ตำแหน่งงาน
    - `created_at` - วันที่สร้าง
    
    ### 4. ใช้ job_id ต่อไป
    - ใช้ `job_id` กับ endpoint `/api/resumes/search_by_job` เพื่อค้นหาเรซูเม่
    
    ---
    
    ## 📝 ตัวอย่าง Request:
    
    ```json
    {
      "title": "Senior Software Engineer",
      "description": "We are looking for an experienced software engineer with 5+ years of experience in Python, JavaScript, and cloud technologies. Must have experience with AWS, Docker, and microservices architecture.",
      "metadata": {
        "salary": "100000-150000",
        "location": "Bangkok, Thailand",
        "type": "Full-time",
        "experience_level": "Senior"
      }
    }
    ```
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "job_id": "job-abc123",
      "title": "Senior Software Engineer",
      "created_at": "2024-01-15T10:30:00"
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - งานที่สร้างจะถูกเก็บใน OpenSearch และ S3
    - ระบบจะสร้าง embedding อัตโนมัติสำหรับการค้นหา
    - `description` ควรมีรายละเอียดครบถ้วนเพื่อให้การจับคู่แม่นยำขึ้น
    - `metadata` เป็น optional แต่แนะนำให้ใส่ข้อมูลเพิ่มเติม
    
    ---
    
    ## 🔄 Workflow:
    
    ```
    สร้างงาน → รับ job_id → ค้นหาเรซูเม่ด้วย job_id
    ```
    """
    try:
        result = job_repository.create_job(
            title=request.title,
            description=request.description,
            metadata=request.metadata
        )
        
        logger.info(f"Created job: {result['job_id']}")
        return result
        
    except Exception as e:
        logger.error(f"Job creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@router.post("/sync_from_s3")
async def sync_jobs_from_s3():
    """
    🔄 ซิงค์งานจาก S3 ไปยัง OpenSearch
    
    โหลดข้อมูลงานจาก S3 และทำการ index ลงใน OpenSearch พร้อมสร้าง embedding
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เรียกใช้ Endpoint
    - คลิก "Try it out" และ "Execute"
    - ไม่ต้องส่ง parameters
    
    ### 2. รับผลลัพธ์
    - Response จะมี:
      - `message` - ข้อความสรุปผล
      - `synced` - จำนวนงานที่ซิงค์สำเร็จ
      - `skipped` - จำนวนงานที่ข้าม (อาจมี error)
      - `total` - จำนวนงานทั้งหมดใน S3
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "message": "Successfully synced 100 jobs from S3 to OpenSearch",
      "synced": 100,
      "skipped": 0,
      "total": 100
    }
    ```
    
    ---
    
    ## 🔍 วิธีการทำงาน:
    
    1. **โหลดข้อมูลจาก S3**: ระบบจะโหลดไฟล์งานทั้งหมดจาก S3 directory (`resumes/jobs/`)
    2. **สร้าง/ตรวจสอบ Index**: สร้าง OpenSearch index ถ้ายังไม่มี
    3. **สร้าง Embedding**: สำหรับแต่ละงานที่ยังไม่มี embedding ระบบจะสร้างใหม่ด้วย AI
    4. **Index ลง OpenSearch**: เก็บงานพร้อม embedding ลงใน OpenSearch
    5. **คืนผลลัพธ์**: สรุปจำนวนงานที่ซิงค์สำเร็จ
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - **ใช้ได้เฉพาะใน Production Mode** (USE_MOCK=false)
    - การซิงค์อาจใช้เวลานานถ้ามีงานจำนวนมาก
    - งานที่ซิงค์แล้วจะสามารถใช้ค้นหาได้ทันที
    - ถ้างานมี embedding อยู่แล้ว จะไม่สร้างใหม่ (ประหยัดเวลาและค่าใช้จ่าย)
    - ถ้างานไม่มี embedding ระบบจะสร้างใหม่อัตโนมัติ
    
    ---
    
    ## 🔄 เมื่อไหร่ควรใช้:
    
    - เมื่อมีงานใหม่ใน S3 ที่ยังไม่ได้ index ใน OpenSearch
    - เมื่อต้องการอัปเดตงานใน OpenSearch ให้ตรงกับ S3
    - หลังจากอัปโหลดงานใหม่ไปยัง S3
    
    ---
    
    ## 💡 Tips:
    
    - เรียกใช้ endpoint นี้หลังจากอัปโหลดงานใหม่ไปยัง S3
    - ตรวจสอบ `skipped` count ถ้ามีค่าสูง อาจมีปัญหาในการประมวลผล
    - ใช้ `/api/jobs/list` เพื่อตรวจสอบว่างานถูกโหลดจาก S3 แล้วหรือยัง
    """
    try:
        from app.clients.s3_client import s3_client
        from app.clients.opensearch_client import opensearch_client
        from app.core.config import settings
        
        if settings.USE_MOCK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sync from S3 is only available in production mode (USE_MOCK=false)"
            )
        
        # Load jobs from S3
        logger.info("Loading jobs from S3...")
        jobs_data = s3_client.load_jobs_data()
        
        if not jobs_data:
            return {
                "message": "No jobs found in S3",
                "synced": 0,
                "total": 0
            }
        
        # Ensure index exists
        index_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "text_excerpt": {"type": "text"},
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": 1024
                    },
                    "metadata": {"type": "object"},
                    "created_at": {"type": "date"}
                }
            }
        }
        opensearch_client.create_index_if_not_exists("jobs_index", index_mapping)
        
        # Index each job to OpenSearch
        synced_count = 0
        skipped_count = 0
        from app.clients.bedrock_client import bedrock_client
        
        for job_data in jobs_data:
            try:
                # Extract job ID and document
                job_id = job_data.get("_id") or job_data.get("job_id") or job_data.get("id")
                
                if not job_id:
                    skipped_count += 1
                    continue
                
                # Prepare document for indexing
                # Remove _id if present (it's used as doc_id parameter)
                document = {k: v for k, v in job_data.items() if k != "_id"}
                
                # Ensure required fields exist
                if "id" not in document:
                    document["id"] = job_id
                
                # Generate embedding if not already present
                if "embeddings" not in document or not document.get("embeddings"):
                    logger.info(f"Generating embedding for job {job_id}")
                    full_text = f"{document.get('title', '')}\n{document.get('description', '')}"
                    try:
                        embedding = bedrock_client.generate_embedding(full_text)
                        document["embeddings"] = embedding
                        logger.info(f"Generated embedding for job {job_id} (dimension: {len(embedding)})")
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for job {job_id}: {e}")
                        # Continue without embedding (will be skipped in vector search)
                
                # Index to OpenSearch
                opensearch_client.index_document(
                    index_name="jobs_index",
                    doc_id=str(job_id),
                    document=document
                )
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync job {job_data.get('_id', job_data.get('job_id', 'unknown'))}: {e}")
                skipped_count += 1
        
        logger.info(f"Synced {synced_count} jobs from S3 to OpenSearch (skipped: {skipped_count})")
        return {
            "message": f"Successfully synced {synced_count} jobs from S3 to OpenSearch",
            "synced": synced_count,
            "skipped": skipped_count,
            "total": len(jobs_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync from S3 error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync jobs from S3: {str(e)}"
        )


@router.post("/search_by_resume")
async def search_jobs_by_resume(request: SearchByResumeRequest):
    """
    🔍 ค้นหางานที่เหมาะสมกับเรซูเม่ (โหมด A)
    
    ค้นหางานที่เหมาะสมที่สุดกับเรซูเม่ที่ระบุ โดยใช้ AI embedding และ vector search
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมข้อมูล
    - ต้องมี `resume_id` (หาได้จาก `/api/resumes/upload` หรือ `/api/resumes/list`)
    
    ### 2. เรียกใช้ Endpoint
    - ใส่ `resume_id` ใน request body
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมีรายการงาน 10 อันดับแรกที่เหมาะสมที่สุด (เรียงตามคะแนน)
    - แต่ละงานจะมี `job_id`, `score` (คะแนนความเหมาะสม), `title`, `description`, และข้อมูลอื่นๆ
    
    ---
    
    ## 📝 ตัวอย่าง Request:
    
    ```json
    {
      "resume_id": "resume-abc123"
    }
    ```
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "resume_id": "resume-abc123",
      "results": [
        {
          "job_id": "job-123",
          "score": 0.95,
          "title": "Senior Software Engineer",
          "description": "We are looking for an experienced software engineer...",
          "text_excerpt": "Senior Software Engineer position...",
          "metadata": {
            "salary": "100000-150000",
            "location": "Bangkok, Thailand"
          }
        },
        {
          "job_id": "job-456",
          "score": 0.87,
          "title": "Full-Stack Developer",
          "description": "Join our team as a full-stack developer...",
          "text_excerpt": "Full-Stack Developer position...",
          "metadata": {}
        }
      ],
      "total": 10
    }
    ```
    
    ---
    
    ## 🔍 วิธีการทำงาน:
    
    1. **ดึงข้อมูลเรซูเม่**: ระบบจะดึง resume text จาก resume_id
       - ถ้าเรซูเม่ยังไม่ได้ประมวลผล จะดึงจาก S3 และประมวลผลอัตโนมัติ
    2. **สร้าง Query Embedding**: ใช้ AI (AWS Bedrock) สร้าง embedding จาก resume text
    3. **Vector Search**: ค้นหางานที่มี embedding ใกล้เคียงที่สุดใน OpenSearch
    4. **Reranking**: ใช้ AI reranking เพื่อจัดอันดับผลลัพธ์ให้แม่นยำขึ้น
    5. **คืนผลลัพธ์**: เรียงตามคะแนนจากสูงไปต่ำ (แสดง 10 อันดับแรก)
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - ถ้าเรซูเม่ยังไม่ได้ประมวลผล ระบบจะดึงจาก S3 และประมวลผลอัตโนมัติ (อาจใช้เวลาสักครู่)
    - คะแนน (score) ยิ่งสูง = ยิ่งเหมาะสมกับเรซูเม่
    - ผลลัพธ์จะแสดงงานที่เหมาะสมที่สุดก่อน (สูงสุด 10 อันดับ)
    - ถ้าไม่มีงานในระบบ จะคืนค่ารายการว่าง
    
    ---
    
    ## 🔄 Workflow:
    
    ```
    อัปโหลดเรซูเม่ → รับ resume_id → ค้นหางาน → รับรายการงานที่เหมาะสมที่สุด
    ```
    
    ---
    
    ## 💡 Tips:
    
    - ใช้เรซูเม่ที่มีข้อมูลครบถ้วนเพื่อให้การจับคู่แม่นยำขึ้น
    - ตรวจสอบว่าเรซูเม่ถูกประมวลผลแล้ว (มี embedding) เพื่อความเร็ว
    - ใช้ `/api/jobs/list` เพื่อดูรายละเอียดงานเพิ่มเติม
    """
    try:
        # Get resume (will fetch from S3 and process if needed)
        resume = resume_repository.get_resume(request.resume_id)
        
        # If not found in OpenSearch, try to get from S3 and process
        if not resume:
            logger.info(f"Resume {request.resume_id} not in OpenSearch, fetching from S3...")
            resume = resume_repository.get_resume_from_s3(request.resume_id)
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {request.resume_id} not found in S3 or OpenSearch"
            )
        
        # Get full text from resume
        resume_text = resume.get("full_text", resume.get("text_excerpt", ""))
        
        if not resume_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resume {request.resume_id} has no text content"
            )
        
        # Search jobs
        results = matching_service.search_jobs_by_resume(
            resume_text=resume_text,
            resume_id=request.resume_id
        )
        
        logger.info(f"Found {len(results)} matching jobs for resume {request.resume_id}")
        return {
            "resume_id": request.resume_id,
            "results": results,
            "total": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

