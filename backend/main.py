"""
FastAPI Main Application
Supports both local development and Lambda deployment via Mangum
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from contextlib import asynccontextmanager

from app.routers import resumes, jobs, health
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Auto-seed jobs in mock mode if empty
    if settings.USE_MOCK:
        from app.clients.opensearch_client import opensearch_client
        jobs_count = len(opensearch_client._mock_data_storage.get("jobs_index", []))
        logger.info(f"Startup: Found {jobs_count} jobs in mock storage")
        
        # If no jobs, auto-seed
        if jobs_count == 0:
            logger.info("No jobs found. Auto-seeding 100 test jobs...")
            try:
                from seed_jobs import build_job_definitions
                from app.repositories.job_repository import job_repository
                
                jobs_to_create = build_job_definitions()
                for i, job_data in enumerate(jobs_to_create):
                    try:
                        job_repository.create_job(
                            title=job_data["title"],
                            description=job_data["description"],
                            metadata=job_data["metadata"]
                        )
                    except Exception as e:
                        logger.error(f"Failed to create job {job_data['title']}: {e}")
                
                final_count = len(opensearch_client._mock_data_storage.get("jobs_index", []))
                logger.info(f"Auto-seeding completed. Total jobs: {final_count}")
            except Exception as e:
                logger.error(f"Auto-seeding failed: {e}")
                logger.info("You can manually seed jobs by running 'python seed_jobs.py'")
    
    yield
    
    # Shutdown (if needed)
    pass


# Create FastAPI app
app = FastAPI(
    title="Resume ↔ Job Matching API",
    description="AI-powered resume and job matching system using AWS Bedrock and OpenSearch",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["Resumes"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

# Lambda handler
handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

