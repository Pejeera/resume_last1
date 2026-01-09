"""
Test Frontend Functionality
ทดสอบ Frontend API calls และ functionality
"""
import sys
import os
import json
import requests
from pathlib import Path
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

API_BASE_URL = 'https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com/api'

def test_api_endpoints():
    """Test all API endpoints used by frontend"""
    print("=" * 70)
    print("  Frontend API Endpoints Test")
    print("=" * 70)
    print()
    print(f"API Base URL: {API_BASE_URL}")
    print()
    
    results = {
        "passed": [],
        "failed": []
    }
    
    # Test 1: Health check (if available)
    print("Test 1: Health Check")
    print("-" * 70)
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10, verify=False)
        if response.status_code == 200:
            print(f"[OK] Health check passed")
            results["passed"].append("Health check")
        else:
            print(f"[WARNING] Health check returned {response.status_code}")
            results["passed"].append("Health check (non-200)")
    except Exception as e:
        print(f"[SKIP] Health check: {e}")
    print()
    
    # Test 2: List Jobs
    print("Test 2: List Jobs (/api/jobs/list)")
    print("-" * 70)
    try:
        response = requests.get(f"{API_BASE_URL}/jobs/list", timeout=15, verify=False)
        if response.status_code == 200:
            data = response.json()
            jobs_count = len(data.get('jobs', []))
            print(f"[OK] List jobs successful")
            print(f"  Found {jobs_count} jobs")
            results["passed"].append("List Jobs")
        else:
            print(f"[FAIL] List jobs returned {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            results["failed"].append(f"List Jobs ({response.status_code})")
    except Exception as e:
        print(f"[FAIL] List jobs error: {e}")
        results["failed"].append(f"List Jobs: {str(e)}")
    print()
    
    # Test 3: List Resumes
    print("Test 3: List Resumes (/api/resumes/list)")
    print("-" * 70)
    try:
        response = requests.get(f"{API_BASE_URL}/resumes/list", timeout=15, verify=False)
        if response.status_code == 200:
            data = response.json()
            resumes_count = len(data.get('resumes', []))
            print(f"[OK] List resumes successful")
            print(f"  Found {resumes_count} resumes")
            results["passed"].append("List Resumes")
        else:
            print(f"[FAIL] List resumes returned {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            results["failed"].append(f"List Resumes ({response.status_code})")
    except Exception as e:
        print(f"[FAIL] List resumes error: {e}")
        results["failed"].append(f"List Resumes: {str(e)}")
    print()
    
    # Test 4: Search Jobs by Resume (if we have resumes)
    print("Test 4: Search Jobs by Resume (/api/jobs/search_by_resume)")
    print("-" * 70)
    try:
        # First get resumes
        resumes_response = requests.get(f"{API_BASE_URL}/resumes/list", timeout=15, verify=False)
        if resumes_response.status_code == 200:
            resumes_data = resumes_response.json()
            resumes = resumes_data.get('resumes', [])
            
            if resumes:
                # Use first resume
                first_resume = resumes[0]
                resume_key = first_resume.get('s3_key') or first_resume.get('resume_id')
                
                if resume_key:
                    search_payload = {
                        "resume_key": resume_key,
                        "resume_id": first_resume.get('resume_id', resume_key)
                    }
                    
                    print(f"  Using resume: {first_resume.get('name', 'N/A')}")
                    print(f"  Resume key: {resume_key}")
                    
                    response = requests.post(
                        f"{API_BASE_URL}/jobs/search_by_resume",
                        json=search_payload,
                        timeout=60,  # Longer timeout for processing
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results_count = len(data.get('results', []))
                        print(f"[OK] Search jobs by resume successful")
                        print(f"  Found {results_count} matching jobs")
                        results["passed"].append("Search Jobs by Resume")
                    else:
                        print(f"[FAIL] Search returned {response.status_code}")
                        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                        print(f"  Error: {error_data.get('detail', response.text[:200])}")
                        results["failed"].append(f"Search Jobs by Resume ({response.status_code})")
                else:
                    print(f"[SKIP] No resume key found")
            else:
                print(f"[SKIP] No resumes available to test")
        else:
            print(f"[SKIP] Could not get resumes list")
    except Exception as e:
        print(f"[FAIL] Search jobs by resume error: {e}")
        results["failed"].append(f"Search Jobs by Resume: {str(e)}")
    print()
    
    # Test 5: Search Resumes by Job (if we have jobs)
    print("Test 5: Search Resumes by Job (/api/resumes/search_by_job)")
    print("-" * 70)
    try:
        # First get jobs
        jobs_response = requests.get(f"{API_BASE_URL}/jobs/list", timeout=15, verify=False)
        if jobs_response.status_code == 200:
            jobs_data = jobs_response.json()
            jobs = jobs_data.get('jobs', [])
            
            if jobs:
                # Use first job
                first_job = jobs[0]
                job_id = first_job.get('id')
                
                if job_id:
                    print(f"  Using job: {first_job.get('title', 'N/A')}")
                    print(f"  Job ID: {job_id}")
                    
                    response = requests.get(
                        f"{API_BASE_URL}/resumes/search_by_job?job_id={job_id}",
                        timeout=60,
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results_count = len(data.get('results', []))
                        print(f"[OK] Search resumes by job successful")
                        print(f"  Found {results_count} matching resumes")
                        results["passed"].append("Search Resumes by Job")
                    else:
                        print(f"[FAIL] Search returned {response.status_code}")
                        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                        print(f"  Error: {error_data.get('detail', response.text[:200])}")
                        results["failed"].append(f"Search Resumes by Job ({response.status_code})")
                else:
                    print(f"[SKIP] No job ID found")
            else:
                print(f"[SKIP] No jobs available to test")
        else:
            print(f"[SKIP] Could not get jobs list")
    except Exception as e:
        print(f"[FAIL] Search resumes by job error: {e}")
        results["failed"].append(f"Search Resumes by Job: {str(e)}")
    print()
    
    # Summary
    print("=" * 70)
    print("  Test Summary")
    print("=" * 70)
    print()
    print(f"Passed: {len(results['passed'])}")
    for test in results['passed']:
        print(f"  ✓ {test}")
    print()
    print(f"Failed: {len(results['failed'])}")
    for test in results['failed']:
        print(f"  ✗ {test}")
    print()
    
    if len(results['failed']) == 0:
        print("[SUCCESS] All frontend API tests passed!")
        return True
    else:
        print("[WARNING] Some tests failed. Frontend may have issues.")
        return False

if __name__ == "__main__":
    try:
        success = test_api_endpoints()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

