"""
Simple OpenSearch checker using requests with AWS signing
This bypasses the OpenSearch client SSL issues
"""
import sys
import json
import requests
from requests_aws4auth import AWS4Auth
import boto3
import urllib3
from pathlib import Path
import os

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env file
env_path = Path(__file__).parent.parent / 'infra' / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value

# Get settings
OPENSEARCH_ENDPOINT = os.getenv('OPENSEARCH_ENDPOINT', '')
AWS_REGION = os.getenv('AWS_REGION', 'ap-southeast-1')

# Extract region from endpoint if available
if OPENSEARCH_ENDPOINT and '.es.amazonaws.com' in OPENSEARCH_ENDPOINT:
    # Extract region from hostname (e.g., ap-southeast-2)
    host = OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '').split('/')[0]
    parts = host.split('.')
    for part in parts:
        if part.startswith('ap-') or part.startswith('us-') or part.startswith('eu-') or part.startswith('sa-') or part.startswith('ca-') or part.startswith('cn-'):
            AWS_REGION = part
            break

if not OPENSEARCH_ENDPOINT:
    print("[ERROR] OPENSEARCH_ENDPOINT not found in .env file")
    sys.exit(1)

# Get AWS credentials
credentials = boto3.Session().get_credentials()
if not credentials:
    print("[ERROR] No AWS credentials found")
    sys.exit(1)

# Create AWS4Auth
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION,
    'es',
    session_token=credentials.token
)

# Extract host from endpoint
host = OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '').split('/')[0]
endpoint = f"https://{host}"

print("\n" + "="*60)
print("OpenSearch Index Checker (Simple)")
print("="*60)
print(f"\nConfiguration:")
print(f"  - Endpoint: {endpoint}")
print(f"  - Region: {AWS_REGION}")

# Get resume_id from command line
resume_id = sys.argv[1] if len(sys.argv) > 1 else "c3a74273-816f-4dd6-bd50-24e8d8c6d8f7"
index_name = "resumes_index"

print(f"  - Index: {index_name}")
print(f"  - Resume ID: {resume_id}")
print()

