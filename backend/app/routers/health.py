"""
Health Check Router
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "service": "Resume Matching API",
        "version": "1.0.0"
    }

