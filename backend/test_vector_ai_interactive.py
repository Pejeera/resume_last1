"""
Interactive test script for Vector AI functionality
Run this script to test Mode A and Mode B interactively
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

def print_header(text):
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)

def print_section(text):
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80)

def test_mode_a_interactive():
    """Interactive test for Mode A"""
    print_header("MODE A: Resume -> Jobs (Vector AI)")
    
    # List resumes
    print_section("Step 1: Listing available resumes...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/resumes", timeout=30)
        if response.status_code != 200:
            print(f"[ERROR] {response.status_code} - {response.text}")
            return
        
        data = response.json()
        resumes = data.get('resumes', [])
        
        if not resumes:
            print("[ERROR] No resumes found. Please upload resumes to S3 first.")
            return
        
        print(f"[SUCCESS] Found {len(resumes)} resumes:")
        for i, resume in enumerate(resumes[:10], 1):
            filename = resume.get('filename', resume.get('key', 'N/A'))
            print(f"  {i}. {filename}")
        
        # Let user select
        if len(resumes) > 1:
            print(f"\nSelect resume (1-{min(len(resumes), 10)}) or enter filename:")
            choice = input("Choice: ").strip()
            
            if choice.isdigit() and 1 <= int(choice) <= min(len(resumes), 10):
                selected_resume = resumes[int(choice) - 1]
            else:
                # Try to find by filename
                selected_resume = next((r for r in resumes if choice in r.get('filename', '')), resumes[0])
        else:
            selected_resume = resumes[0]
        
        resume_key = selected_resume.get('key') or selected_resume.get('filename')
        print(f"\n[INFO] Selected: {resume_key}")
        
    except Exception as e:
        print(f"[ERROR] Error listing resumes: {e}")
        return
    
    # Test Mode A
    print_section("Step 2: Searching jobs by resume (Vector AI)...")
    try:
        payload = {"resume_key": resume_key}
        print(f"Request: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/jobs/search_by_resume",
            json=payload,
            timeout=60,
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"\n[SUCCESS] Found {len(results)} matching jobs:\n")
            
            for i, result in enumerate(results, 1):
                print(f"  {'='*70}")
                print(f"  [{i}] {result.get('job_title', 'N/A')}")
                print(f"  {'='*70}")
                print(f"  Job ID: {result.get('job_id', 'N/A')}")
                print(f"  Match Score: {result.get('match_score', 0):.2f}%")
                print(f"  Rerank Score: {result.get('rerank_score', 0):.4f}")
                print(f"\n  Reasons:")
                print(f"    {result.get('reasons', 'N/A')}")
                
                if result.get('highlighted_skills'):
                    print(f"\n  Highlighted Skills:")
                    for skill in result.get('highlighted_skills', [])[:10]:
                        print(f"    • {skill}")
                
                if result.get('gaps'):
                    print(f"\n  Gaps:")
                    for gap in result.get('gaps', [])[:10]:
                        print(f"    • {gap}")
                
                if result.get('recommended_questions_for_interview'):
                    print(f"\n  Recommended Interview Questions:")
                    for q in result.get('recommended_questions_for_interview', [])[:5]:
                        print(f"    • {q}")
                
                print()
        else:
            error_data = response.json() if response.content else {}
            print(f"[ERROR] {error_data.get('error', response.text)}")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

def test_mode_b_interactive():
    """Interactive test for Mode B"""
    print_header("MODE B: Job -> Resumes (Vector AI)")
    
    # List jobs
    print_section("Step 1: Listing available jobs...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/jobs", timeout=30, verify=False)
        if response.status_code != 200:
            print(f"[ERROR] {response.status_code} - {response.text}")
            return
        
        data = response.json()
        jobs = data.get('jobs', [])
        
        if not jobs:
            print("[ERROR] No jobs found. Please sync jobs from S3 first.")
            return
        
        print(f"[SUCCESS] Found {len(jobs)} jobs:")
        for i, job in enumerate(jobs[:10], 1):
            title = job.get('title', 'N/A')
            job_id = job.get('job_id', 'N/A')
            print(f"  {i}. {title} (ID: {job_id})")
        
        # Let user select
        if len(jobs) > 1:
            print(f"\nSelect job (1-{min(len(jobs), 10)}) or enter job_id:")
            choice = input("Choice: ").strip()
            
            if choice.isdigit() and 1 <= int(choice) <= min(len(jobs), 10):
                selected_job = jobs[int(choice) - 1]
            else:
                # Try to find by job_id
                selected_job = next((j for j in jobs if choice in j.get('job_id', '')), jobs[0])
        else:
            selected_job = jobs[0]
        
        job_id = selected_job.get('job_id')
        print(f"\n[INFO] Selected: {selected_job.get('title', 'N/A')} (ID: {job_id})")
        
    except Exception as e:
        print(f"[ERROR] Error listing jobs: {e}")
        return
    
    # List resumes
    print_section("Step 2: Listing available resumes...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/resumes", timeout=30, verify=False)
        if response.status_code != 200:
            print(f"[ERROR] {response.status_code} - {response.text}")
            return
        
        data = response.json()
        resumes = data.get('resumes', [])
        
        if not resumes:
            print("[ERROR] No resumes found. Please upload resumes to S3 first.")
            return
        
        print(f"[SUCCESS] Found {len(resumes)} resumes:")
        for i, resume in enumerate(resumes[:10], 1):
            filename = resume.get('filename', resume.get('key', 'N/A'))
            print(f"  {i}. {filename}")
        
        # Let user select resumes
        print(f"\nSelect resumes to search (comma-separated, e.g., 1,2,3) or 'all' for all:")
        choice = input("Choice: ").strip().lower()
        
        if choice == 'all':
            selected_resumes = resumes
        else:
            indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip().isdigit()]
            selected_resumes = [resumes[i] for i in indices if 0 <= i < len(resumes)]
            if not selected_resumes:
                selected_resumes = resumes[:3]  # Default to first 3
        
        resume_keys = [r.get('key') or r.get('filename') for r in selected_resumes]
        print(f"\n[INFO] Selected {len(resume_keys)} resumes:")
        for key in resume_keys:
            print(f"    • {key}")
        
    except Exception as e:
        print(f"[ERROR] Error listing resumes: {e}")
        return
    
    # Test Mode B
    print_section("Step 3: Searching resumes by job (Vector AI)...")
    try:
        payload = {"resume_keys": resume_keys}
        print(f"Request: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/resumes/search_by_job?job_id={job_id}",
            json=payload,
            timeout=60,
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            print(f"\n[SUCCESS] Found {len(results)} matching resumes:\n")
            
            for i, result in enumerate(results, 1):
                print(f"  {'='*70}")
                print(f"  [{i}] {result.get('resume_name', 'N/A')}")
                print(f"  {'='*70}")
                print(f"  Resume ID: {result.get('resume_id', 'N/A')}")
                print(f"  Match Score: {result.get('match_score', 0):.2f}%")
                print(f"  Rerank Score: {result.get('rerank_score', 0):.4f}")
                print(f"\n  Reasons:")
                print(f"    {result.get('reasons', 'N/A')}")
                
                if result.get('highlighted_skills'):
                    print(f"\n  Highlighted Skills:")
                    for skill in result.get('highlighted_skills', [])[:10]:
                        print(f"    • {skill}")
                
                if result.get('gaps'):
                    print(f"\n  Gaps:")
                    for gap in result.get('gaps', [])[:10]:
                        print(f"    • {gap}")
                
                if result.get('recommended_questions_for_interview'):
                    print(f"\n  Recommended Interview Questions:")
                    for q in result.get('recommended_questions_for_interview', [])[:5]:
                        print(f"    • {q}")
                
                print()
        else:
            error_data = response.json() if response.content else {}
            print(f"[ERROR] {error_data.get('error', response.text)}")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main menu"""
    print_header("VECTOR AI INTERACTIVE TESTING")
    print(f"API Base URL: {API_BASE_URL}")
    
    while True:
        print("\n" + "=" * 80)
        print("SELECT TEST MODE:")
        print("=" * 80)
        print("1. Mode A: Resume -> Jobs (Vector AI)")
        print("2. Mode B: Job -> Resumes (Vector AI)")
        print("3. Exit")
        print("=" * 80)
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            test_mode_a_interactive()
        elif choice == '2':
            test_mode_b_interactive()
        elif choice == '3':
            print("\n[INFO] Goodbye!")
            break
        else:
            print("[ERROR] Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()

