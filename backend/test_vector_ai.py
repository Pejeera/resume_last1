"""
Test script for Vector AI functionality
Tests both Mode A and Mode B with vector search and reranking
"""
import requests
import json
import os
import urllib3
from dotenv import load_dotenv
from pathlib import Path

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env from infra directory
env_path = Path(__file__).parent.parent / 'infra' / '.env'
if env_path.exists():
    load_dotenv(env_path)

# API Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com')
# Or use local Lambda URL if testing locally
# API_BASE_URL = 'http://localhost:9000/2015-03-31/functions/function/invocations'

print("=" * 80)
print("VECTOR AI TESTING SCRIPT")
print("=" * 80)

def test_health():
    """Test health endpoint"""
    print("\n[TEST 1] Health Check")
    print("-" * 80)
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=10, verify=False)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_list_jobs():
    """Test listing jobs"""
    print("\n[TEST 2] List Jobs")
    print("-" * 80)
    try:
        response = requests.get(f"{API_BASE_URL}/api/jobs", timeout=30, verify=False)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total jobs: {data.get('total', 0)}")
        jobs = data.get('jobs', [])
        if jobs:
            print(f"\nFirst 3 jobs:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"  {i}. {job.get('title', 'N/A')} (ID: {job.get('job_id', 'N/A')})")
        return jobs
    except Exception as e:
        print(f"Error: {e}")
        return []

def test_list_resumes():
    """Test listing resumes"""
    print("\n[TEST 3] List Resumes")
    print("-" * 80)
    try:
        response = requests.get(f"{API_BASE_URL}/api/resumes", timeout=30, verify=False)
        print(f"Status: {response.status_code}")
        data = response.json()
        resumes = data.get('resumes', [])
        print(f"Total resumes: {len(resumes)}")
        if resumes:
            print(f"\nFirst 3 resumes:")
            for i, resume in enumerate(resumes[:3], 1):
                print(f"  {i}. {resume.get('filename', 'N/A')}")
        return resumes
    except Exception as e:
        print(f"Error: {e}")
        return []

def test_sync_jobs():
    """Test syncing jobs with embeddings"""
    print("\n[TEST 4] Sync Jobs from S3 to OpenSearch (with embeddings)")
    print("-" * 80)
    try:
        response = requests.post(f"{API_BASE_URL}/api/jobs/sync_from_s3", timeout=300, verify=False)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Synced: {data.get('synced', 0)}")
        print(f"Skipped: {data.get('skipped', 0)}")
        print(f"Total: {data.get('total', 0)}")
        return data.get('synced', 0) > 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_sync_resumes():
    """Test syncing resumes with embeddings"""
    print("\n[TEST 5] Sync Resumes from S3 to OpenSearch (with embeddings)")
    print("-" * 80)
    try:
        response = requests.post(f"{API_BASE_URL}/api/resumes/sync_from_s3", timeout=300, verify=False)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Synced: {data.get('synced', 0)}")
        print(f"Skipped: {data.get('skipped', 0)}")
        print(f"Total: {data.get('total', 0)}")
        return data.get('synced', 0) > 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_mode_a(resume_key):
    """Test Mode A: Search Jobs by Resume (Vector AI)"""
    print("\n[TEST 6] Mode A: Search Jobs by Resume (Vector AI)")
    print("-" * 80)
    print(f"Resume: {resume_key}")
    try:
        payload = {
            "resume_key": resume_key
        }
        response = requests.post(
            f"{API_BASE_URL}/api/jobs/search_by_resume",
            json=payload,
            timeout=60,
            verify=False
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200:
            results = data.get('results', [])
            print(f"\nFound {len(results)} matching jobs:")
            for i, result in enumerate(results, 1):
                print(f"\n  [{i}] {result.get('job_title', 'N/A')}")
                print(f"      Job ID: {result.get('job_id', 'N/A')}")
                print(f"      Match Score: {result.get('match_score', 0):.2f}%")
                print(f"      Rerank Score: {result.get('rerank_score', 0):.2f}")
                print(f"      Reasons: {result.get('reasons', 'N/A')[:100]}...")
                if result.get('highlighted_skills'):
                    print(f"      Skills: {', '.join(result.get('highlighted_skills', [])[:5])}")
        else:
            print(f"Error: {data.get('error', 'Unknown error')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mode_b(job_id, resume_keys):
    """Test Mode B: Search Resumes by Job (Vector AI)"""
    print("\n[TEST 7] Mode B: Search Resumes by Job (Vector AI)")
    print("-" * 80)
    print(f"Job ID: {job_id}")
    print(f"Resumes to search: {len(resume_keys)}")
    try:
        payload = {
            "resume_keys": resume_keys
        }
        response = requests.post(
            f"{API_BASE_URL}/api/resumes/search_by_job?job_id={job_id}",
            json=payload,
            timeout=60,
            verify=False
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200:
            results = data.get('results', [])
            print(f"\nFound {len(results)} matching resumes:")
            for i, result in enumerate(results, 1):
                print(f"\n  [{i}] {result.get('resume_name', 'N/A')}")
                print(f"      Resume ID: {result.get('resume_id', 'N/A')}")
                print(f"      Match Score: {result.get('match_score', 0):.2f}%")
                print(f"      Rerank Score: {result.get('rerank_score', 0):.2f}")
                print(f"      Reasons: {result.get('reasons', 'N/A')[:100]}...")
                if result.get('highlighted_skills'):
                    print(f"      Skills: {', '.join(result.get('highlighted_skills', [])[:5])}")
        else:
            print(f"Error: {data.get('error', 'Unknown error')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\nStarting Vector AI Tests...")
    print(f"API Base URL: {API_BASE_URL}")
    
    # Test 1: Health check
    if not test_health():
        print("\n[ERROR] Health check failed. Please check API URL.")
        return
    
    # Test 2: List jobs
    jobs = test_list_jobs()
    
    # Test 3: List resumes
    resumes = test_list_resumes()
    
    # Test 4: Sync jobs (optional - uncomment if needed)
    # print("\nDo you want to sync jobs? (This may take a while)")
    # sync_jobs = input("Sync jobs? (y/n): ").lower() == 'y'
    # if sync_jobs:
    #     test_sync_jobs()
    
    # Test 5: Sync resumes (optional - uncomment if needed)
    # print("\nDo you want to sync resumes? (This may take a while)")
    # sync_resumes = input("Sync resumes? (y/n): ").lower() == 'y'
    # if sync_resumes:
    #     test_sync_resumes()
    
    # Test 6: Mode A - Search Jobs by Resume
    if resumes:
        print("\n" + "=" * 80)
        print("TESTING MODE A: Resume -> Jobs (Vector AI)")
        print("=" * 80)
        # Use first resume for testing
        test_resume = resumes[0].get('key') or resumes[0].get('filename')
        if test_resume:
            test_mode_a(test_resume)
    
    # Test 7: Mode B - Search Resumes by Job
    if jobs:
        print("\n" + "=" * 80)
        print("TESTING MODE B: Job -> Resumes (Vector AI)")
        print("=" * 80)
        # Use first job for testing
        test_job_id = jobs[0].get('job_id')
        if test_job_id and resumes:
            # Use first 3 resumes for testing
            test_resume_keys = [r.get('key') or r.get('filename') for r in resumes[:3]]
            test_mode_b(test_job_id, test_resume_keys)
    
    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

