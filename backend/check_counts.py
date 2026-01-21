"""
Script to check counts of resumes and jobs in S3 and OpenSearch
"""
import boto3
from opensearchpy import OpenSearch
from app.core.config import settings
from app.core.logging import get_logger
import sys

logger = get_logger(__name__)

def check_s3_counts():
    """Count files in S3 bucket"""
    try:
        s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        bucket_name = settings.S3_BUCKET_NAME
        
        # Count resumes
        resumes_prefix = f"{settings.S3_PREFIX}"
        resumes_count = 0
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name, Prefix=resumes_prefix):
                if 'Contents' in page:
                    # Filter out directories and only count actual files
                    resumes_count += len([obj for obj in page['Contents'] if not obj['Key'].endswith('/')])
        except Exception as e:
            logger.warning(f"Error counting resumes in S3: {e}")
        
        # Count jobs
        jobs_prefix = f"{settings.S3_PREFIX}jobs/"
        jobs_count = 0
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name, Prefix=jobs_prefix):
                if 'Contents' in page:
                    jobs_count += len([obj for obj in page['Contents'] if not obj['Key'].endswith('/')])
        except Exception as e:
            logger.warning(f"Error counting jobs in S3: {e}")
        
        return resumes_count, jobs_count
    except Exception as e:
        logger.error(f"Error connecting to S3: {e}")
        return None, None

def check_opensearch_counts():
    """Count documents in OpenSearch indices"""
    try:
        # Parse endpoint
        endpoint = settings.OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '')
        
        opensearch_client = OpenSearch(
            hosts=[{'host': endpoint.split(':')[0], 'port': int(endpoint.split(':')[1]) if ':' in endpoint else 443}],
            http_auth=(settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD),
            use_ssl=settings.OPENSEARCH_USE_SSL,
            verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
            ssl_show_warn=False
        )
        
        # Count resumes
        resumes_count = 0
        try:
            response = opensearch_client.count(index="resumes_index")
            resumes_count = response.get('count', 0)
        except Exception as e:
            logger.warning(f"Error counting resumes in OpenSearch: {e}")
        
        # Count jobs
        jobs_count = 0
        try:
            response = opensearch_client.count(index="jobs_index")
            jobs_count = response.get('count', 0)
        except Exception as e:
            logger.warning(f"Error counting jobs in OpenSearch: {e}")
        
        return resumes_count, jobs_count
    except Exception as e:
        logger.error(f"Error connecting to OpenSearch: {e}")
        return None, None

def main():
    print("=" * 60)
    print("Checking counts in S3 and OpenSearch")
    print("=" * 60)
    print(f"S3 Bucket: {settings.S3_BUCKET_NAME}")
    print(f"OpenSearch Endpoint: {settings.OPENSEARCH_ENDPOINT}")
    print()
    
    # Check S3
    print("[S3] Checking S3...")
    s3_resumes, s3_jobs = check_s3_counts()
    if s3_resumes is not None and s3_jobs is not None:
        print(f"  [OK] S3 Resumes: {s3_resumes}")
        print(f"  [OK] S3 Jobs: {s3_jobs}")
    else:
        print("  [ERROR] Failed to count S3 files")
    print()
    
    # Check OpenSearch
    print("[OpenSearch] Checking OpenSearch...")
    os_resumes, os_jobs = check_opensearch_counts()
    if os_resumes is not None and os_jobs is not None:
        print(f"  [OK] OpenSearch Resumes: {os_resumes}")
        print(f"  [OK] OpenSearch Jobs: {os_jobs}")
    else:
        print("  [ERROR] Failed to count OpenSearch documents")
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Resumes - S3: {s3_resumes if s3_resumes is not None else 'N/A'}, OpenSearch: {os_resumes if os_resumes is not None else 'N/A'}")
    print(f"Jobs - S3: {s3_jobs if s3_jobs is not None else 'N/A'}, OpenSearch: {os_jobs if os_jobs is not None else 'N/A'}")
    print("=" * 60)

if __name__ == "__main__":
    main()
