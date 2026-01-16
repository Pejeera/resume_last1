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
async def bulk_upload_resumes(files: List[UploadFile] = File(...)):
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
    resume_keys: Optional[List[str]] = None

@router.post("/search_by_job")
async def search_resumes_by_job(
    job_id: str = Query(...),
    request: Optional[SearchResumesByJobRequest] = None
):
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

