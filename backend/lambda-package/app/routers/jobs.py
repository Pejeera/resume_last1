"""
Job Router
Handles job creation and search operations
"""
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
    """
    try:
        from app.clients.opensearch_client import opensearch_client
        from app.core.config import settings
        
        if settings.USE_MOCK:
            # Get from mock storage
            jobs = opensearch_client._mock_data_storage.get("jobs_index", [])
            result = [
                {
                    "job_id": job.get("_id", ""),
                    "title": job.get("title", "N/A"),
                    "description": job.get("description", job.get("text_excerpt", ""))[:200],
                    "created_at": job.get("created_at", "")
                }
                for job in jobs
            ]
        else:
            # Get from OpenSearch (would need to implement search all)
            result = []
        
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


@router.post("/search_by_resume")
async def search_jobs_by_resume(request: SearchByResumeRequest):
    """
    Mode A: Search top jobs for a resume
    
    Takes resume_id and returns top 10 matching jobs
    """
    try:
        # Get resume
        resume = resume_repository.get_resume(request.resume_id)
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {request.resume_id} not found"
            )
        
        # Get full text from resume
        resume_text = resume.get("full_text", resume.get("text_excerpt", ""))
        
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

