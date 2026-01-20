"""
Test script to delete job via API
Tests both S3 and OpenSearch deletion
"""
import sys
import os
import requests
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def test_delete_by_job_id(job_id: str, api_base_url: str = None):
    """Test deleting job by job_id"""
    if not api_base_url:
        # Try to get from settings or use default
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    url = f"{api_base_url}/api/jobs/{job_id}"
    
    print(f"\n{'='*60}")
    print(f"Testing DELETE job by ID")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"Job ID: {job_id}")
    
    try:
        response = requests.delete(url)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("\n[SUCCESS] Job deleted successfully!")
            result = response.json()
            print(f"  - Deleted from OpenSearch: {result.get('deleted_from_opensearch', False)}")
            print(f"  - Deleted from S3: {result.get('deleted_from_s3', False)}")
            return True
        else:
            print(f"\n[ERROR] Failed to delete job: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_delete_by_title(title: str, api_base_url: str = None):
    """Test deleting job by title"""
    if not api_base_url:
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    import urllib.parse
    encoded_title = urllib.parse.quote(title)
    url = f"{api_base_url}/api/jobs/by_title/{encoded_title}"
    
    print(f"\n{'='*60}")
    print(f"Testing DELETE job by Title")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"Title: {title}")
    
    try:
        response = requests.delete(url)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("\n[SUCCESS] Job(s) deleted successfully!")
            result = response.json()
            deleted_jobs = result.get('deleted_jobs', [])
            print(f"  - Number of jobs deleted: {len(deleted_jobs)}")
            for job in deleted_jobs:
                print(f"    * {job.get('title')} (ID: {job.get('job_id')})")
            return True
        else:
            print(f"\n[ERROR] Failed to delete job: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_jobs(api_base_url: str = None):
    """List all jobs to see what's available"""
    if not api_base_url:
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    url = f"{api_base_url}/api/jobs/list"
    
    print(f"\n{'='*60}")
    print(f"Listing all jobs")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get('jobs', [])
            print(f"\nFound {len(jobs)} job(s):")
            print("-" * 60)
            for i, job in enumerate(jobs, 1):
                print(f"{i}. Title: {job.get('title', 'N/A')}")
                print(f"   ID: {job.get('id', job.get('job_id', 'N/A'))}")
                print(f"   Created: {job.get('created_at', 'N/A')}")
                print()
            return jobs
        else:
            print(f"\n[ERROR] Failed to list jobs: {response.status_code}")
            print(f"Response: {response.text}")
            return []
            
    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test job deletion API")
    parser.add_argument("--api-url", type=str, help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--job-id", type=str, help="Job ID to delete")
    parser.add_argument("--title", type=str, help="Job title to delete")
    parser.add_argument("--list", action="store_true", help="List all jobs first")
    
    args = parser.parse_args()
    
    api_url = args.api_url or os.getenv("API_BASE_URL", "http://localhost:8000")
    
    # List jobs first if requested
    if args.list or (not args.job_id and not args.title):
        jobs = list_jobs(api_url)
        if jobs and not args.job_id and not args.title:
            print("\n" + "="*60)
            print("To delete a job, use:")
            print(f"  python test_delete_job_api.py --job-id <job_id>")
            print(f"  python test_delete_job_api.py --title \"<title>\"")
            print("="*60)
    
    # Delete by job_id
    if args.job_id:
        test_delete_by_job_id(args.job_id, api_url)
    
    # Delete by title
    if args.title:
        test_delete_by_title(args.title, api_url)
