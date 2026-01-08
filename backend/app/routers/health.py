"""
Health Check Router
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class HealthResponse(BaseModel):
    """Response model สำหรับ health check"""
    status: str = Field(..., description="สถานะของบริการ")
    service: str = Field(..., description="ชื่อบริการ")
    version: str = Field(..., description="เวอร์ชันของ API")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    ❤️ ตรวจสอบสถานะของ API
    
    ใช้เพื่อตรวจสอบว่า API ทำงานอยู่หรือไม่ (Health Check)
    
    ---
    
    ## 📋 ขั้นตอนการใช้งาน:
    
    ### 1. เรียกใช้ Endpoint
    - คลิก "Try it out" และ "Execute"
    - ไม่ต้องส่ง parameters
    - **ไม่ต้อง Authentication** (ใช้ได้โดยไม่ต้อง login)
    
    ### 2. รับผลลัพธ์
    - Response จะมี:
      - `status` - สถานะของ API (ปกติจะเป็น "healthy")
      - `service` - ชื่อบริการ
      - `version` - เวอร์ชันของ API
    
    ---
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "status": "healthy",
      "service": "Resume Matching API",
      "version": "1.0.0"
    }
    ```
    
    ---
    
    ## 💡 การใช้งาน:
    
    - ใช้สำหรับ monitoring และ health checks
    - ใช้ตรวจสอบว่า API server ทำงานอยู่หรือไม่
    - ใช้ใน load balancer หรือ container orchestration (เช่น Kubernetes liveness probe)
    - ไม่ต้อง authentication เพื่อให้ง่ายต่อการตรวจสอบ
    
    ---
    
    ## ⚠️ หมายเหตุ:
    
    - Endpoint นี้ไม่ตรวจสอบ AWS services (S3, OpenSearch, Bedrock)
    - ถ้าต้องการตรวจสอบ AWS services ต้องเรียกใช้ endpoints อื่นๆ
    - Response จะเป็น "healthy" ถ้า API server ทำงานอยู่ (แม้ AWS services จะมีปัญหา)
    """
    return {
        "status": "healthy",
        "service": "Resume Matching API",
        "version": "1.0.0"
    }

