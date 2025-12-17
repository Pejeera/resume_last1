"""
Upload jobs_data.json to S3 bucket
"""
import json
import boto3
import os
from botocore.exceptions import ClientError
from pathlib import Path

# Load environment variables from infra/.env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def upload_jobs_to_s3():
    """Upload jobs_data.json to S3 bucket"""
    # Load from local file
    local_file = Path(__file__).parent / 'jobs_data.json'
    if not local_file.exists():
        print(f"[ERROR] File not found: {local_file}")
        return False
    
    try:
        with open(local_file, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)
        print(f"[OK] Loaded {len(jobs_data)} jobs from {local_file}")
    except Exception as e:
        print(f"[ERROR] Failed to load jobs_data.json: {e}")
        return False
    
    # Get S3 config from env
    bucket_name = os.getenv('S3_BUCKET_NAME')
    s3_prefix = os.getenv('S3_PREFIX', 'resumes/')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    if not bucket_name:
        print("[ERROR] S3_BUCKET_NAME not found in environment")
        return False
    
    if not aws_access_key or not aws_secret_key:
        print("[ERROR] AWS credentials not found in environment")
        return False
    
    # Upload to S3
    try:
        print(f"[INFO] Uploading to S3 bucket: {bucket_name}")
        print(f"       Region: {aws_region}")
        print(f"       Key: {s3_prefix}jobs_data.json")
        
        s3_client = boto3.client(
            's3',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        s3_key = f"{s3_prefix}jobs_data.json"
        data_json = json.dumps(jobs_data, ensure_ascii=False, indent=2).encode('utf-8')
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=data_json,
            ContentType='application/json',
            Metadata={
                "total_jobs": str(len(jobs_data))
            }
        )
        
        s3_url = f"s3://{bucket_name}/{s3_key}"
        print(f"[OK] Successfully uploaded {len(jobs_data)} jobs to S3: {s3_url}")
        return True
    except ClientError as e:
        print(f"[ERROR] Failed to upload to S3: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    upload_jobs_to_s3()

