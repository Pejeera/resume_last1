"""
Resume Router
Handles resume upload and search operations
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

from app.repositories.resume_repository import resume_repository
from app.services.matching_service import matching_service
from app.core.logging import get_logger
from app.core.exceptions import FileProcessingError

logger = get_logger(__name__)
router = APIRouter()


class ResumeUploadResponse(BaseModel):
    resume_id: str
    s3_url: str
    name: str
    created_at: str


class BulkUploadResponse(BaseModel):
    results: List[dict]
    total: int
    success: int
    failed: int


@router.post("/upload_to_s3", response_model=ResumeUploadResponse)
async def upload_resume_to_s3(file: UploadFile = File(...)):
    """
    Upload resume file to S3 only (without processing)
    
    This endpoint only uploads the file to S3 and returns the resume_id.
    Processing (text extraction, embedding) will be done later when needed.
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
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a single resume file (legacy - processes immediately)
    
    Mode A: Upload resume for job matching
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


@router.post("/bulk_upload", response_model=BulkUploadResponse)
async def bulk_upload_resumes(files: List[UploadFile] = File(...)):
    """
    Upload multiple resume files
    
    Mode B: Bulk upload resumes for job matching
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


@router.post("/search_by_job")
async def search_resumes_by_job(
    job_description: str = None,
    job_id: str = None
):
    """
    Mode B: Search top resumes for a job
    
    Either job_description or job_id must be provided
    """
    try:
        if not job_description and not job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either job_description or job_id must be provided"
            )
        
        # If job_id provided, get job description from repository
        if job_id and not job_description:
            from app.repositories.job_repository import job_repository
            job = job_repository.get_job(job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found"
                )
            job_description = job.get("description", "")
        
        # Search resumes
        results = matching_service.search_resumes_by_job(
            job_description=job_description,
            job_id=job_id
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

