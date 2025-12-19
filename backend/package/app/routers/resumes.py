"""
Resume Router
Handles resume upload and search operations
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
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


@router.get("/list")
async def list_resumes():
    """
    List all resumes from S3
    
    Returns list of resumes that have been uploaded to S3
    """
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        import boto3
        
        # Use s3_client if available, otherwise use boto3 directly
        if hasattr(s3_client, 'client') and s3_client.client:
            s3_client_boto = s3_client.client
        else:
            s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
        
        # List all resume files from Candidate folder (structure: resumes/Candidate/{filename})
        candidate_prefix = f"{settings.S3_PREFIX}Candidate/"
        resumes = []
        
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


class SearchResumesByJobRequest(BaseModel):
    resume_ids: Optional[List[str]] = None

@router.post("/search_by_job")
async def search_resumes_by_job(
    job_id: str = Query(..., description="Job ID to search for"),
    request: Optional[SearchResumesByJobRequest] = None
):
    """
    Mode B: Search top resumes for a job
    
    Uses resume_ids from request body if provided, otherwise searches all resumes
    """
    try:
        # Get job description from repository
        from app.repositories.job_repository import job_repository
        job = job_repository.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        job_description = job.get("description", "")
        
        # Get resume_ids from request if provided
        resume_ids = None
        if request and request.resume_ids:
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

