"""
S3 Client for file storage
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any, List
import uuid
import json
from datetime import datetime
import os

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import FileProcessingError

logger = get_logger(__name__)


class S3Client:
    """S3 client for uploading and retrieving files"""
    
    def __init__(self):
        if settings.USE_MOCK:
            self.client = None
            logger.info("S3Client initialized in MOCK mode")
        else:
            # In Lambda, always use IAM role - don't pass credentials
            # boto3 will automatically use the Lambda execution role
            # Only use explicit credentials if we're NOT in Lambda environment
            import os
            
            # Check if we're in Lambda (Lambda sets AWS_LAMBDA_FUNCTION_NAME)
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            if is_lambda:
                # In Lambda: Use IAM role only - don't pass any credentials
                self.client = boto3.client(
                    's3',
                    region_name=settings.AWS_REGION
                )
                logger.info(f"S3Client initialized using IAM role (Lambda) for bucket: {settings.S3_BUCKET_NAME}")
            else:
                # Local dev: Use explicit credentials if provided
                client_kwargs = {
                    'service_name': 's3',
                    'region_name': settings.AWS_REGION
                }
                
                # Only add credentials if explicitly provided (for local dev)
                # Check for both None and empty string
                if (settings.AWS_ACCESS_KEY_ID and 
                    settings.AWS_SECRET_ACCESS_KEY and 
                    settings.AWS_ACCESS_KEY_ID.strip() != "" and 
                    settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
                    client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                    client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
                    logger.info(f"S3Client initialized with explicit credentials for bucket: {settings.S3_BUCKET_NAME}")
                else:
                    # Use default credentials (from ~/.aws/credentials or environment)
                    logger.info(f"S3Client initialized using default credentials for bucket: {settings.S3_BUCKET_NAME}")
                
                self.client = boto3.client(**client_kwargs)
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str = "application/octet-stream") -> dict:
        """
        Upload file to S3
        
        Structure: resumes/Candidate-{resume_id}/resume.pdf
        
        Returns:
            dict with keys: file_id, s3_url, s3_key
        """
        if settings.USE_MOCK:
            # Mock response
            file_id = str(uuid.uuid4())
            # Use folder structure: Candidate-{resume_id}/original_filename
            candidate_folder = f"Candidate-{file_id}"
            # Keep original filename
            s3_key = f"{settings.S3_PREFIX}{candidate_folder}/{file_name}"
            s3_url = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            logger.info(f"MOCK: Uploaded file {file_name} to {s3_url}")
            return {
                "file_id": file_id,
                "s3_url": s3_url,
                "s3_key": s3_key,
                "bucket": settings.S3_BUCKET_NAME
            }
        
        try:
            file_id = str(uuid.uuid4())
            # Use folder structure: Candidate-{resume_id}/original_filename
            candidate_folder = f"Candidate-{file_id}"
            # Keep original filename
            s3_key = f"{settings.S3_PREFIX}{candidate_folder}/{file_name}"
            
            self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "original_filename": file_name,
                    "candidate_id": file_id
                }
            )
            
            s3_url = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            logger.info(f"Uploaded file {file_name} to {s3_url} (Candidate-{file_id})")
            
            return {
                "file_id": file_id,
                "s3_url": s3_url,
                "s3_key": s3_key,
                "bucket": settings.S3_BUCKET_NAME
            }
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise FileProcessingError(f"Failed to upload file to S3: {str(e)}")
    
    def get_file(self, s3_key: str) -> Optional[bytes]:
        """Retrieve file from S3"""
        if settings.USE_MOCK:
            logger.info(f"MOCK: Retrieved file from {s3_key}")
            return b"mock file content"
        
        try:
            response = self.client.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"S3 get error: {e}")
            return None
    
    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3"""
        if settings.USE_MOCK:
            logger.info(f"MOCK: Deleted file {s3_key}")
            return True
        
        try:
            self.client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            logger.info(f"Deleted file {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
            return False
    
    def save_jobs_data(self, jobs_data: List[Dict[str, Any]]) -> bool:
        """Save jobs data to S3 (for mock mode persistence)"""
        s3_key = f"{settings.S3_PREFIX}jobs_data.json"
        
        if settings.USE_MOCK:
            # In mock mode, save to local file
            local_file = "jobs_data.json"
            try:
                with open(local_file, 'w', encoding='utf-8') as f:
                    json.dump(jobs_data, f, ensure_ascii=False, indent=2)
                logger.info(f"MOCK: Saved {len(jobs_data)} jobs to {local_file}")
                return True
            except Exception as e:
                logger.error(f"MOCK: Failed to save jobs data: {e}")
                return False
        
        try:
            data_json = json.dumps(jobs_data, ensure_ascii=False, indent=2).encode('utf-8')
            self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=data_json,
                ContentType='application/json',
                Metadata={
                    "saved_at": datetime.utcnow().isoformat(),
                    "total_jobs": str(len(jobs_data))
                }
            )
            logger.info(f"Saved {len(jobs_data)} jobs to S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"S3 save jobs error: {e}")
            return False
    
    def load_jobs_data(self) -> List[Dict[str, Any]]:
        """Load jobs data from S3 (for mock mode persistence)"""
        s3_key = f"{settings.S3_PREFIX}jobs_data.json"
        
        if settings.USE_MOCK:
            # In mock mode, load from local file
            local_file = "jobs_data.json"
            if os.path.exists(local_file):
                try:
                    with open(local_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # รองรับทั้ง list และ dict format
                    if isinstance(data, list):
                        jobs_data = data
                    elif isinstance(data, dict):
                        jobs_data = data.get("jobs", [])
                    else:
                        jobs_data = []
                    
                    logger.info(f"MOCK: Loaded {len(jobs_data)} jobs from {local_file}")
                    return jobs_data
                except Exception as e:
                    logger.error(f"MOCK: Failed to load jobs data: {e}")
                    return []
            else:
                logger.info(f"MOCK: Jobs data file not found: {local_file}")
                return []
        
        try:
            response = self.client.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            
            # รองรับทั้ง list และ dict format
            if isinstance(data, list):
                jobs_data = data
            elif isinstance(data, dict):
                jobs_data = data.get("jobs", [])
            else:
                jobs_data = []
            
            logger.info(f"Loaded {len(jobs_data)} jobs from S3: {s3_key}")
            return jobs_data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info(f"Jobs data not found in S3: {s3_key}")
                return []
            logger.error(f"S3 load jobs error: {e}")
            return []


# Singleton instance
s3_client = S3Client()