# 1. List indices
print("="*60)
print("1. ตรวจสอบ indices ที่มีอยู่")
print("="*60)
try:
    response = requests.get(
        f"{endpoint}/_cat/indices?v&format=json",
        auth=awsauth,
        verify=False,
        timeout=10
    )
    if response.status_code == 200:
        indices = response.json()
        print(f"\nพบ {len(indices)} indices:")
        for idx in indices:
            print(f"  - {idx['index']} (docs: {idx.get('docs.count', 'N/A')}, size: {idx.get('store.size', 'N/A')})")
        
        resume_indices = [idx['index'] for idx in indices if 'resume' in idx['index'].lower()]
        if resume_indices:
            print(f"\n[OK] พบ resume indices: {resume_indices}")
            index_name = resume_indices[0]
        else:
            print("\n[WARNING] ไม่พบ resume indices")
    else:
        print(f"[ERROR] Status {response.status_code}: {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

# 2. Check if resume exists
print("\n" + "="*60)
print(f"2. ตรวจสอบว่า resume_id อยู่ใน {index_name} หรือไม่")
print("="*60)
print(f"Resume ID: {resume_id}\n")

try:
    # Try with keyword field
    search_body = {
        "query": {
            "term": {
                "resume_id.keyword": resume_id
            }
        }
    }
    
    response = requests.post(
        f"{endpoint}/{index_name}/_search",
        json=search_body,
        auth=awsauth,
        verify=False,
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        total = result['hits']['total']['value'] if isinstance(result['hits']['total'], dict) else result['hits']['total']
        
        if total > 0:
            print(f"[OK] พบ resume (total: {total})")
            print("\nDocument:")
            print(json.dumps(result['hits']['hits'][0]['_source'], indent=2, ensure_ascii=False))
        else:
            print("[NO] ไม่พบ resume (total: 0)")
            print("\nลองใช้ match query แทน...")
            
            # Try with match
            search_body_match = {
                "query": {
                    "match": {
                        "resume_id": resume_id
                    }
                }
            }
            
            response_match = requests.post(
                f"{endpoint}/{index_name}/_search",
                json=search_body_match,
                auth=awsauth,
                verify=False,
                timeout=10
            )
            
            if response_match.status_code == 200:
                result_match = response_match.json()
                total_match = result_match['hits']['total']['value'] if isinstance(result_match['hits']['total'], dict) else result_match['hits']['total']
                
                if total_match > 0:
                    print(f"[OK] พบ resume ด้วย match query (total: {total_match})")
                    print("\nDocument:")
                    print(json.dumps(result_match['hits']['hits'][0]['_source'], indent=2, ensure_ascii=False))
                else:
                    print("[NO] ไม่พบ resume แม้ใช้ match query")
    else:
        print(f"[ERROR] Status {response.status_code}: {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

# 3. Check vector fields
print("\n" + "="*60)
print(f"3. ตรวจสอบว่า {index_name} มี vector fields หรือไม่")
print("="*60)
print()

try:
    search_body = {
        "_source": ["resume_id", "embedding", "embeddings", "vector", "resume_vector", "content"],
        "query": {
            "match_all": {}
        },
        "size": 1
    }
    
    response = requests.post(
        f"{endpoint}/{index_name}/_search",
        json=search_body,
        auth=awsauth,
        verify=False,
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        total = result['hits']['total']['value'] if isinstance(result['hits']['total'], dict) else result['hits']['total']
        
        if total > 0:
            doc = result['hits']['hits'][0]['_source']
            print("Fields ใน document:")
            for key in doc.keys():
                value = doc[key]
                if isinstance(value, list):
                    print(f"  - {key}: list[{len(value)}]")
                else:
                    print(f"  - {key}: {type(value).__name__}")
            
            vector_fields = ['embedding', 'embeddings', 'vector', 'resume_vector']
            found_vector_fields = [field for field in vector_fields if field in doc]
            
            if found_vector_fields:
                print(f"\n[OK] พบ vector fields: {found_vector_fields}")
                for field in found_vector_fields:
                    value = doc[field]
                    if isinstance(value, list):
                        print(f"  - {field}: list with {len(value)} dimensions")
            else:
                print(f"\n[NO] ไม่พบ vector fields ใน document")
                print(f"   (ตรวจสอบ: {vector_fields})")
        else:
            print("[NO] ไม่มี documents ใน index นี้")
    else:
        print(f"[ERROR] Status {response.status_code}: {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

# 4. Check mapping
print("\n" + "="*60)
print(f"4. ตรวจสอบ mapping ของ {index_name}")
print("="*60)
print()

try:
    response = requests.get(
        f"{endpoint}/{index_name}/_mapping",
        auth=awsauth,
        verify=False,
        timeout=10
    )
    
    if response.status_code == 200:
        mapping = response.json()
        index_mapping = mapping[index_name]['mappings']['properties']
        
        print("Mapping fields:")
        vector_fields = {}
        for field_name, field_config in index_mapping.items():
            field_type = field_config.get('type', 'N/A')
            print(f"  - {field_name}: {field_type}")
            
            if field_type in ['knn_vector', 'dense_vector']:
                dimension = field_config.get('dimension', 'N/A')
                print(f"    [OK] Vector field! (dimension: {dimension})")
                vector_fields[field_name] = {
                    'type': field_type,
                    'dimension': dimension
                }
        
        if vector_fields:
            print(f"\n[OK] พบ vector fields ใน mapping:")
            for field_name, config in vector_fields.items():
                print(f"  - {field_name}: {config['type']} (dimension: {config['dimension']})")
        else:
            print(f"\n[NO] ไม่พบ vector fields ใน mapping")
            print("   (ตรวจสอบ: knn_vector หรือ dense_vector)")
    else:
        print(f"[ERROR] Status {response.status_code}: {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "="*60)
print("สรุปผล")
print("="*60)
print(f"  Index: {index_name}")
print(f"  Resume ID: {resume_id}")
print()

