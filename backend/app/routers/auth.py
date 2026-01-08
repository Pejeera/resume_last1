"""
Authentication Router
Handles user login and authentication via AWS Cognito
"""
import hmac
import hashlib
import base64
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)
router = APIRouter()

# Cognito configuration
COGNITO_USER_POOL_ID = "ap-southeast-2_bKxx54EbY"
COGNITO_CLIENT_ID = "14keq2t7pc87ncl3i26rrf5vec"
COGNITO_CLIENT_SECRET = "jjlm1l5lg2fvb2na0i2kuv75edgv8fvbskc8dq34abv5362tmdl"
COGNITO_REGION = "ap-southeast-2"


class LoginRequest(BaseModel):
    """Request model สำหรับการ login"""
    username: str = Field(..., description="Email หรือ username สำหรับ login")
    password: str = Field(..., description="Password สำหรับ login")


class LoginResponse(BaseModel):
    """Response model สำหรับการ login"""
    idToken: str = Field(..., description="JWT ID Token สำหรับใช้ใน Authorization header")
    accessToken: str = Field(..., description="Access Token จาก Cognito")
    refreshToken: Optional[str] = Field(None, description="Refresh Token สำหรับ refresh token")
    email: str = Field(..., description="Email ของผู้ใช้")
    message: str = Field(..., description="ข้อความแจ้งเตือน")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    🔐 Login เพื่อรับ JWT Token
    
    ใช้ endpoint นี้เพื่อยืนยันตัวตนและรับ JWT token จาก AWS Cognito
    
    ---
    
    ## 📋 ขั้นตอนการใช้งานแบบละเอียด:
    
    ### 1. เรียกใช้ Login Endpoint
    - ใส่ `username` (email) และ `password` ใน request body
    - กด "Try it out" และ "Execute"
    
    ### 2. รับ Token จาก Response
    - Response จะมี `idToken`, `accessToken`, และ `refreshToken`
    - **คัดลอก `idToken`** (ใช้ตัวนี้สำหรับ API calls)
    
    ### 3. Authorize ใน Swagger UI
    - คลิกปุ่ม **"Authorize"** 🔒 ที่มุมขวาบนของหน้า Swagger UI
    - ในช่อง "Value" ให้วาง `idToken` ที่คัดลอกมา
    - คลิก **"Authorize"** และ **"Close"**
    - ตอนนี้ทุก API call จะมี Authorization header อัตโนมัติ
    
    ### 4. ใช้ API อื่นๆ
    - ตอนนี้สามารถใช้ API endpoints อื่นๆ ได้แล้ว
    - ไม่ต้องใส่ token เอง เพราะ Swagger UI จะใส่ให้อัตโนมัติ
    
    ---
    
    ## 📝 ตัวอย่าง Request:
    
    ```json
    {
      "username": "user@example.com",
      "password": "YourPassword123"
    }
    ```
    
    ## 📝 ตัวอย่าง Response:
    
    ```json
    {
      "idToken": "eyJraWQiOiJcL0p...",
      "accessToken": "eyJraWQiOiJcL0p...",
      "refreshToken": "eyJjdHkiOiJKV1QiLCJlbmMiOiJBMjU2R0NNIi...",
      "email": "user@example.com",
      "message": "Login สำเร็จ! คัดลอก idToken ไปใส่ในปุ่ม Authorize ใน Swagger UI"
    }
    ```
    
    ---
    
    ## ⚠️ ข้อผิดพลาดที่อาจเกิดขึ้น:
    
    - **401 Unauthorized**: Username หรือ password ไม่ถูกต้อง
    - **403 Forbidden**: บัญชีผู้ใช้ยังไม่ได้ยืนยัน (ต้องยืนยันอีเมลก่อน)
    - **404 Not Found**: ไม่พบผู้ใช้ในระบบ
    
    ---
    
    ## 💡 Tips:
    
    - Token จะหมดอายุหลังจากเวลาหนึ่ง (ตามที่ Cognito กำหนด)
    - ถ้า token หมดอายุ ให้ login ใหม่
    - ใช้ `refreshToken` เพื่อ refresh token โดยไม่ต้อง login ใหม่ (ต้อง implement endpoint เพิ่ม)
    """
    try:
        if not request.username or not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username และ password จำเป็นต้องระบุ"
            )
        
        # Calculate SECRET_HASH
        message = request.username + COGNITO_CLIENT_ID
        secret_hash = base64.b64encode(
            hmac.new(
                COGNITO_CLIENT_SECRET.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Create Cognito client
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        
        try:
            auth_response = cognito_client.initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                ClientId=COGNITO_CLIENT_ID,
                AuthParameters={
                    'USERNAME': request.username,
                    'PASSWORD': request.password,
                    'SECRET_HASH': secret_hash
                }
            )
            
            if auth_response.get('AuthenticationResult'):
                result = auth_response['AuthenticationResult']
                logger.info(f"Login successful for user: {request.username}")
                
                return {
                    "idToken": result.get('IdToken'),
                    "accessToken": result.get('AccessToken'),
                    "refreshToken": result.get('RefreshToken'),
                    "email": request.username,
                    "message": "Login สำเร็จ! คัดลอก idToken ไปใส่ในปุ่ม Authorize ใน Swagger UI"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="การยืนยันตัวตนล้มเหลว"
                )
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'NotAuthorizedException':
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Username หรือ password ไม่ถูกต้อง"
                )
            elif error_code == 'UserNotConfirmedException':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="บัญชีผู้ใช้ยังไม่ได้ยืนยัน กรุณายืนยันอีเมลก่อน"
                )
            elif error_code == 'UserNotFoundException':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="ไม่พบผู้ใช้"
                )
            else:
                logger.error(f"Login error: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"การยืนยันตัวตนล้มเหลว: {error_code}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"เกิดข้อผิดพลาดในการ login: {str(e)}"
        )

