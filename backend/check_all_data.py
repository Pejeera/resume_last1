"""Check all data: S3 files and OpenSearch vectors for both jobs and resumes"""
import boto3
import requests
from requests.auth import HTTPBasicAuth
import json
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from infra directory
env_path = Path(__file__).parent.parent / 'infra' / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Config
OPENSEARCH_HOST = os.getenv('OPENSEARCH_ENDPOINT', '').replace('https://', '').replace('http://', '')
OPENSEARCH_USERNAME = os.getenv('OPENSEARCH_USERNAME', 'Admin')
OPENSEARCH_PASSWORD = os.getenv('OPENSEARCH_PASSWORD', 'P@ssw0rd')
S3_BUCKET = 'resume-matching-533267343789'

print("=" * 70)
print("CHECKING ALL DATA: S3 FILES AND OPENSEARCH VECTORS")
print("=" * 70)

# Setup
s3 = boto3.client('s3', region_name='ap-southeast-2')
opensearch_auth = HTTPBasicAuth(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)

# ========== JOBS ==========
print("\nJOBS")
print("-" * 70)

# Jobs in S3
jobs_prefix = 'resumes/jobs/'
jobs_s3 = []
try:
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=jobs_prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                if obj['Key'].endswith('.json'):
                    jobs_s3.append(obj['Key'])
except Exception as e:
    print(f"Error listing jobs from S3: {e}")

print(f"S3 Files: {len(jobs_s3)} files")
for job_file in jobs_s3[:5]:
    print(f"  - {job_file}")

# Jobs in OpenSearch
jobs_os = []
try:
    url = f"https://{OPENSEARCH_HOST}/jobs_index/_search"
    query = {"size": 1000, "query": {"match_all": {}}}
    res = requests.get(url, auth=opensearch_auth, headers={"Content-Type": "application/json"}, json=query, timeout=30, verify=False)
    if res.status_code == 200:
        hits = res.json().get("hits", {}).get("hits", [])
        jobs_os = [hit.get("_id") for hit in hits]
        jobs_with_emb = sum(1 for hit in hits if hit.get("_source", {}).get("embeddings"))
        print(f"\nOpenSearch: {len(jobs_os)} documents")
        print(f"  With embeddings: {jobs_with_emb}")
        print(f"  Without embeddings: {len(jobs_os) - jobs_with_emb}")
        for job_id in jobs_os[:5]:
            print(f"  - {job_id}")
    else:
        print(f"\nOpenSearch: Error {res.status_code} - {res.text}")
except Exception as e:
    print(f"\nOpenSearch: Error - {e}")

# ========== RESUMES ==========
print("\nRESUMES")
print("-" * 70)

# Resumes in S3
resumes_prefix = 'resumes/Candidate/'
resumes_s3 = []
try:
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=resumes_prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                if not obj['Key'].endswith('/'):
                    resumes_s3.append(obj['Key'])
except Exception as e:
    print(f"Error listing resumes from S3: {e}")

print(f"S3 Files: {len(resumes_s3)} files")
for resume_file in resumes_s3[:5]:
    filename = resume_file.split('/')[-1]
    print(f"  - {filename}")

# Resumes in OpenSearch
resumes_os = []
try:
    url = f"https://{OPENSEARCH_HOST}/resumes_index/_search"
    query = {"size": 1000, "query": {"match_all": {}}}
    res = requests.get(url, auth=opensearch_auth, headers={"Content-Type": "application/json"}, json=query, timeout=30, verify=False)
    if res.status_code == 200:
        hits = res.json().get("hits", {}).get("hits", [])
        resumes_os = [hit.get("_id") for hit in hits]
        resumes_with_emb = sum(1 for hit in hits if hit.get("_source", {}).get("embeddings"))
        print(f"\nOpenSearch: {len(resumes_os)} documents")
        print(f"  With embeddings: {resumes_with_emb}")
        print(f"  Without embeddings: {len(resumes_os) - resumes_with_emb}")
        for resume_id in resumes_os[:5]:
            print(f"  - {resume_id}")
    elif res.status_code == 404:
        print(f"\nOpenSearch: Index 'resumes_index' does not exist yet")
    else:
        print(f"\nOpenSearch: Error {res.status_code} - {res.text}")
except Exception as e:
    print(f"\nOpenSearch: Error - {e}")

# ========== SUMMARY ==========
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\nJobs:")
print(f"  S3 (raw files):     {len(jobs_s3)} files")
print(f"  OpenSearch (vectors): {len(jobs_os)} documents ({sum(1 for h in requests.get(f'https://{OPENSEARCH_HOST}/jobs_index/_search', auth=opensearch_auth, headers={'Content-Type': 'application/json'}, json={'size': 1000, 'query': {'match_all': {}}}, timeout=30, verify=False).json().get('hits', {}).get('hits', [])) if requests.get(f'https://{OPENSEARCH_HOST}/jobs_index/_search', auth=opensearch_auth, headers={'Content-Type': 'application/json'}, json={'size': 1000, 'query': {'match_all': {}}}, timeout=30, verify=False).status_code == 200 else 0} with embeddings)")

print(f"\nResumes:")
print(f"  S3 (raw files):     {len(resumes_s3)} files")
print(f"  OpenSearch (vectors): {len(resumes_os)} documents")

print("\n" + "=" * 70)
if len(jobs_s3) > 0 and len(jobs_os) > 0 and len(resumes_s3) > 0:
    if len(resumes_os) > 0:
        print("COMPLETE: Both jobs and resumes have raw files AND vectors!")
    else:
        print("PARTIAL: Jobs complete, but resumes need to be synced to OpenSearch")
else:
    print("INCOMPLETE: Missing data")
print("=" * 70)

