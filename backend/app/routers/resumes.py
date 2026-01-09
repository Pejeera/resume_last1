"""
Resume Router
Handles resume upload and search operations
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import os
import uuid

from app.repositories.resume_repository import resume_repository
from app.services.matching_service import matching_service
from app.core.logging import get_logger
from app.core.exceptions import FileProcessingError

logger = get_logger(__name__)
router = APIRouter()


class ResumeUploadResponse(BaseModel):
    """Response model สำหรับการอัปโหลดเรซูเม่"""
    resume_id: str = Field(..., description="ID ของเรซูเม่ที่อัปโหลด")
    s3_url: str = Field(..., description="URL ของไฟล์ใน S3")
    name: str = Field(..., description="ชื่อไฟล์")
    created_at: str = Field(..., description="วันที่และเวลาที่อัปโหลด")


class BulkUploadResponse(BaseModel):
    """Response model สำหรับการอัปโหลดเรซูเม่หลายไฟล์"""
    results: List[dict] = Field(..., description="รายการผลลัพธ์การอัปโหลดแต่ละไฟล์")
    total: int = Field(..., description="จำนวนไฟล์ทั้งหมด")
    success: int = Field(..., description="จำนวนไฟล์ที่อัปโหลดสำเร็จ")
    failed: int = Field(..., description="จำนวนไฟล์ที่อัปโหลดล้มเหลว")


@router.post("/upload_to_s3", response_model=ResumeUploadResponse)
async def upload_resume_to_s3(file: UploadFile = File(..., description="ไฟล์เรซูเม่ (PDF หรือ DOCX)")):
    """
    📤 อัปโหลดเรซูเม่ไปยัง S3 เท่านั้น (ไม่ประมวลผล)
    
    อัปโหลดไฟล์เรซูเม่ไปยัง S3 โดยไม่ประมวลผล (ไม่ดึงข้อความ, ไม่สร้าง embedding)
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมไฟล์เรซูเม่
    - ไฟล์ที่รองรับ: **PDF** หรือ **DOCX**
    - ขนาดไฟล์: แนะนำไม่เกิน 10MB
    
    ### 2. อัปโหลดไฟล์
    - คลิก "Try it out"
    - คลิก "Choose File" และเลือกไฟล์เรซูเม่
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมี `resume_id` - เก็บไว้ใช้สำหรับประมวลผลภายหลัง
    - `s3_url` - ที่อยู่ไฟล์ใน S3
    - `name` - ชื่อไฟล์
    - `created_at` - วันที่อัปโหลด
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "resume_id": "resume-abc123",
      "s3_url": "s3://bucket/resumes/Candidate/resume-abc123.pdf",
      "name": "my_resume.pdf",
      "created_at": "2024-01-15T10:30:00"
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - **ไม่ประมวลผล**: ไฟล์จะถูกอัปโหลดไปยัง S3 เท่านั้น (ไม่ดึงข้อความ, ไม่สร้าง embedding)
    - **ประมวลผลภายหลัง**: เมื่อต้องการใช้เรซูเม่นี้ในการค้นหา ระบบจะประมวลผลอัตโนมัติ
    - **ใช้เมื่อ**: ต้องการอัปโหลดไฟล์ก่อน แล้วค่อยประมวลผลทีหลัง (เพื่อประหยัดเวลา)
    - **ไม่แนะนำ**: ถ้าต้องการใช้งานทันที ให้ใช้ `/api/resumes/upload` แทน
    
    ---
    
    ## 🔄 ความแตกต่างระหว่าง Endpoints:
    
    | Endpoint | ประมวลผล | ใช้ค้นหาได้ทันที | ใช้เมื่อ |
    |----------|----------|------------------|----------|
    | `/api/resumes/upload` | ✅ ใช่ | ✅ ใช่ | ต้องการใช้งานทันที |
    | `/api/resumes/upload_to_s3` | ❌ ไม่ | ❌ ไม่ (ต้องประมวลผลก่อน) | ต้องการอัปโหลดก่อน |
    
    ---
    
    ## 💡 Tips:
    
    - ใช้ endpoint นี้เมื่อต้องการอัปโหลดไฟล์หลายไฟล์ก่อน แล้วค่อยประมวลผลทีหลัง
    - เมื่อเรียกใช้ `/api/resumes/search_by_job` หรือ `/api/jobs/search_by_resume` ระบบจะประมวลผลอัตโนมัติ
    - ถ้าต้องการใช้งานทันที ให้ใช้ `/api/resumes/upload` แทน
    """
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Upload to S3 only (no processing)
        from app.clients.s3_client import s3_client
        from datetime import datetime
        
        upload_result = s3_client.upload_file(
            file_content=file_content,
            file_name=file.filename,
            content_type=file.content_type or "application/pdf"
        )
        
        resume_id = upload_result["file_id"]
        
        logger.info(f"Uploaded resume to S3: {resume_id}")
        return {
            "resume_id": resume_id,
            "s3_url": upload_result["s3_url"],
            "name": file.filename,
            "created_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Upload to S3 error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload resume to S3: {str(e)}"
        )


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(..., description="ไฟล์เรซูเม่ (PDF หรือ DOCX)")):
    """
    📤 อัปโหลดเรซูเม่เดียว (ประมวลผลทันที)
    
    อัปโหลดไฟล์เรซูเม่และประมวลผลทันที (ดึงข้อความ, สร้าง embedding, เก็บใน OpenSearch)
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมไฟล์เรซูเม่
    - ไฟล์ที่รองรับ: **PDF** หรือ **DOCX**
    - ขนาดไฟล์: แนะนำไม่เกิน 10MB
    
    ### 2. อัปโหลดไฟล์
    - คลิก "Try it out"
    - คลิก "Choose File" และเลือกไฟล์เรซูเม่
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมี `resume_id` - เก็บไว้ใช้สำหรับค้นหางาน
    - `s3_url` - ที่อยู่ไฟล์ใน S3
    - `name` - ชื่อไฟล์
    - `created_at` - วันที่อัปโหลด
    
    ### 4. ใช้ resume_id ต่อไป
    - ใช้ `resume_id` กับ endpoint `/api/jobs/search_by_resume` เพื่อค้นหางาน
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "resume_id": "resume-abc123",
      "s3_url": "s3://bucket/resumes/Candidate/resume-abc123.pdf",
      "name": "my_resume.pdf",
      "created_at": "2024-01-15T10:30:00"
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - การประมวลผลอาจใช้เวลาสักครู่ (ขึ้นอยู่กับขนาดไฟล์)
    - ระบบจะดึงข้อความจากไฟล์, สร้าง embedding ด้วย AI, และเก็บใน OpenSearch
    - ถ้าต้องการอัปโหลดหลายไฟล์ ให้ใช้ `/api/resumes/bulk_upload`
    - ถ้าต้องการอัปโหลดไปยัง S3 เท่านั้น (ไม่ประมวลผล) ให้ใช้ `/api/resumes/upload_to_s3`
    
    ---
    
    ## 🔄 Workflow:
    
    ```
    อัปโหลดเรซูเม่ → รับ resume_id → ค้นหางานด้วย resume_id
    ```
    """
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Create resume
        result = resume_repository.create_resume(
            file_content=file_content,
            file_name=file.filename
        )
        
        logger.info(f"Uploaded resume: {result['resume_id']}")
        return result
        
    except FileProcessingError as e:
        logger.error(f"File processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload resume: {str(e)}"
        )


@router.get("/list")
async def list_resumes():
    """
    📋 แสดงรายการเรซูเม่ทั้งหมด
    
    แสดงรายการเรซูเม่ทั้งหมดที่ถูกอัปโหลดไปยัง S3
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เรียกใช้ Endpoint
    - คลิก "Try it out" และ "Execute"
    - ไม่ต้องส่ง parameters
    
    ### 2. รับผลลัพธ์
    - Response จะมี:
      - `resumes` - รายการเรซูเม่ทั้งหมด (แต่ละรายการมี resume_id, name, s3_url, created_at)
      - `total` - จำนวนเรซูเม่ทั้งหมด
    
    ### 3. ใช้ resume_ids ต่อไป
    - เก็บ `resume_id` ที่ต้องการ
    - ใช้กับ endpoint `/api/resumes/search_by_job` เพื่อค้นหาเรซูเม่ตามงาน
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "resumes": [
        {
          "resume_id": "resume-abc123",
          "name": "john_doe_resume.pdf",
          "s3_key": "resumes/Candidate/resume-abc123.pdf",
          "s3_url": "s3://bucket/resumes/Candidate/resume-abc123.pdf",
          "created_at": "2024-01-15T10:30:00",
          "size": 245678
        },
        {
          "resume_id": "resume-def456",
          "name": "jane_smith_resume.docx",
          "s3_key": "resumes/Candidate/resume-def456.docx",
          "s3_url": "s3://bucket/resumes/Candidate/resume-def456.docx",
          "created_at": "2024-01-15T11:00:00",
          "size": 189234
        }
      ],
      "total": 2
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - ใน Mock Mode จะคืนค่ารายการว่าง (ต้อง configure AWS credentials)
    - เรซูเม่ที่แสดงคือไฟล์ที่อยู่ใน S3 เท่านั้น
    - ถ้าเรซูเม่ยังไม่ได้ประมวลผล จะต้องประมวลผลก่อนใช้ค้นหา
    """
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        import boto3
        
        # Check if in mock mode or no AWS credentials
        if settings.USE_MOCK or not settings.AWS_ACCESS_KEY_ID:
            logger.info("Mock mode or no AWS credentials: Returning empty resumes list")
            return {
                "resumes": [],
                "total": 0,
                "message": "Mock mode: No resumes available. Configure AWS credentials to access S3."
            }
        
        # Use s3_client if available, otherwise use boto3 directly
        try:
            if hasattr(s3_client, 'client') and s3_client.client:
                s3_client_boto = s3_client.client
            else:
                # Try to create S3 client, but handle errors gracefully
                try:
                    s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
                except Exception as cred_error:
                    logger.warning(f"Cannot create S3 client (no credentials?): {cred_error}")
                    return {
                        "resumes": [],
                        "total": 0,
                        "message": "S3 not configured. Set AWS credentials or enable USE_MOCK mode."
                    }
        except Exception as s3_error:
            logger.error(f"Failed to create S3 client: {s3_error}")
            # Return empty list instead of error for better UX
            return {
                "resumes": [],
                "total": 0,
                "message": f"S3 service unavailable: {str(s3_error)}"
            }
        
        # List all resume files from Candidate folder (structure: resumes/Candidate/{filename})
        candidate_prefix = f"{settings.S3_PREFIX}Candidate/"
        resumes = []
        
        try:
            paginator = s3_client_boto.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=settings.S3_BUCKET_NAME,
                Prefix=candidate_prefix
            )
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        file_key = obj['Key']
                        file_name = file_key.split('/')[-1]
                        
                        # Skip folders
                        if file_key.endswith('/'):
                            continue
                        
                        # Get file metadata to extract resume_id
                        try:
                            file_obj = s3_client_boto.head_object(
                                Bucket=settings.S3_BUCKET_NAME,
                                Key=file_key
                            )
                            
                            # Get resume_id from metadata
                            metadata = file_obj.get('Metadata', {})
                            resume_id = metadata.get('resume_id', '')
                            
                            # If no resume_id in metadata, generate one from filename or use timestamp
                            if not resume_id:
                                # Try to extract from filename or generate new ID
                                resume_id = str(uuid.uuid4())
                                logger.warning(f"No resume_id in metadata for {file_key}, generated: {resume_id}")
                            
                            last_modified = file_obj.get('LastModified', '')
                            if hasattr(last_modified, 'isoformat'):
                                created_at = last_modified.isoformat()
                            else:
                                created_at = str(last_modified) if last_modified else datetime.utcnow().isoformat()
                            
                            resumes.append({
                                "resume_id": resume_id,
                                "name": file_name,
                                "s3_key": file_key,
                                "s3_url": f"s3://{settings.S3_BUCKET_NAME}/{file_key}",
                                "created_at": created_at,
                                "size": file_obj.get('ContentLength', 0)
                            })
                        except Exception as e:
                            logger.warning(f"Failed to get metadata for {file_key}: {e}")
                            continue
        except Exception as list_error:
            logger.error(f"Failed to list S3 objects: {list_error}")
            # Return empty list instead of error for better UX
            return {
                "resumes": [],
                "total": 0,
                "message": f"Failed to list resumes from S3: {str(list_error)}"
            }
        
        logger.info(f"Listed {len(resumes)} resumes from S3")
        return {
            "resumes": resumes,
            "total": len(resumes)
        }
        
    except Exception as e:
        logger.error(f"List resumes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list resumes: {str(e)}"
        )


@router.post("/bulk_upload", response_model=BulkUploadResponse)
async def bulk_upload_resumes(files: List[UploadFile] = File(..., description="ไฟล์เรซูเม่หลายไฟล์ (PDF หรือ DOCX)")):
    """
    📤 อัปโหลดเรซูเม่หลายไฟล์พร้อมกัน
    
    อัปโหลดเรซูเม่หลายไฟล์พร้อมกันและประมวลผลทั้งหมด
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมไฟล์เรซูเม่
    - เลือกไฟล์หลายไฟล์ (PDF หรือ DOCX)
    - แต่ละไฟล์จะถูกประมวลผลแยกกัน
    
    ### 2. อัปโหลดไฟล์
    - คลิก "Try it out"
    - คลิก "Choose File" และเลือกหลายไฟล์ (กด Ctrl/Cmd + คลิก)
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมี:
      - `results` - รายการผลลัพธ์แต่ละไฟล์ (มี resume_id สำหรับไฟล์ที่สำเร็จ)
      - `total` - จำนวนไฟล์ทั้งหมด
      - `success` - จำนวนไฟล์ที่อัปโหลดสำเร็จ
      - `failed` - จำนวนไฟล์ที่ล้มเหลว
    
    ### 4. ใช้ resume_ids ต่อไป
    - เก็บ `resume_ids` จาก results ที่สำเร็จ
    - ใช้กับ endpoint `/api/resumes/search_by_job` เพื่อค้นหาเรซูเม่ตามงาน
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "results": [
        {
          "resume_id": "resume-abc123",
          "s3_url": "s3://bucket/resumes/Candidate/resume-abc123.pdf",
          "name": "resume1.pdf",
          "created_at": "2024-01-15T10:30:00"
        },
        {
          "resume_id": "resume-def456",
          "s3_url": "s3://bucket/resumes/Candidate/resume-def456.pdf",
          "name": "resume2.pdf",
          "created_at": "2024-01-15T10:31:00"
        }
      ],
      "total": 2,
      "success": 2,
      "failed": 0
    }
    ```
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - การอัปโหลดหลายไฟล์อาจใช้เวลานาน (ขึ้นอยู่กับจำนวนและขนาดไฟล์)
    - แต่ละไฟล์จะถูกประมวลผลแยกกัน (ดึงข้อความ, สร้าง embedding)
    - ถ้าไฟล์ใดล้มเหลว จะแสดง error ใน results แต่ไฟล์อื่นจะยังประมวลผลต่อ
    
    ---
    
    ## 🔄 Workflow:
    
    ```
    อัปโหลดหลายเรซูเม่ → รับ resume_ids → ค้นหาเรซูเม่ตามงานด้วย resume_ids
    ```
    """
    try:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )
        
        # Read all files
        file_data = []
        for file in files:
            if file.filename:
                content = await file.read()
                file_data.append((content, file.filename))
        
        # Bulk create
        results = resume_repository.bulk_create_resumes(file_data)
        
        success = sum(1 for r in results if "resume_id" in r)
        failed = len(results) - success
        
        logger.info(f"Bulk upload: {success} success, {failed} failed")
        
        return {
            "results": results,
            "total": len(results),
            "success": success,
            "failed": failed
        }
        
    except Exception as e:
        logger.error(f"Bulk upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk upload resumes: {str(e)}"
        )


class SearchResumesByJobRequest(BaseModel):
    """Request model สำหรับค้นหาเรซูเม่ตามงาน"""
    resume_ids: Optional[List[str]] = Field(None, description="รายการ ID ของเรซูเม่ที่ต้องการค้นหา (ถ้าไม่ระบุจะค้นหาทั้งหมด)")
    resume_keys: Optional[List[str]] = Field(None, description="รายการ S3 keys ของเรซูเม่ (ใช้แทน resume_ids ถ้ามี)")

@router.post("/search_by_job")
async def search_resumes_by_job(
    job_id: str = Query(..., description="ID ของงานที่ต้องการค้นหา"),
    request: Optional[SearchResumesByJobRequest] = None
):
    """
    🔍 ค้นหาเรซูเม่ที่เหมาะสมกับงาน (โหมด B)
    
    ค้นหาเรซูเม่ที่เหมาะสมที่สุดกับงานที่ระบุ โดยใช้ AI embedding และ vector search
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เตรียมข้อมูล
    - ต้องมี `job_id` (หาได้จาก `/api/jobs/list`)
    - (Optional) เตรียม `resume_ids` ถ้าต้องการค้นหาเฉพาะบางเรซูเม่
    
    ### 2. เรียกใช้ Endpoint
    - ใส่ `job_id` ใน query parameter
    - (Optional) ใส่ `resume_ids` ใน request body ถ้าต้องการค้นหาเฉพาะบางเรซูเม่
    - คลิก "Execute"
    
    ### 3. รับผลลัพธ์
    - Response จะมีรายการเรซูเม่ที่เหมาะสมที่สุด (เรียงตามคะแนน)
    - แต่ละเรซูเม่จะมี `resume_id`, `score` (คะแนนความเหมาะสม), และข้อมูลอื่นๆ
    
    ---
    
    ## 📝 ตัวอย่าง Request:
    
    ### กรณี 1: ค้นหาจากเรซูเม่ทั้งหมด
    ```
    Query Parameter: job_id=job-123
    Request Body: {} (ว่างเปล่า)
    ```
    
    ### กรณี 2: ค้นหาเฉพาะบางเรซูเม่
    ```json
    Query Parameter: job_id=job-123
    Request Body:
    {
      "resume_ids": ["resume-abc123", "resume-def456", "resume-ghi789"]
    }
    ```
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "query": {
        "job_id": "job-123",
        "job_description": "Software Engineer position..."
      },
      "results": [
        {
          "resume_id": "resume-abc123",
          "score": 0.95,
          "name": "john_doe_resume.pdf",
          "text_excerpt": "Experienced software engineer...",
          "metadata": {}
        },
        {
          "resume_id": "resume-def456",
          "score": 0.87,
          "name": "jane_smith_resume.docx",
          "text_excerpt": "Full-stack developer with 5 years...",
          "metadata": {}
        }
      ],
      "total": 2
    }
    ```
    
    ---
    
    ## 🔍 วิธีการทำงาน:
    
    1. **ดึงข้อมูลงาน**: ระบบจะดึง job description จาก job_id
    2. **สร้าง Query Embedding**: ใช้ AI (AWS Bedrock) สร้าง embedding จาก job description
    3. **Vector Search**: ค้นหาเรซูเม่ที่มี embedding ใกล้เคียงที่สุดใน OpenSearch
    4. **Reranking**: ใช้ AI reranking เพื่อจัดอันดับผลลัพธ์ให้แม่นยำขึ้น
    5. **คืนผลลัพธ์**: เรียงตามคะแนนจากสูงไปต่ำ
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - ถ้าไม่ระบุ `resume_ids` จะค้นหาจากเรซูเม่ทั้งหมดในระบบ
    - ถ้าเรซูเม่ยังไม่ได้ประมวลผล ระบบจะดึงจาก S3 และประมวลผลอัตโนมัติ
    - คะแนน (score) ยิ่งสูง = ยิ่งเหมาะสมกับงาน
    - ผลลัพธ์จะแสดงเรซูเม่ที่เหมาะสมที่สุดก่อน
    
    ---
    
    ## 🔄 Workflow:
    
    ```
    เลือกงาน (job_id) → ค้นหาเรซูเม่ → รับรายการเรซูเม่ที่เหมาะสมที่สุด
    ```
    """
    try:
        # Get job description from repository
        from app.repositories.job_repository import job_repository
        job = job_repository.get_job(job_id)
        
        # If not found in OpenSearch, try to get from S3
        if not job:
            logger.info(f"Job {job_id} not in OpenSearch, fetching from S3...")
            job = job_repository.get_job_from_s3(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found in S3 or OpenSearch"
            )
        
        job_description = job.get("description", "")
        if not job_description:
            job_description = job.get("text_excerpt", "")
        
        # Get resume_ids from request if provided
        # Prefer resume_keys (s3_key) if available, otherwise use resume_ids
        resume_ids = None
        if request:
            if request.resume_keys:
                # Use resume_keys (s3_key) - more reliable
                logger.info(f"Using {len(request.resume_keys)} resume_keys for search")
                # Process resumes from S3 using resume_keys
                for resume_key in request.resume_keys:
                    resume = resume_repository.get_resume_from_s3_by_key(resume_key)
                    if resume:
                        # Add resume_id to list for matching service
                        if resume_ids is None:
                            resume_ids = []
                        resume_ids.append(resume.get('id', resume_key))
            elif request.resume_ids:
                resume_ids = request.resume_ids
                # Process resumes from S3 if needed
                for resume_id in resume_ids:
                    resume = resume_repository.get_resume(resume_id)
                    if not resume:
                        logger.info(f"Resume {resume_id} not in OpenSearch, fetching from S3...")
                        resume = resume_repository.get_resume_from_s3(resume_id)
        
        # Search resumes
        results = matching_service.search_resumes_by_job(
            job_description=job_description,
            job_id=job_id,
            resume_ids=resume_ids
        )
        
        logger.info(f"Found {len(results)} matching resumes")
        return {
            "query": {
                "job_id": job_id,
                "job_description": job_description[:100] + "..." if job_description and len(job_description) > 100 else job_description
            },
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

