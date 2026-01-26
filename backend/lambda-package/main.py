"""
FastAPI Main Application
Supports both local development and Lambda deployment via Mangum

Authentication:
- This API uses AWS API Gateway JWT Authorizer (Cognito User Pool)
- API Gateway verifies JWT tokens before requests reach this backend
- Backend does NOT verify JWT tokens - it trusts API Gateway authentication
- User claims are available via: event.requestContext.authorizer.jwt.claims
- Use app.core.auth utilities to read user information from API Gateway claims
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load .env from infra directory (if exists)
env_path = Path(__file__).parent.parent / 'infra' / '.env'
if env_path.exists():
    load_dotenv(env_path)

from app.routers import resumes, jobs, health, auth
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
        
        # If no jobs, try to load from S3 first, then auto-seed if still empty
        if jobs_count == 0:
            logger.info("No jobs found in memory. Trying to load from S3...")
            try:
                from app.clients.s3_client import s3_client
                jobs_data = s3_client.load_jobs_data()
                if jobs_data:
                    opensearch_client._mock_data_storage["jobs_index"] = jobs_data
                    logger.info(f"Loaded {len(jobs_data)} jobs from S3")
                else:
                    logger.info("No jobs in S3. Auto-seeding 100 test jobs...")
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
                    
                    # Save to S3 after seeding
                    final_jobs = opensearch_client._mock_data_storage.get("jobs_index", [])
                    if final_jobs:
                        s3_client.save_jobs_data(final_jobs)
                    
                    final_count = len(final_jobs)
                    logger.info(f"Auto-seeding completed. Total jobs: {final_count}")
            except Exception as e:
                logger.error(f"Failed to load/seed jobs: {e}")
                logger.info("You can manually seed jobs by running 'python seed_jobs.py'")
    
    yield
    
    # Shutdown (if needed)
    pass


# Create FastAPI app
app = FastAPI(
    title="Resume ↔ Job Matching API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {
            "url": "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com",
            "description": "Production API Gateway - CORS configured"
        }
    ],
    openapi_tags=[
        {
            "name": "Auth"
        },
        {
            "name": "Health"
        },
        {
            "name": "Resumes"
        },
        {
            "name": "Jobs"
        }
    ]
)

# CORS middleware - อนุญาตทุก origin เพื่อแก้ปัญหา CORS
# สำหรับ local development: รองรับ localhost:3000 และ localhost:8000
# สำหรับ production: รองรับ API Gateway origin และ Swagger UI

# กำหนด CORS origins สำหรับ local development และ API Gateway
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com",  # API Gateway origin for Swagger UI
]

# ถ้า settings.CORS_ORIGINS ไม่ใช่ ["*"] ให้เพิ่มเข้าไปด้วย
if settings.CORS_ORIGINS and settings.CORS_ORIGINS != ["*"]:
    cors_origins.extend(settings.CORS_ORIGINS)
elif settings.CORS_ORIGINS == ["*"]:
    # ถ้า CORS_ORIGINS = ["*"] ให้ใช้ ["*"] เพื่ออนุญาตทุก origin
    cors_origins = ["*"]

# ใช้ cors_origins เสมอเพื่อให้รองรับ localhost:3000 และใช้ allow_credentials=True ได้
# แต่ถ้าใช้ ["*"] จะไม่สามารถใช้ allow_credentials=True ได้
# สำหรับ login endpoint ต้องใช้ allow_credentials=False เมื่อใช้ ["*"]
if cors_origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # อนุญาตทุก origin (รวมถึง Swagger UI จาก API Gateway)
        allow_credentials=False,  # ไม่สามารถใช้ credentials กับ "*" ได้ แต่ login endpoint ไม่ต้องการ credentials
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # อนุญาตทุก HTTP method
        allow_headers=["*"],  # อนุญาตทุก header รวมถึง Authorization, Content-Type
        expose_headers=["*"],  # เปิดเผยทุก header ใน response
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,  # รองรับ localhost:3000 และ origin อื่นๆ
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # อนุญาตทุก HTTP method
        allow_headers=["*"],  # อนุญาตทุก header รวมถึง Authorization, Content-Type
        expose_headers=["*"],  # เปิดเผยทุก header ใน response
    )

# Root endpoint for testing
@app.get("/", tags=["Root"])
async def root():
    return {"message": "Resume Matching API is running", "version": "1.0.0"}

# Customize OpenAPI schema to add JWT security
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
        tags=app.openapi_tags,
    )
    
    # Add JWT Bearer security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Add security requirement to all endpoints except login and health
    # This tells Swagger UI to include Authorization header
    for path, methods in openapi_schema["paths"].items():
        for method, operation in methods.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                # Skip login and health endpoints (they don't need auth)
                if "/auth/login" in path or "/health" in path or path == "/":
                    continue
                # Add security requirement
                if "security" not in operation:
                    operation["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["Resumes"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

# Local development only
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

