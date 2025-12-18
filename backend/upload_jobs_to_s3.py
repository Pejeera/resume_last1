"""
Script to upload jobs data to S3
"""
import boto3
import json
import os
from botocore.exceptions import ClientError

# S3 configuration
BUCKET_NAME = "resume-matching-533267343789"
S3_KEY = "resumes/jobs_data.json"
REGION = "us-east-1"

def upload_jobs_data():
    """Upload jobs data to S3"""
    try:
        # Read jobs data
        with open("sample_jobs_data.json", "r", encoding="utf-8") as f:
            jobs_data = json.load(f)
        
        print(f"Loaded {len(jobs_data)} jobs from sample_jobs_data.json")
        
        # Create S3 client
        s3_client = boto3.client('s3', region_name=REGION)
        
        # Convert to JSON string
        data_json = json.dumps(jobs_data, ensure_ascii=False, indent=2).encode('utf-8')
        
        # Upload to S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=S3_KEY,
            Body=data_json,
            ContentType='application/json'
        )
        
        print(f"✅ Successfully uploaded {len(jobs_data)} jobs to s3://{BUCKET_NAME}/{S3_KEY}")
        return True
        
    except FileNotFoundError:
        print("❌ Error: sample_jobs_data.json not found")
        return False
    except ClientError as e:
        print(f"❌ S3 upload error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    upload_jobs_data()

