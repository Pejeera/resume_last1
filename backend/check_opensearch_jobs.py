"""Check OpenSearch jobs index"""
import boto3
import requests
from requests_aws4auth import AWS4Auth
import json
import os
from dotenv import load_dotenv
from pathlib import Path
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env from infra directory
env_path = Path(__file__).parent.parent / 'infra' / '.env'
if env_path.exists():
    load_dotenv(env_path)

# OpenSearch config
OPENSEARCH_HOST = os.getenv('OPENSEARCH_ENDPOINT', '').replace('https://', '').replace('http://', '')
OPENSEARCH_REGION = os.getenv('OPENSEARCH_REGION', 'ap-southeast-2')
OPENSEARCH_USERNAME = os.getenv('OPENSEARCH_USERNAME', '')
OPENSEARCH_PASSWORD = os.getenv('OPENSEARCH_PASSWORD', '')
INDEX_NAME = "jobs_index"

print(f"Checking OpenSearch: {OPENSEARCH_HOST}")
print(f"Index: {INDEX_NAME}")
print("=" * 70)

# Setup AWS auth
session = boto3.Session()
credentials = session.get_credentials()

if OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD:
    awsauth = AWS4Auth(
        OPENSEARCH_USERNAME,
        OPENSEARCH_PASSWORD,
        OPENSEARCH_REGION,
        'es'
    )
else:
    if credentials:
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            OPENSEARCH_REGION,
            'es',
            session_token=credentials.token
        )
    else:
        print("Error: No OpenSearch credentials found")
        exit(1)

# Search all documents
url = f"https://{OPENSEARCH_HOST}/{INDEX_NAME}/_search"
query = {
    "size": 1000,
    "query": {"match_all": {}},
    "_source": True
}

try:
    print("Fetching jobs from OpenSearch...")
    res = requests.get(
        url,
        auth=awsauth,
        headers={"Content-Type": "application/json"},
        json=query,
        timeout=30,
        verify=False  # Disable SSL verification for local testing
    )

    if res.status_code != 200:
        print(f"Error: {res.status_code}")
        print(f"Response: {res.text}")
        exit(1)

    data = res.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {})
    
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    print(f"\nFound {len(hits)} jobs in OpenSearch (Total: {total_count})\n")

    if len(hits) == 0:
        print("No jobs found in OpenSearch index")
        print("\nThis means jobs have not been indexed yet.")
        print("You may need to:")
        print("  1. Call /api/jobs/sync_from_s3 endpoint to sync jobs from S3 to OpenSearch")
        print("  2. Or create jobs using /api/jobs/create endpoint")
    else:
        for i, hit in enumerate(hits, 1):
            source = hit.get("_source", {})
            doc_id = hit.get("_id", "N/A")
            
            print(f"{i}. Document ID: {doc_id}")
            print(f"   Title: {source.get('title', 'N/A')}")
            print(f"   ID: {source.get('id', source.get('_id', 'N/A'))}")
            
            # Check if has embeddings
            if 'embeddings' in source:
                emb = source.get('embeddings', [])
                if isinstance(emb, list) and len(emb) > 0:
                    print(f"   Embeddings: YES (dimension: {len(emb)})")
                else:
                    print(f"   Embeddings: NO or empty")
            else:
                print(f"   Embeddings: NO")
            
            # Show description excerpt
            if 'description' in source:
                desc = source.get('description', '')[:100]
                print(f"   Description: {desc}...")
            
            # Show metadata
            if 'metadata' in source and source.get('metadata'):
                meta = source.get('metadata', {})
                if 'skills' in meta:
                    print(f"   Skills: {', '.join(meta.get('skills', []))}")
            
            print()

    print(f"\nSummary:")
    print(f"  Total documents: {total_count}")
    print(f"  Documents with embeddings: {sum(1 for h in hits if h.get('_source', {}).get('embeddings'))}")
    print(f"  Documents without embeddings: {sum(1 for h in hits if not h.get('_source', {}).get('embeddings'))}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

