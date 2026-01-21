"""
Script to delete all resumes and jobs from S3 and OpenSearch
⚠️ WARNING: This will permanently delete all data!
"""
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from app.core.config import settings
from app.core.logging import get_logger
import sys
import argparse

logger = get_logger(__name__)

def delete_from_s3():
    """Delete all resumes and jobs from S3"""
    try:
        s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
        )
        
        bucket_name = settings.S3_BUCKET_NAME
        
        print("=" * 80)
        print("DELETING FROM S3")
        print("=" * 80)
        
        # Delete resumes
        resumes_prefix = f"{settings.S3_PREFIX}"
        resumes_deleted = 0
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name, Prefix=resumes_prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Skip directories
                        if not obj['Key'].endswith('/'):
                            s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                            resumes_deleted += 1
                            print(f"  Deleted: {obj['Key']}")
        except Exception as e:
            print(f"  [WARNING] Error deleting resumes: {e}")
        
        # Delete jobs
        jobs_prefix = f"{settings.S3_PREFIX}jobs/"
        jobs_deleted = 0
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name, Prefix=jobs_prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Skip directories
                        if not obj['Key'].endswith('/'):
                            s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                            jobs_deleted += 1
                            print(f"  Deleted: {obj['Key']}")
        except Exception as e:
            print(f"  [WARNING] Error deleting jobs: {e}")
        
        print(f"\nS3 Summary:")
        print(f"  Resumes deleted: {resumes_deleted}")
        print(f"  Jobs deleted: {jobs_deleted}")
        
        return resumes_deleted, jobs_deleted
        
    except Exception as e:
        print(f"[ERROR] Failed to delete from S3: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def delete_from_opensearch():
    """Delete all resumes and jobs from OpenSearch"""
    try:
        # Parse endpoint
        endpoint = settings.OPENSEARCH_ENDPOINT
        host = endpoint.replace('https://', '').replace('http://', '')
        if ':' in host:
            host, _ = host.rsplit(':', 1)
        
        # Extract region
        opensearch_region = settings.AWS_REGION
        if '.es.amazonaws.com' in host or '.aoss.amazonaws.com' in host:
            parts = host.split('.')
            for part in parts:
                if part.startswith('ap-') or part.startswith('us-') or part.startswith('eu-'):
                    opensearch_region = part
                    break
        
        # Get AWS credentials
        credentials = boto3.Session().get_credentials()
        if not credentials:
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                awsauth = AWS4Auth(
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY,
                    opensearch_region,
                    'es'
                )
            else:
                print("[ERROR] No AWS credentials found!")
                return 0, 0
        else:
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                opensearch_region,
                'es',
                session_token=credentials.token
            )
        
        opensearch_client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=False,  # For local testing
            ssl_show_warn=False,
            connection_class=RequestsHttpConnection
        )
        
        print("\n" + "=" * 80)
        print("DELETING FROM OPENSEARCH")
        print("=" * 80)
        
        # Delete all documents from resumes_index
        resumes_deleted = 0
        try:
            # First, get count
            count_response = opensearch_client.count(index="resumes_index")
            count = count_response.get('count', 0)
            
            if count > 0:
                # Delete by query (delete all)
                delete_response = opensearch_client.delete_by_query(
                    index="resumes_index",
                    body={"query": {"match_all": {}}}
                )
                resumes_deleted = delete_response.get('deleted', count)
                print(f"  Deleted {resumes_deleted} documents from 'resumes_index'")
            else:
                print(f"  No documents in 'resumes_index'")
        except Exception as e:
            print(f"  [WARNING] Error deleting resumes: {e}")
            # Try alternative: delete index and recreate
            try:
                if opensearch_client.indices.exists(index="resumes_index"):
                    opensearch_client.indices.delete(index="resumes_index")
                    print(f"  Deleted entire 'resumes_index'")
                    resumes_deleted = "index_deleted"
            except Exception as e2:
                print(f"  [ERROR] Could not delete index: {e2}")
        
        # Delete all documents from jobs_index
        jobs_deleted = 0
        try:
            # First, get count
            count_response = opensearch_client.count(index="jobs_index")
            count = count_response.get('count', 0)
            
            if count > 0:
                # Delete by query (delete all)
                delete_response = opensearch_client.delete_by_query(
                    index="jobs_index",
                    body={"query": {"match_all": {}}}
                )
                jobs_deleted = delete_response.get('deleted', count)
                print(f"  Deleted {jobs_deleted} documents from 'jobs_index'")
            else:
                print(f"  No documents in 'jobs_index'")
        except Exception as e:
            print(f"  [WARNING] Error deleting jobs: {e}")
            # Try alternative: delete index and recreate
            try:
                if opensearch_client.indices.exists(index="jobs_index"):
                    opensearch_client.indices.delete(index="jobs_index")
                    print(f"  Deleted entire 'jobs_index'")
                    jobs_deleted = "index_deleted"
            except Exception as e2:
                print(f"  [ERROR] Could not delete index: {e2}")
        
        # Also delete old 'jobs' index if it exists
        old_jobs_deleted = 0
        try:
            if opensearch_client.indices.exists(index="jobs"):
                count_response = opensearch_client.count(index="jobs")
                count = count_response.get('count', 0)
                
                if count > 0:
                    delete_response = opensearch_client.delete_by_query(
                        index="jobs",
                        body={"query": {"match_all": {}}}
                    )
                    old_jobs_deleted = delete_response.get('deleted', count)
                    print(f"  Deleted {old_jobs_deleted} documents from old 'jobs' index")
                else:
                    print(f"  No documents in old 'jobs' index")
                
                # Optionally delete the entire old index
                opensearch_client.indices.delete(index="jobs")
                print(f"  Deleted entire old 'jobs' index")
        except Exception as e:
            print(f"  [INFO] Old 'jobs' index not found or already deleted: {e}")
        
        print(f"\nOpenSearch Summary:")
        print(f"  Resumes deleted: {resumes_deleted}")
        print(f"  Jobs deleted: {jobs_deleted}")
        if old_jobs_deleted > 0:
            print(f"  Old jobs index deleted: {old_jobs_deleted} documents")
        
        return resumes_deleted, jobs_deleted
        
    except Exception as e:
        print(f"[ERROR] Failed to delete from OpenSearch: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def main():
    parser = argparse.ArgumentParser(description='Delete all resumes and jobs from S3 and OpenSearch')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation and delete immediately')
    args = parser.parse_args()
    
    print("=" * 80)
    print("WARNING: This will DELETE ALL RESUMES AND JOBS!")
    print("=" * 80)
    print("This will delete:")
    print("  - All resume files from S3")
    print("  - All job files from S3")
    print("  - All documents from OpenSearch 'resumes_index'")
    print("  - All documents from OpenSearch 'jobs_index'")
    print("  - Old 'jobs' index (if exists)")
    print("=" * 80)
    
    # Ask for confirmation unless --yes flag is used
    if not args.yes:
        try:
            response = input("\nType 'DELETE ALL' to confirm: ")
            if response != "DELETE ALL":
                print("\n[CANCELLED] Cancelled. No data was deleted.")
                return
        except EOFError:
            print("\n[ERROR] Cannot read input. Use --yes flag to skip confirmation.")
            return
    
    print("\n[STARTING] Starting deletion process...\n")
    
    # Delete from S3
    s3_resumes, s3_jobs = delete_from_s3()
    
    # Delete from OpenSearch
    os_resumes, os_jobs = delete_from_opensearch()
    
    # Final summary
    print("\n" + "=" * 80)
    print("DELETION COMPLETE")
    print("=" * 80)
    print("S3:")
    print(f"  Resumes deleted: {s3_resumes}")
    print(f"  Jobs deleted: {s3_jobs}")
    print("\nOpenSearch:")
    print(f"  Resumes deleted: {os_resumes}")
    print(f"  Jobs deleted: {os_jobs}")
    print("=" * 80)

if __name__ == "__main__":
    main()
