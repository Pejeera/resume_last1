"""
FastAPI Main Application
Supports both local development and Lambda deployment via Mangum
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.routers import resumes, jobs, health
from app.core.config import settings
from app.core.logging import setup_logging

# Initialize logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Resume ↔ Job Matching API",
    description="AI-powered resume and job matching system using AWS Bedrock and OpenSearch",
    version="1.0.0"
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

