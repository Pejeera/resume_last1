"""
Job Router
Handles job creation and search operations
"""
import json
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, UploadFile, File, UploadFile, File, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any

from app.repositories.job_repository import job_repository
from app.services.matching_service import matching_service
from app.repositories.resume_repository import resume_repository
from app.core.logging import get_logger
from app.core.auth import require_auth

logger = get_logger(__name__)
router = APIRouter()


class JobMetadata(BaseModel):
    """Structured metadata for a job posting (used in Swagger UI)."""
    location: Optional[str] = Field(
        default=None,
        description="สถานที่ทำงาน เช่น Bangkok หรือ Remote"
    )
    department: Optional[str] = Field(
        default=None,
        description="แผนกหรือทีม เช่น Engineering, HR"
    )
    employment_type: Optional[str] = Field(
        default=None,
        description="ประเภทงาน เช่น full-time, part-time, contract"
    )
    experience_years: Optional[int] = Field(
        default=None,
        description="จำนวนปีประสบการณ์ที่ต้องการ เช่น 3"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="สกิลที่ต้องการ เช่น ['Python', 'AWS', 'SQL']"
    )
    responsibilities: List[str] = Field(
        default_factory=list,
        description="หน้าที่ความรับผิดชอบหลักของตำแหน่งนี้"
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="คุณสมบัติ / สิ่งที่ผู้สมัครควรมี"
    )
    scoring_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="น้ำหนักคะแนนสำหรับแต่ละหัวข้อ เช่น { 'skills': 0.5, 'experience_years': 0.3 }"
    )


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Backend Engineer",
                "description": "พัฒนาและดูแลระบบ Backend ด้วย Python/FastAPI",
                "metadata": {
                    "location": "Bangkok",
                    "department": "Engineering",
                    "employment_type": "full-time",
                    "experience_years": 3,
                    "skills": ["Python", "FastAPI", "SQL", "AWS"],
                    "responsibilities": [
                        "ออกแบบและพัฒนา REST API",
                        "ดูแล performance และ reliability ของระบบ"
                    ],
                    "requirements": [
                        "มีประสบการณ์ด้าน Backend 3 ปีขึ้นไป",
                        "เข้าใจ RESTful API และฐานข้อมูลเชิงสัมพันธ์"
                    ],
                    "scoring_weights": {
                        "skills": 0.5,
                        "experience_years": 0.3,
                        "requirements": 0.2
                    }
                }
            }
        }
    )
    title: str = Field(..., description="ชื่อตำแหน่งงาน")
    description: str = Field(..., description="รายละเอียดงาน (ข้อความยาวได้)")
    metadata: Optional[JobMetadata] = Field(
        default=None,
        description="รายละเอียดเพิ่มเติมของตำแหน่งงาน แยกเป็นหัวข้อย่อย"
    )


class JobCreateResponse(BaseModel):
    job_id: str
    title: str
    created_at: str


class JobUploadResponse(BaseModel):
    job_id: str
    title: str
    created_at: str
    message: str


class SearchByResumeRequest(BaseModel):
    resume_id: Optional[str] = None
    resume_key: Optional[str] = None


