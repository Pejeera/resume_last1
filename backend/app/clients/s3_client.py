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
            # Use IAM role credentials if no explicit credentials provided
            # This allows Lambda to use its IAM role automatically
            client_kwargs = {
                'service_name': 's3',
                'region_name': settings.AWS_REGION
            }
            
            # In Lambda, always use IAM role (don't pass credentials)
            # Only use explicit credentials for local development
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            if is_lambda:
                # Lambda environment - use IAM role, don't pass credentials
                logger.info(f"S3Client initialized using IAM role for bucket: {settings.S3_BUCKET_NAME} (Lambda environment)")
            else:
                # Local development - only add credentials if explicitly provided
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
        
        Structure: resumes/Candidate/{original_filename}
        All resumes stored in Candidate folder with original filename
        
        Returns:
            dict with keys: file_id, s3_url, s3_key
        """
        if settings.USE_MOCK:
            # Mock response
            file_id = str(uuid.uuid4())
            # Structure: resumes/Candidate/{original_filename}
            s3_key = f"{settings.S3_PREFIX}Candidate/{file_name}"
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
            # Structure: resumes/Candidate/{original_filename}
            # Use original filename, all resumes in Candidate folder
            s3_key = f"{settings.S3_PREFIX}Candidate/{file_name}"
            
            self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "original_filename": file_name,
                    "resume_id": file_id
                }
            )
            
            s3_url = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            logger.info(f"Uploaded file {file_name} to {s3_url} (resume_id: {file_id})")
            
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
            # First check if file exists
            try:
                self.client.head_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key
                )
            except ClientError as head_error:
                error_code = head_error.response.get('Error', {}).get('Code', '')
                if error_code == '404' or error_code == 'NoSuchKey':
                    logger.warning(f"File {s3_key} does not exist in S3 (may have been already deleted)")
                    return True  # Consider it successful if file doesn't exist
                else:
                    logger.error(f"S3 head_object error for {s3_key}: {error_code} - {head_error}")
                    raise head_error
            
            # File exists, proceed with deletion
            self.client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            logger.info(f"Deleted file {s3_key} from S3 bucket {settings.S3_BUCKET_NAME}")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 delete error for {s3_key}: Code={error_code}, Message={error_message}")
            logger.error(f"Full error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file {s3_key} from S3: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
            logger.info(f"Loading jobs from S3: bucket={settings.S3_BUCKET_NAME}, prefix={jobs_prefix}")
            jobs_data = []
            paginator = self.client.get_paginator('list_objects_v2')
            
            page_count = 0
            for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=jobs_prefix):
                page_count += 1
                if 'Contents' not in page:
                    logger.info(f"Page {page_count}: No objects found")
                    continue
                
                logger.info(f"Page {page_count}: Found {len(page['Contents'])} objects")
                    
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    
                    # Only process .json files
                    if not s3_key.endswith('.json'):
                        logger.debug(f"Skipping non-JSON file: {s3_key}")
                        continue
                    
                    try:
                        # Get and parse JSON file
                        logger.debug(f"Loading job file: {s3_key}")
                        response = self.client.get_object(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key=s3_key
                        )
                        content = response['Body'].read().decode('utf-8')
                        job_data = json.loads(content)
                        
                        # Each file should contain 1 job object (dict)
                        if isinstance(job_data, dict):
                            jobs_data.append(job_data)
                            logger.debug(f"Loaded job from {s3_key}: {job_data.get('title', 'N/A')}")
                        elif isinstance(job_data, list):
                            # If file contains array, add all items
                            jobs_data.extend(job_data)
                            logger.debug(f"Loaded {len(job_data)} jobs from array in {s3_key}")
                        else:
                            logger.warning(f"Invalid job data format in {s3_key}: expected dict or list, got {type(job_data)}")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON from {s3_key}: {e}")
                        continue
                    except ClientError as e:
                        error_code = e.response.get('Error', {}).get('Code', '')
                        logger.warning(f"Failed to read {s3_key} (Error: {error_code}): {e}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing {s3_key}: {e}", exc_info=True)
                        continue
            
            logger.info(f"Loaded {len(jobs_data)} jobs from S3: {jobs_prefix} (processed {page_count} pages)")
            return jobs_data
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            if error_code == 'NoSuchBucket':
                logger.error(f"Bucket does not exist: {settings.S3_BUCKET_NAME} (Error: {error_code})")
            elif error_code == 'AccessDenied':
                logger.error(f"Access denied to S3 bucket: {settings.S3_BUCKET_NAME}, prefix: {jobs_prefix} (Error: {error_code})")
            else:
                logger.error(f"S3 load jobs error (Code: {error_code}, Message: {error_message}): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading jobs: {e}", exc_info=True)
            return []


# Singleton instance - lazy initialization to avoid init timeout
_s3_client_instance = None

def get_s3_client():
    """Get or create S3 client instance (lazy initialization)"""
    global _s3_client_instance
    if _s3_client_instance is None:
        _s3_client_instance = S3Client()
    return _s3_client_instance

# For backward compatibility - create a simple wrapper
class S3ClientWrapper:
    """Wrapper to maintain backward compatibility"""
    def __getattr__(self, name):
        return getattr(get_s3_client(), name)
    
    @property
    def client(self):
        """Expose client attribute directly"""
        return get_s3_client().client

s3_client = S3ClientWrapper()

