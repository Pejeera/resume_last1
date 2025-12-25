"""
Detailed test for Mode B to debug why only 1 result is returned
"""
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

print("=" * 80)
print("DETAILED MODE B TEST")
print("=" * 80)

# 1. List jobs
print("\n[1] Listing jobs...")
response = requests.get(f"{API_BASE_URL}/api/jobs", timeout=30, verify=False)
jobs = response.json().get('jobs', [])
print(f"Found {len(jobs)} jobs")
job_id = jobs[0].get('job_id') if jobs else None
print(f"Using job: {jobs[0].get('title', 'N/A')} (ID: {job_id})")

# 2. List resumes
print("\n[2] Listing resumes...")
response = requests.get(f"{API_BASE_URL}/api/resumes", timeout=30, verify=False)
resumes = response.json().get('resumes', [])
print(f"Found {len(resumes)} resumes")
resume_keys = [r.get('key') or r.get('filename') for r in resumes[:3]]
print(f"Using {len(resume_keys)} resumes:")
for i, key in enumerate(resume_keys, 1):
    print(f"  {i}. {key}")

# 3. Test Mode B
print("\n[3] Testing Mode B: Search Resumes by Job...")
print(f"Job ID: {job_id}")
print(f"Resume keys: {resume_keys}")

payload = {
    "resume_keys": resume_keys
}

print(f"\nRequest payload: {json.dumps(payload, indent=2)}")

response = requests.post(
    f"{API_BASE_URL}/api/resumes/search_by_job?job_id={job_id}",
    json=payload,
    timeout=60,
    verify=False
)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Headers: {dict(response.headers)}")

if response.status_code == 200:
    data = response.json()
    print(f"\nResponse Data:")
    print(f"  Total: {data.get('total', 0)}")
    print(f"  Results count: {len(data.get('results', []))}")
    
    results = data.get('results', [])
    print(f"\n{'='*80}")
    print(f"RESULTS: {len(results)} resumes found")
    print(f"{'='*80}")
    
    for i, result in enumerate(results, 1):
        print(f"\n[{i}] {result.get('resume_name', 'N/A')}")
        print(f"    Rank: {result.get('rank', 'N/A')}")
        print(f"    Resume ID: {result.get('resume_id', 'N/A')}")
        print(f"    Match Score: {result.get('match_score', 0):.2f}%")
        print(f"    Rerank Score: {result.get('rerank_score', 0):.4f}")
        print(f"    Reasons: {result.get('reasons', 'N/A')[:100]}...")
        if result.get('highlighted_skills'):
            print(f"    Skills: {', '.join(result.get('highlighted_skills', [])[:5])}")
    
    if len(results) < 3:
        print(f"\n⚠️  WARNING: Only {len(results)} results returned, expected 3!")
        print(f"   This means the backend is not returning all candidates.")
    else:
        print(f"\n✅ SUCCESS: All {len(results)} results returned!")
else:
    error_data = response.json() if response.content else {}
    print(f"\n❌ ERROR: {error_data.get('error', response.text)}")

print("\n" + "=" * 80)