@router.get("/list")
async def list_jobs(user: dict = Depends(require_auth)):
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        
        result = []
        
        # Load directly from S3 directory: resumes/jobs/
        logger.info(f"Loading jobs from S3 bucket: {settings.S3_BUCKET_NAME}, prefix: {settings.S3_PREFIX}jobs/")
        try:
            jobs_data = s3_client.load_jobs_data()
            logger.info(f"Raw jobs_data from S3: {len(jobs_data) if jobs_data else 0} items")
            
            if jobs_data and len(jobs_data) > 0:
                result = []
                for job in jobs_data:
                    # Extract job ID - support multiple formats
                    job_id = job.get("_id") or job.get("id") or job.get("job_id") or ""
                    
                    # Skip if no valid ID
                    if not job_id:
                        logger.warning(f"Skipping job without ID: {job.get('title', 'Unknown')}")
                        continue
                    
                    # Build job object with both id and job_id for frontend compatibility
                    job_obj = {
                        "id": job_id,  # Frontend uses this
                        "job_id": job_id,  # Backward compatibility
                        "title": job.get("title", "N/A"),
                        "description": job.get("description", job.get("text_excerpt", ""))[:200],
                        "created_at": job.get("created_at", ""),
                        # Include full job data for frontend job viewer
                        "location": job.get("location") or (job.get("metadata", {}).get("location") if isinstance(job.get("metadata"), dict) else None),
                        "department": job.get("department") or (job.get("metadata", {}).get("department") if isinstance(job.get("metadata"), dict) else None),
                        "employment_type": job.get("employment_type") or (job.get("metadata", {}).get("employment_type") if isinstance(job.get("metadata"), dict) else None),
                        "experience_years": job.get("experience_years") or (job.get("metadata", {}).get("experience_years") if isinstance(job.get("metadata"), dict) else None),
                        "skills": job.get("skills") or (job.get("metadata", {}).get("skills", []) if isinstance(job.get("metadata"), dict) else []),
                        "responsibilities": job.get("responsibilities") or (job.get("metadata", {}).get("responsibilities", []) if isinstance(job.get("metadata"), dict) else []),
                        "requirements": job.get("requirements") or (job.get("metadata", {}).get("requirements", []) if isinstance(job.get("metadata"), dict) else []),
                        "scoring_weights": job.get("scoring_weights") or (job.get("metadata", {}).get("scoring_weights") if isinstance(job.get("metadata"), dict) else None),
                        "metadata": job.get("metadata", {})
                    }
                    result.append(job_obj)
                
                logger.info(f"Loaded {len(result)} jobs from S3 directory: {settings.S3_PREFIX}jobs/")
            else:
                logger.warning(f"No jobs found in S3 bucket: {settings.S3_BUCKET_NAME}, prefix: {settings.S3_PREFIX}jobs/ (directory may be empty or not exist)")
                # Clear mock storage if in mock mode
                if settings.USE_MOCK:
                    from app.clients.opensearch_client import opensearch_client
                    opensearch_client._mock_data_storage["jobs_index"] = []
                    logger.info("Cleared mock storage jobs_index")
        except Exception as s3_error:
            logger.error(f"Error loading jobs from S3: {s3_error}", exc_info=True)
            # Clear mock storage if in mock mode
            if settings.USE_MOCK:
                from app.clients.opensearch_client import opensearch_client
                opensearch_client._mock_data_storage["jobs_index"] = []
                logger.info("Cleared mock storage jobs_index due to error")
            # Don't raise error, just return empty list
            # This allows frontend to show helpful message
        
        logger.info(f"Listed {len(result)} jobs")
        return {
            "jobs": result,
            "total": len(result)
        }
        
    except Exception as e:
        logger.error(f"List jobs error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.post("/create", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest, user: dict = Depends(require_auth)):
    try:
        result = job_repository.create_job(
            title=request.title,
            description=request.description,
            # Convert Pydantic model to dict for storage/search
            metadata=request.metadata.dict() if request.metadata else None
        )
        
        logger.info(f"Created job: {result['job_id']}")
        return result
        
    except Exception as e:
        logger.error(f"Job creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@router.post("/upload", response_model=JobUploadResponse)
async def upload_job_file(file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """
    Upload a job JSON file
    Accepts a JSON file containing job data and stores it in both S3 and OpenSearch
    """
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file extension
        if not file.filename.lower().endswith('.json'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a JSON file (.json)"
            )
        
        # Read and parse JSON file
        file_content = await file.read()
        try:
            job_data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file: {str(e)}"
            )
        
        # Validate required fields
        if "title" not in job_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON file must contain 'title' field"
            )
        
        # Handle description - use text_excerpt or other fields if description is missing
        description = job_data.get("description")
        if not description:
            # Try to get from text_excerpt or other fields
            description = job_data.get("text_excerpt") or job_data.get("text") or job_data.get("content")
            
            # If still no description, try to build from available fields
            if not description:
                desc_parts = []
                if job_data.get("title"):
                    desc_parts.append(f"Position: {job_data['title']}")
                if job_data.get("requirements"):
                    if isinstance(job_data["requirements"], list):
                        desc_parts.append(f"Requirements: {' '.join(job_data['requirements'])}")
                    else:
                        desc_parts.append(f"Requirements: {job_data['requirements']}")
                if job_data.get("responsibilities"):
                    if isinstance(job_data["responsibilities"], list):
                        desc_parts.append(f"Responsibilities: {' '.join(job_data['responsibilities'])}")
                    else:
                        desc_parts.append(f"Responsibilities: {job_data['responsibilities']}")
                if job_data.get("skills"):
                    if isinstance(job_data["skills"], list):
                        desc_parts.append(f"Skills: {', '.join(job_data['skills'])}")
                    else:
                        desc_parts.append(f"Skills: {job_data['skills']}")
                
                description = "\n".join(desc_parts) if desc_parts else job_data.get("title", "No description available")
        
        # Extract metadata if present
        metadata = job_data.get("metadata")
        if not metadata and any(key in job_data for key in ["location", "department", "skills", "requirements"]):
            # If metadata fields are at top level, create metadata dict
            metadata = {}
            for key in ["location", "department", "employment_type", "experience_years", 
                       "skills", "responsibilities", "requirements", "scoring_weights"]:
                if key in job_data:
                    metadata[key] = job_data[key]
        
        # Create job using repository (will save to both S3 and OpenSearch)
        result = job_repository.create_job(
            title=job_data["title"],
            description=description,
            metadata=metadata
        )
        
        logger.info(f"Uploaded job from file: {result['job_id']}")
        return {
            "job_id": result["job_id"],
            "title": result["title"],
            "created_at": result["created_at"],
            "message": f"Job uploaded successfully from {file.filename}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload job: {str(e)}"
        )


@router.post("/search_by_resume")
async def search_jobs_by_resume(request: SearchByResumeRequest, user: dict = Depends(require_auth)):
    try:
        # Determine which identifier to use (prefer resume_key if provided)
        resume_identifier = request.resume_key or request.resume_id
        
        if not resume_identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either resume_id or resume_key must be provided"
            )
        
        # Get resume (will fetch from S3 and process if needed)
        # If resume_key is provided, use it directly; otherwise use resume_id
        resume = None
        if request.resume_key:
            # Use resume_key (s3_key) to get resume directly from S3
            logger.info(f"Using resume_key to fetch resume: {request.resume_key}")
            resume = resume_repository.get_resume_from_s3_by_key(request.resume_key)
            if not resume:
                logger.warning(f"Failed to get resume by resume_key: {request.resume_key}")
                # Try with resume_id as fallback
                if request.resume_id and request.resume_id != request.resume_key:
                    logger.info(f"Trying fallback: using resume_id: {request.resume_id}")
                    resume = resume_repository.get_resume(request.resume_id)
                    if not resume:
                        resume = resume_repository.get_resume_from_s3(request.resume_id)
        else:
            # Try OpenSearch first, then S3
            logger.info(f"Using resume_id to fetch resume: {request.resume_id}")
            resume = resume_repository.get_resume(request.resume_id)
            if not resume:
                logger.info(f"Resume {request.resume_id} not in OpenSearch, fetching from S3...")
                resume = resume_repository.get_resume_from_s3(request.resume_id)
        
        if not resume:
            error_msg = f"Resume {resume_identifier} not found in S3 or OpenSearch"
            if request.resume_key:
                error_msg += f" (s3_key: {request.resume_key})"
            if request.resume_id:
                error_msg += f" (resume_id: {request.resume_id})"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
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


