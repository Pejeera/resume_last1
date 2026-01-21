"""
Health Check Router
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any

from app.clients.s3_client import get_s3_client
from app.clients.opensearch_client import OpenSearchClient
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class StatsResponse(BaseModel):
    s3: Dict[str, int] = Field(description="Counts from S3")
    opensearch: Dict[str, int] = Field(description="Counts from OpenSearch")
    summary: Dict[str, Any] = Field(description="Summary and discrepancies")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "service": "Resume Matching API",
        "version": "1.0.0"
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get counts of resumes and jobs from S3 and OpenSearch
    """
    stats = {
        "s3": {
            "resumes": 0,
            "jobs": 0
        },
        "opensearch": {
            "resumes": 0,
            "jobs": 0
        },
        "summary": {
            "resume_mismatch": False,
            "job_mismatch": False,
            "resume_difference": 0,
            "job_difference": 0
        }
    }
    
    try:
        # Count S3 resumes
        if not settings.USE_MOCK:
            try:
                s3_client = get_s3_client()
                bucket_name = settings.S3_BUCKET_NAME
                
                # Count resumes
                resume_prefix = f"{settings.S3_PREFIX}Candidate/"
                resume_count = 0
                paginator = s3_client.client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=bucket_name, Prefix=resume_prefix):
                    if 'Contents' in page:
                        resume_count += len(page['Contents'])
                stats["s3"]["resumes"] = resume_count
                
                # Count jobs
                job_prefix = f"{settings.S3_PREFIX}jobs/"
                job_count = 0
                for page in paginator.paginate(Bucket=bucket_name, Prefix=job_prefix):
                    if 'Contents' in page:
                        json_files = [obj for obj in page['Contents'] if obj['Key'].endswith('.json')]
                        job_count += len(json_files)
                stats["s3"]["jobs"] = job_count
                
                logger.info(f"S3 counts: Resumes={resume_count}, Jobs={job_count}")
            except Exception as e:
                logger.error(f"Error counting S3 files: {e}")
        
        # Count OpenSearch documents
        try:
            opensearch_client = OpenSearchClient()
            
            if settings.USE_MOCK:
                # Mock mode
                stats["opensearch"]["resumes"] = len(opensearch_client._mock_data_storage.get("resumes_index", []))
                stats["opensearch"]["jobs"] = len(opensearch_client._mock_data_storage.get("jobs_index", []))
            else:
                # Production mode
                # Count resumes
                resumes_index = "resumes_index"
                if opensearch_client.client.indices.exists(index=resumes_index):
                    response = opensearch_client.client.count(index=resumes_index)
                    stats["opensearch"]["resumes"] = response['count']
                else:
                    logger.warning(f"Index '{resumes_index}' does not exist")
                
                # Count jobs
                jobs_index = "jobs_index"
                if opensearch_client.client.indices.exists(index=jobs_index):
                    response = opensearch_client.client.count(index=jobs_index)
                    stats["opensearch"]["jobs"] = response['count']
                else:
                    logger.warning(f"Index '{jobs_index}' does not exist")
            
            logger.info(f"OpenSearch counts: Resumes={stats['opensearch']['resumes']}, Jobs={stats['opensearch']['jobs']}")
        except Exception as e:
            logger.error(f"Error counting OpenSearch documents: {e}")
        
        # Calculate differences
        resume_diff = abs(stats["s3"]["resumes"] - stats["opensearch"]["resumes"])
        job_diff = abs(stats["s3"]["jobs"] - stats["opensearch"]["jobs"])
        
        stats["summary"]["resume_mismatch"] = resume_diff > 0
        stats["summary"]["job_mismatch"] = job_diff > 0
        stats["summary"]["resume_difference"] = resume_diff
        stats["summary"]["job_difference"] = job_diff
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
    
    return stats

