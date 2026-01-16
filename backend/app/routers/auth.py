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
    username: str
    password: str


class LoginResponse(BaseModel):
    idToken: str
    accessToken: str
    refreshToken: Optional[str] = None
    email: str
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
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
        # In Lambda, use IAM role; locally, use credentials from environment
        import os
        is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
        
        if is_lambda:
            # Lambda environment - use IAM role
            cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            logger.info("Using IAM role for Cognito client (Lambda environment)")
        else:
            # Local development - use credentials from environment or default
            cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
            logger.info("Using default credentials for Cognito client (local environment)")
        
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
        # Log full error details for debugging
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Login error: {str(e)}")
        logger.error(f"Error traceback: {error_trace}")
        
        # Check if it's a boto3/aws error
        if hasattr(e, 'response'):
            logger.error(f"AWS Error Response: {e.response}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"เกิดข้อผิดพลาดในการ login: {str(e)}"
        )