class JobUpdateRequest(BaseModel):
    job: dict


@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(require_auth)):
    """
    Get job details by ID
    Tries OpenSearch first, then falls back to S3
    Returns job in the same format as list_jobs for frontend compatibility
    """
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        
        # Try OpenSearch first
        job = job_repository.get_job(job_id)
        
        # If not found in OpenSearch, try S3
        if not job:
            logger.info(f"Job {job_id} not found in OpenSearch, trying S3...")
            job = job_repository.get_job_from_s3(job_id)
        
        # If still not found, try loading directly from S3
        if not job:
            logger.info(f"Job {job_id} not found in repository, trying direct S3 load...")
            try:
                jobs_data = s3_client.load_jobs_data()
                if jobs_data:
                    for job_item in jobs_data:
                        job_id_in_data = job_item.get("_id") or job_item.get("id") or job_item.get("job_id") or ""
                        if job_id_in_data == job_id:
                            job = job_item
                            break
            except Exception as s3_error:
                logger.warning(f"Failed to load job from S3: {s3_error}")
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        # Extract job ID - support multiple formats
        job_id_final = job.get("_id") or job.get("id") or job.get("job_id") or job_id
        
        # Format job object to match list_jobs format for frontend compatibility
        job_obj = {
            "id": job_id_final,  # Frontend uses this
            "job_id": job_id_final,  # Backward compatibility
            "title": job.get("title", "N/A"),
            "description": job.get("description", job.get("text_excerpt", "")),
            "created_at": job.get("created_at", ""),
            # Include full job data for frontend job viewer
            "location": job.get("location") or (job.get("metadata", {}).get("location") if isinstance(job.get("metadata"), dict) else None),
            "department": job.get("department") or (job.get("metadata", {}).get("department") if isinstance(job.get("metadata"), dict) else None),
            "employment_type": job.get("employment_type") or (job.get("metadata", {}).get("employment_type") if isinstance(job.get("metadata"), dict) else None),
            "experience_years": job.get("experience_years") or (job.get("metadata", {}).get("experience_years") if isinstance(job.get("metadata"), dict) else None),
            "skills": job.get("skills") or (job.get("metadata", {}).get("skills", []) if isinstance(job.get("metadata"), dict) else []),
            "responsibilities": job.get("responsibilities") or (job.get("metadata", {}).get("responsibilities", []) if isinstance(job.get("metadata"), dict) else []),
            "requirements": job.get("requirements") or (job.get("metadata", {}).get("requirements", []) if isinstance(job.get("metadata"), dict) else []),
            "scoring_weights": job.get("scoring_weights") or (job.get("metadata", {}).get("scoring_weights") if isinstance(job.get("metadata"), dict) else None),
            "metadata": job.get("metadata", {}),
            "text_excerpt": job.get("text_excerpt", job.get("description", "")[:500]),
            "embeddings": job.get("embeddings")  # Include embeddings if available
        }
        
        logger.info(f"Retrieved job {job_id_final}")
        return job_obj
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job: {str(e)}"
        )


