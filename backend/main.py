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
    description="""
    # ระบบจับคู่เรซูเม่และงานด้วย AI
    
    ระบบจับคู่เรซูเม่และงานด้วย AI โดยใช้ AWS Bedrock และ OpenSearch สำหรับการค้นหาและจับคู่อัจฉริยะ
    
    ---
    
    ## 📋 ฟีเจอร์หลัก
    
    ### 1. การจัดการเรซูเม่ (Resumes)
    - **อัปโหลดเรซูเม่**: อัปโหลดไฟล์เรซูเม่ (PDF, DOCX) เพื่อประมวลผลและจัดเก็บ
    - **อัปโหลดหลายไฟล์**: อัปโหลดเรซูเม่หลายไฟล์พร้อมกัน
    - **แสดงรายการเรซูเม่**: ดูรายการเรซูเม่ทั้งหมดที่อัปโหลดแล้ว
    - **ค้นหาเรซูเม่ตามงาน**: ค้นหาเรซูเม่ที่เหมาะสมกับงานที่ระบุ
    
    ### 2. การจัดการงาน (Jobs)
    - **สร้างงาน**: สร้างงานใหม่สำหรับทดสอบหรือใช้งานจริง
    - **แสดงรายการงาน**: ดูรายการงานทั้งหมดที่มีในระบบ
    - **ซิงค์งานจาก S3**: โหลดงานจาก S3 ไปยัง OpenSearch
    - **ค้นหางานตามเรซูเม่**: ค้นหางานที่เหมาะสมกับเรซูเม่ที่ระบุ
    
    ### 3. การจับคู่อัจฉริยะ
    - ใช้ AI embedding (AWS Bedrock) เพื่อสร้าง vector representations
    - ใช้ OpenSearch KNN search เพื่อค้นหาความคล้ายคลึงกัน
    - ใช้ Reranking เพื่อจัดอันดับผลลัพธ์ที่แม่นยำ
    
    ---
    
    ## 🔐 การยืนยันตัวตน (Authentication)
    
    API นี้ใช้ AWS Cognito สำหรับการยืนยันตัวตน
    
    ### ขั้นตอนการใช้งาน:
    
    1. **Login เพื่อรับ Token**
       - ไปที่ endpoint `/api/auth/login`
       - ใส่ username (email) และ password
       - รับ `idToken` จาก response
    
    2. **ใช้ Token ใน Swagger UI**
       - คลิกปุ่ม **"Authorize"** 🔒 ที่มุมขวาบน
       - วาง `idToken` ในช่อง "Value"
       - คลิก **"Authorize"** และ **"Close"**
       - ตอนนี้สามารถใช้ API อื่นๆ ได้แล้ว
    
    3. **ใช้ Token ใน API Calls**
       - ส่ง header: `Authorization: Bearer <idToken>`
       - หรือใช้ปุ่ม Authorize ใน Swagger UI (จะใส่ให้อัตโนมัติ)
    
    ### ⚠️ หมายเหตุ:
    
    - API นี้ใช้ AWS API Gateway สำหรับ production
    - ต้องมี CORS configuration ที่ถูกต้องใน API Gateway
    - Token จะหมดอายุหลังจากเวลาหนึ่ง (ตามที่ Cognito กำหนด)
    - ถ้า token หมดอายุ ให้ login ใหม่
    
    ---
    
    ## 🚀 ขั้นตอนการใช้งาน API
    
    ### โหมด A: ค้นหางานที่เหมาะสมกับเรซูเม่
    
    1. **อัปโหลดเรซูเม่**
       ```
       POST /api/resumes/upload
       - เลือกไฟล์เรซูเม่ (PDF หรือ DOCX)
       - ระบบจะประมวลผลและสร้าง embedding อัตโนมัติ
       - รับ resume_id กลับมา
       ```
    
    2. **ค้นหางานที่เหมาะสม**
       ```
       POST /api/jobs/search_by_resume
       - ส่ง resume_id ที่ได้จากขั้นตอนที่ 1
       - รับรายการงาน 10 อันดับแรกที่เหมาะสมที่สุด
       ```
    
    ### โหมด B: ค้นหาเรซูเม่ที่เหมาะสมกับงาน
    
    1. **อัปโหลดเรซูเม่หลายไฟล์** (ถ้ายังไม่มี)
       ```
       POST /api/resumes/bulk_upload
       - เลือกไฟล์เรซูเม่หลายไฟล์
       - ระบบจะประมวลผลทั้งหมด
       ```
    
    2. **เลือกงานที่ต้องการ**
       ```
       GET /api/jobs/list
       - ดูรายการงานทั้งหมด
       - เลือก job_id ที่ต้องการ
       ```
    
    3. **ค้นหาเรซูเม่ที่เหมาะสม**
       ```
       POST /api/resumes/search_by_job?job_id=<job_id>
       - ส่ง job_id และ resume_ids (ถ้าต้องการค้นหาเฉพาะบางเรซูเม่)
       - รับรายการเรซูเม่ที่เหมาะสมที่สุด
       ```
    
    ---
    
    ## 📝 ตัวอย่างการใช้งาน
    
    ### ตัวอย่าง 1: อัปโหลดเรซูเม่และค้นหางาน
    
    ```bash
    # Base URL
    BASE_URL="https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"
    
    # 1. Login
    curl -X POST "${BASE_URL}/api/auth/login" \\
         -H "Content-Type: application/json" \\
         -d '{"username": "user@example.com", "password": "password123"}'
    
    # 2. อัปโหลดเรซูเม่ (ใช้ idToken จากขั้นตอนที่ 1)
    curl -X POST "${BASE_URL}/api/resumes/upload" \\
         -H "Authorization: Bearer <idToken>" \\
         -F "file=@resume.pdf"
    
    # 3. ค้นหางาน (ใช้ resume_id จากขั้นตอนที่ 2)
    curl -X POST "${BASE_URL}/api/jobs/search_by_resume" \\
         -H "Authorization: Bearer <idToken>" \\
         -H "Content-Type: application/json" \\
         -d '{"resume_id": "resume-123"}'
    ```
    
    ### ตัวอย่าง 2: ค้นหาเรซูเม่ตามงาน
    
    ```bash
    # Base URL
    BASE_URL="https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"
    
    # 1. ดูรายการงาน
    curl -X GET "${BASE_URL}/api/jobs/list" \\
         -H "Authorization: Bearer <idToken>"
    
    # 2. ค้นหาเรซูเม่ที่เหมาะสมกับงาน
    curl -X POST "${BASE_URL}/api/resumes/search_by_job?job_id=job-456" \\
         -H "Authorization: Bearer <idToken>" \\
         -H "Content-Type: application/json" \\
         -d '{"resume_ids": ["resume-123", "resume-456"]}'
    ```
    
    ---
    
    ## 🔧 Technical Details
    
    - **Vector Embedding**: ใช้ AWS Bedrock Cohere Embed Multilingual v3 (1024 dimensions)
    - **Search Engine**: AWS OpenSearch Service with KNN vector search
    - **Reranking**: AWS Bedrock Amazon Nova Lite v1
    - **Storage**: AWS S3 สำหรับเก็บไฟล์เรซูเม่และงาน
    - **Authentication**: AWS Cognito User Pool
    
    ---
    
    ## 📚 Endpoints Overview
    
    ### Auth
    - `POST /api/auth/login` - Login เพื่อรับ JWT token
    
    ### Health
    - `GET /api/health` - ตรวจสอบสถานะ API
    
    ### Resumes
    - `POST /api/resumes/upload` - อัปโหลดเรซูเม่เดียว (ประมวลผลทันที)
    - `POST /api/resumes/upload_to_s3` - อัปโหลดไปยัง S3 เท่านั้น (ไม่ประมวลผล)
    - `POST /api/resumes/bulk_upload` - อัปโหลดเรซูเม่หลายไฟล์
    - `GET /api/resumes/list` - แสดงรายการเรซูเม่ทั้งหมด
    - `POST /api/resumes/search_by_job` - ค้นหาเรซูเม่ตามงาน
    
    ### Jobs
    - `GET /api/jobs/list` - แสดงรายการงานทั้งหมด
    - `POST /api/jobs/create` - สร้างงานใหม่
    - `POST /api/jobs/sync_from_s3` - ซิงค์งานจาก S3 ไปยัง OpenSearch
    - `POST /api/jobs/search_by_resume` - ค้นหางานตามเรซูเม่
    
    ---
    
    ## ⚠️ หมายเหตุ
    
    - ไฟล์ที่รองรับ: PDF และ DOCX เท่านั้น
    - ขนาดไฟล์: แนะนำไม่เกิน 10MB
    - การประมวลผล: อาจใช้เวลาสักครู่สำหรับไฟล์ขนาดใหญ่
    - Mock Mode: ในโหมด mock จะใช้ข้อมูลจำลองแทน AWS services จริง
    
    ---
    
    ## 🌐 API Server
    
    **API นี้ใช้ Production API Gateway เท่านั้น**
    - Server: `https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com`
    - Path prefix: `/api` (เช่น `/api/auth/login`, `/api/resumes/upload`)
    - CORS ถูกตั้งค่าแล้วบน API Gateway
    
    ### ⚠️ หมายเหตุ:
    - Swagger UI จะเรียก API ไปที่ Production Server โดยอัตโนมัติ
    - CORS configuration ถูกตั้งค่าแล้วบน API Gateway
    - ถ้าเกิด CORS error ให้ตรวจสอบ CORS configuration บน API Gateway อีกครั้ง
    """,
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
            "name": "Auth",
            "description": """
            🔐 การยืนยันตัวตน
            
            Endpoints สำหรับการ login และรับ JWT token จาก AWS Cognito
            
            **Endpoints:**
            - `POST /api/auth/login` - Login เพื่อรับ JWT token
            
            **ขั้นตอน:**
            1. เรียกใช้ `/api/auth/login` ด้วย username และ password
            2. รับ `idToken` จาก response
            3. ใช้ token ในปุ่ม "Authorize" ใน Swagger UI
            """
        },
        {
            "name": "Health",
            "description": """
            ❤️ ตรวจสอบสถานะ API
            
            Endpoints สำหรับตรวจสอบสถานะและสุขภาพของ API
            
            **Endpoints:**
            - `GET /api/health` - ตรวจสอบว่า API ทำงานอยู่หรือไม่
            
            **หมายเหตุ:** ไม่ต้อง authentication
            """
        },
        {
            "name": "Resumes",
            "description": """
            📄 การจัดการเรซูเม่
            
            Endpoints สำหรับอัปโหลด, จัดเก็บ, และค้นหาเรซูเม่
            
            **Endpoints:**
            - `POST /api/resumes/upload` - อัปโหลดเรซูเม่เดียว (ประมวลผลทันที)
            - `POST /api/resumes/upload_to_s3` - อัปโหลดไปยัง S3 เท่านั้น (ไม่ประมวลผล)
            - `POST /api/resumes/bulk_upload` - อัปโหลดเรซูเม่หลายไฟล์
            - `GET /api/resumes/list` - แสดงรายการเรซูเม่ทั้งหมด
            - `POST /api/resumes/search_by_job` - ค้นหาเรซูเม่ที่เหมาะสมกับงาน (โหมด B)
            
            **Workflow:**
            - โหมด A: อัปโหลดเรซูเม่ → ค้นหางาน
            - โหมด B: อัปโหลดเรซูเม่หลายไฟล์ → ค้นหาเรซูเม่ตามงาน
            """
        },
        {
            "name": "Jobs",
            "description": """
            💼 การจัดการงาน
            
            Endpoints สำหรับสร้าง, จัดเก็บ, และค้นหางาน
            
            **Endpoints:**
            - `GET /api/jobs/list` - แสดงรายการงานทั้งหมด
            - `POST /api/jobs/create` - สร้างงานใหม่
            - `POST /api/jobs/sync_from_s3` - ซิงค์งานจาก S3 ไปยัง OpenSearch
            - `POST /api/jobs/search_by_resume` - ค้นหางานที่เหมาะสมกับเรซูเม่ (โหมด A)
            
            **Workflow:**
            - โหมด A: อัปโหลดเรซูเม่ → ค้นหางาน
            - โหมด B: เลือกงาน → ค้นหาเรซูเม่ตามงาน
            """
        }
    ]
)

# CORS middleware - อนุญาตทุก origin เพื่อแก้ปัญหา CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # อนุญาตทุก origin เพื่อแก้ปัญหา CORS
    allow_credentials=True,
    allow_methods=["*"],  # อนุญาตทุก HTTP method
    allow_headers=["*"],  # อนุญาตทุก header รวมถึง Authorization
    expose_headers=["*"],  # เปิดเผยทุก header ใน response
)

# Root endpoint for testing
@app.get("/", tags=["Root"])
async def root():
    """
    จุดเริ่มต้นของ API
    
    ใช้สำหรับทดสอบว่า API ทำงานอยู่หรือไม่
    """
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
            "bearerFormat": "JWT",
            "description": "JWT token from AWS Cognito. Get token from /api/auth/login endpoint or Cognito Hosted UI"
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

