"""
Job Router
Handles job creation and search operations
"""
import json
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.repositories.job_repository import job_repository
from app.services.matching_service import matching_service
from app.repositories.resume_repository import resume_repository
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class JobCreateRequest(BaseModel):
    title: str
    description: str
    metadata: Optional[dict] = None


class JobCreateResponse(BaseModel):
    job_id: str
    title: str
    created_at: str


class SearchByResumeRequest(BaseModel):
    resume_id: str


@router.get("/list")
async def list_jobs():
    """
    List all available jobs
    
    Returns list of jobs for selection in frontend
    Currently loads from S3 directly to avoid OpenSearch connection timeout
    """
    try:
        from app.clients.s3_client import s3_client
        from app.core.config import settings
        
        result = []
        
        # Load directly from S3 (skip OpenSearch to avoid timeout)
        logger.info("Loading jobs from S3...")
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
                logger.info(f"Loaded {len(result)} jobs from S3")
            else:
                logger.warning("No jobs found in S3. jobs_data.json may not exist or is empty.")
        except Exception as s3_error:
            logger.error(f"Error loading jobs from S3: {s3_error}")
            # Try alternative paths in S3
            logger.info("Trying alternative S3 paths...")
            try:
                # Try root level
                from botocore.exceptions import ClientError
                if hasattr(s3_client, 'client') and s3_client.client:
                    try:
                        response = s3_client.client.get_object(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key="jobs_data.json"
                        )
                        content = response['Body'].read().decode('utf-8')
                        data = json.loads(content)
                        
                        # รองรับทั้ง list และ dict format
                        if isinstance(data, list):
                            jobs_data = data
                        elif isinstance(data, dict):
                            jobs_data = data.get("jobs", [])
                        else:
                            jobs_data = []
                        
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
                            logger.info(f"Loaded {len(result)} jobs from S3 root (jobs_data.json)")
                    except ClientError as ce:
                        if ce.response['Error']['Code'] != 'NoSuchKey':
                            logger.error(f"S3 error: {ce}")
            except Exception as alt_error:
                logger.error(f"Alternative S3 path also failed: {alt_error}")
        
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
    Create a new job posting
    
    Admin/Mock endpoint to create jobs for testing
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
    Sync jobs from S3 to OpenSearch
    
    Loads jobs data from S3 and indexes them into OpenSearch.
    This endpoint ensures jobs from S3 are available in OpenSearch for search.
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
    Mode A: Search top jobs for a resume
    
    Takes resume_id and returns top 10 matching jobs
    Will fetch resume from S3 if not already processed
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