@router.put("/{job_id}")
async def update_job(job_id: str, request: JobUpdateRequest, user: dict = Depends(require_auth)):
    try:
        from app.clients.s3_client import s3_client
        from app.clients.opensearch_client import opensearch_client
        from app.core.config import settings
        from app.clients.bedrock_client import bedrock_client
        
        job_data = request.job
        
        # Validate job_id matches
        job_id_from_data = job_data.get("id") or job_data.get("job_id") or job_data.get("_id")
        if job_id_from_data and job_id_from_data != job_id:
            logger.warning(f"Job ID mismatch: path={job_id}, data={job_id_from_data}, using path parameter")
        
        # Use path parameter as source of truth
        final_job_id = job_id
        
        # Ensure job_id is set in job_data
        job_data["id"] = final_job_id
        job_data["job_id"] = final_job_id
        job_data["_id"] = final_job_id
        
        # Generate filename from title (using helper from job_repository)
        job_title = job_data.get("title", "job")
        filename = job_repository._sanitize_filename(job_title, final_job_id)
        
        # Save to S3
        jobs_prefix = f"{settings.S3_PREFIX}jobs/"
        s3_key = f"{jobs_prefix}{filename}"
        
        if settings.USE_MOCK:
            # In mock mode, save to local file
            local_dir = "jobs"
            os.makedirs(local_dir, exist_ok=True)
            local_file = os.path.join(local_dir, filename)
            
            # If old file exists with different name (based on old title), delete it
            # Search for old file with job_id pattern
            if os.path.exists(local_dir): 
                for old_file in os.listdir(local_dir):
                    if old_file.endswith(f"-{final_job_id}.json") and old_file != filename:
                        old_path = os.path.join(local_dir, old_file)
                        try:
                            os.remove(old_path)
                            logger.info(f"MOCK: Removed old job file: {old_file}")
                        except Exception as e:
                            logger.warning(f"MOCK: Failed to remove old file {old_file}: {e}")
            try:
                with open(local_file, 'w', encoding='utf-8') as f:
                    json.dump(job_data, f, ensure_ascii=False, indent=2)
                logger.info(f"MOCK: Updated job {final_job_id} in {local_file}")
            except Exception as e:
                logger.error(f"MOCK: Failed to save job: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save job: {str(e)}"
                )
        else:
            # Save to S3
            try:
                data_json = json.dumps(job_data, ensure_ascii=False, indent=2).encode('utf-8')
                s3_client.client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key,
                    Body=data_json,
                    ContentType='application/json',
                    Metadata={
                        "updated_at": datetime.utcnow().isoformat(),
                        "job_id": final_job_id
                    }
                )
                logger.info(f"Updated job {final_job_id} in S3: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to save job to S3: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save job to S3: {str(e)}"
                )
        
        # Update in OpenSearch (if not in mock mode)
        if not settings.USE_MOCK:
            try:
                # Prepare document for indexing
                document = {k: v for k, v in job_data.items() if k != "_id"}
                
                # Ensure required fields exist
                if "id" not in document:
                    document["id"] = final_job_id
                
                # Generate embedding if not already present or if description changed
                if "embeddings" not in document or not document.get("embeddings"):
                    logger.info(f"Generating embedding for updated job {final_job_id}")
                    full_text = f"{document.get('title', '')}\n{document.get('description', '')}"
                    try:
                        embedding = bedrock_client.generate_embedding(full_text)
                        document["embeddings"] = embedding
                        logger.info(f"Generated embedding for job {final_job_id} (dimension: {len(embedding)})")
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for job {final_job_id}: {e}")
                        # Continue without embedding (will be skipped in vector search)
                
                # Index to OpenSearch
                opensearch_client.index_document(
                    index_name="jobs_index",
                    doc_id=str(final_job_id),
                    document=document
                )
                logger.info(f"Updated job {final_job_id} in OpenSearch")
            except Exception as e:
                logger.warning(f"Failed to update job in OpenSearch (job still saved in S3): {e}")
                # Don't fail the request if OpenSearch update fails
        
        return {
            "message": f"Job {final_job_id} updated successfully",
            "job_id": final_job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update job error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job: {str(e)}"
        )


