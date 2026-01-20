"""
Script to create a test job
"""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.repositories.job_repository import job_repository
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_test_job():
    """Create a test job with the provided data"""
    job_data = {
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
    
    try:
        print("Creating job...")
        print(f"Title: {job_data['title']}")
        print(f"Description: {job_data['description'][:50]}...")
        
        result = job_repository.create_job(
            title=job_data["title"],
            description=job_data["description"],
            metadata=job_data["metadata"]
        )
        
        print(f"\n[SUCCESS] Job created successfully!")
        print(f"Job ID: {result['job_id']}")
        print(f"Title: {result['title']}")
        print(f"Created at: {result['created_at']}")
        
        return result
        
    except Exception as e:
        print(f"\n[ERROR] Error creating job: {e}")
        logger.error(f"Error creating job: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    create_test_job()
