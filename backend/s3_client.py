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
            self.client = boto3.client(
                's3',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None
            )
            logger.info(f"S3Client initialized for bucket: {settings.S3_BUCKET_NAME}")
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str = "application/octet-stream") -> dict:
        """
        Upload file to S3
        
        Returns:
            dict with keys: file_id, s3_url, s3_key
        """
        if settings.USE_MOCK:
            # Mock response
            file_id = str(uuid.uuid4())
            s3_key = f"{settings.S3_PREFIX}{file_id}/{file_name}"
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
            s3_key = f"{settings.S3_PREFIX}{file_id}/{file_name}"
            
            self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "original_filename": file_name
                }
            )
            
            s3_url = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            logger.info(f"Uploaded file {file_name} to {s3_url}")
            
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
        """
        Load jobs data from S3 directory: resumes/jobs/
        Reads all .json files, each file = 1 job object
        Returns list of job objects
        """
        jobs_prefix = f"{settings.S3_PREFIX}jobs/"
        
        if settings.USE_MOCK:
            # In mock mode, load from local directory
            local_dir = "jobs"
            jobs_data = []
            
            if os.path.exists(local_dir) and os.path.isdir(local_dir):
                try:
                    for filename in os.listdir(local_dir):
                        if filename.endswith('.json'):
                            file_path = os.path.join(local_dir, filename)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    job_data = json.load(f)
                                    
                                # Ensure it's a dict (single job object)
                                if isinstance(job_data, dict):
                                    jobs_data.append(job_data)
                                elif isinstance(job_data, list):
                                    # If file contains array, add all items
                                    jobs_data.extend(job_data)
                                    
                            except json.JSONDecodeError as e:
                                logger.warning(f"MOCK: Failed to parse {filename}: {e}")
                                continue
                            except Exception as e:
                                logger.warning(f"MOCK: Error reading {filename}: {e}")
                                continue
                    
                    logger.info(f"MOCK: Loaded {len(jobs_data)} jobs from {local_dir}/")
                    return jobs_data
                except Exception as e:
                    logger.error(f"MOCK: Failed to load jobs from directory: {e}")
                    return []
            else:
                logger.info(f"MOCK: Jobs directory not found: {local_dir}")
                return []
        
        try:
            # List all objects in resumes/jobs/ prefix
            jobs_data = []
            paginator = self.client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=jobs_prefix):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    
                    # Only process .json files
                    if not s3_key.endswith('.json'):
                        continue
                    
                    try:
                        # Get and parse JSON file
                        response = self.client.get_object(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key=s3_key
                        )
                        content = response['Body'].read().decode('utf-8')
                        job_data = json.loads(content)
                        
                        # Each file should contain 1 job object (dict)
                        if isinstance(job_data, dict):
                            jobs_data.append(job_data)
                        elif isinstance(job_data, list):
                            # If file contains array, add all items
                            jobs_data.extend(job_data)
                        else:
                            logger.warning(f"Invalid job data format in {s3_key}: expected dict or list")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON from {s3_key}: {e}")
                        continue
                    except ClientError as e:
                        logger.warning(f"Failed to read {s3_key}: {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing {s3_key}: {e}")
                        continue
            
            logger.info(f"Loaded {len(jobs_data)} jobs from S3: {jobs_prefix}")
            return jobs_data
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchBucket' or error_code == 'AccessDenied':
                logger.warning(f"Cannot access S3 bucket or prefix {jobs_prefix}: {e}")
            else:
                logger.error(f"S3 load jobs error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading jobs: {e}")
            return []


# Singleton instance
s3_client = S3Client()