@router.delete("/{job_id}", summary="Delete job by ID", tags=["Jobs"])
async def delete_job(job_id: str, user: dict = Depends(require_auth)):
    """
    Delete a job by ID
    Deletes from both S3 and OpenSearch
    """
    try:
        from app.clients.s3_client import s3_client
        from app.clients.opensearch_client import opensearch_client
        from app.core.config import settings
        
        deleted_from_opensearch = False
        deleted_from_s3 = False
        errors = []
        
        # Delete from OpenSearch (try to delete, but not required if already deleted)
        try:
            if not settings.USE_MOCK:
                deleted_from_opensearch = opensearch_client.delete_document(
                    index_name="jobs_index",
                    doc_id=job_id
                )
            else:
                # In mock mode, delete from mock storage
                deleted_from_opensearch = opensearch_client.delete_document(
                    index_name="jobs_index",
                    doc_id=job_id
                )
            
            if deleted_from_opensearch:
                logger.info(f"Deleted job {job_id} from OpenSearch")
            else:
                logger.info(f"Job {job_id} not found in OpenSearch (may have been already deleted)")
        except Exception as e:
            error_msg = f"Failed to delete job {job_id} from OpenSearch: {str(e)}"
            logger.warning(error_msg)
            # Don't add to errors - OpenSearch deletion is optional if job already deleted
        
        # Find and delete from S3 (MUST succeed)
        jobs_prefix = f"{settings.S3_PREFIX}jobs/"
        s3_file_found = False
        
        try:
            if settings.USE_MOCK:
                # In mock mode, delete local file (support both old format: {job_id}.json and new format: {title}-{job_id}.json)
                local_dir = "jobs"
                if os.path.exists(local_dir):
                    for filename in os.listdir(local_dir):
                        # Check both formats: {job_id}.json and {title}-{job_id}.json
                        if filename == f"{job_id}.json" or filename.endswith(f"-{job_id}.json"):
                            local_file = os.path.join(local_dir, filename)
                            try:
                                os.remove(local_file)
                                deleted_from_s3 = True
                                s3_file_found = True
                                logger.info(f"MOCK: Deleted job {job_id} from {local_file}")
                                break
                            except Exception as e:
                                error_msg = f"MOCK: Failed to delete job file: {str(e)}"
                                logger.error(error_msg)
                                errors.append(error_msg)
                
                if not s3_file_found:
                    errors.append(f"Job {job_id} file not found in local jobs directory")
            else:
                # Delete from S3 - search for file with job_id pattern
                paginator = s3_client.client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=jobs_prefix):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            key = obj['Key']
                            # Extract filename from key
                            filename = key.split('/')[-1]
                            # Support both old format: {job_id}.json and new format: {title}-{job_id}.json
                            if filename == f"{job_id}.json" or filename.endswith(f"-{job_id}.json"):
                                s3_file_found = True
                                try:
                                    s3_client.client.delete_object(
                                        Bucket=settings.S3_BUCKET_NAME,
                                        Key=key
                                    )
                                    deleted_from_s3 = True
                                    logger.info(f"Deleted job {job_id} from S3: {key}")
                                    break
                                except Exception as e:
                                    error_msg = f"Failed to delete job {job_id} from S3: {str(e)}"
                                    logger.error(error_msg)
                                    errors.append(error_msg)
                        if deleted_from_s3:
                            break
                
                if not s3_file_found:
                    errors.append(f"Job {job_id} file not found in S3")
        except Exception as e:
            error_msg = f"Failed to delete job {job_id} from S3: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        # S3 deletion is required, OpenSearch deletion is optional (may have been already deleted)
        if deleted_from_s3:
            return {
                "message": f"Job {job_id} deleted successfully",
                "job_id": job_id,
                "deleted_from_opensearch": deleted_from_opensearch,
                "deleted_from_s3": True
            }
        else:
            # If S3 deletion failed, return error with details
            error_detail = f"Failed to delete job {job_id} from S3. Errors: {'; '.join(errors)}"
            logger.error(error_detail)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete job error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}"
        )

