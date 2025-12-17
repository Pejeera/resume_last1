"""
Test OpenSearch connection and operations
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def test_opensearch_connection():
    """Test OpenSearch connection"""
    print("=" * 60)
    print("Testing OpenSearch Connection")
    print("=" * 60)
    
    # Get config
    endpoint = os.getenv('OPENSEARCH_ENDPOINT', 'https://localhost:9200')
    username = os.getenv('OPENSEARCH_USERNAME', 'admin')
    password = os.getenv('OPENSEARCH_PASSWORD', 'admin')
    use_ssl = os.getenv('OPENSEARCH_USE_SSL', 'true').lower() == 'true'
    verify_certs = os.getenv('OPENSEARCH_VERIFY_CERTS', 'false').lower() == 'true'
    
    print(f"Endpoint: {endpoint}")
    print(f"Username: {username}")
    print(f"Use SSL: {use_ssl}")
    print(f"Verify Certs: {verify_certs}")
    
    # Parse endpoint - remove protocol and any path
    host = endpoint.replace('https://', '').replace('http://', '')
    # Remove any path (e.g., /_dashboards)
    if '/' in host:
        host = host.split('/')[0]
    # Remove port if present
    if ':' in host:
        host = host.split(':')[0]
    port = 443 if use_ssl else 9200
    
    print(f"Parsed Host: {host}")
    print(f"Port: {port}")
    print()
    
    try:
        
        client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=(username, password),
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            connection_class=RequestsHttpConnection
        )
        
        # Test connection
        info = client.info()
        print(f"[OK] Connected to OpenSearch!")
        print(f"     Cluster: {info.get('cluster_name', 'N/A')}")
        print(f"     Version: {info.get('version', {}).get('number', 'N/A')}")
        print()
        
        return client
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        print()
        print("[INFO] Possible reasons:")
        print("  1. OpenSearch is in a VPC and not accessible from local machine")
        print("  2. Need VPN connection or EC2 instance in the same VPC")
        print("  3. Security group rules may block access")
        print("  4. Network connectivity issues")
        print()
        print("[INFO] To test OpenSearch:")
        print("  - Use VPN to connect to the VPC")
        print("  - Run this script from an EC2 instance in the same VPC")
        print("  - Or configure OpenSearch with public access (not recommended for production)")
        print()
        import traceback
        traceback.print_exc()
        return None

def test_create_indices(client):
    """Test creating indices"""
    print("=" * 60)
    print("Testing Index Creation")
    print("=" * 60)
    
    if not client:
        print("[SKIP] No OpenSearch client available")
        return False
    
    try:
        # Load mappings
        mapping_file = Path(__file__).parent.parent / 'infra' / 'opensearch_index_mapping.json'
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mappings = json.load(f)
        
        # Create jobs_index
        jobs_mapping = mappings.get('jobs_index', {})
        index_name = 'jobs_index'
        
        if client.indices.exists(index=index_name):
            print(f"[INFO] Index {index_name} already exists. Deleting...")
            client.indices.delete(index=index_name)
        
        client.indices.create(index=index_name, body=jobs_mapping)
        print(f"[OK] Created index: {index_name}")
        
        # Create resumes_index
        resumes_mapping = mappings.get('resumes_index', {})
        index_name = 'resumes_index'
        
        if client.indices.exists(index=index_name):
            print(f"[INFO] Index {index_name} already exists. Deleting...")
            client.indices.delete(index=index_name)
        
        client.indices.create(index=index_name, body=resumes_mapping)
        print(f"[OK] Created index: {index_name}")
        print()
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create indices: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_index_document(client):
    """Test indexing a document"""
    print("=" * 60)
    print("Testing Document Indexing")
    print("=" * 60)
    
    if not client:
        print("[SKIP] No OpenSearch client available")
        return False
    
    try:
        # Create a test job document
        test_job = {
            "title": "Test Senior Backend Engineer",
            "description": "We are looking for a Senior Backend Engineer with experience in Python, FastAPI, and AWS.",
            "text_excerpt": "Senior Backend Engineer Python FastAPI AWS",
            "metadata": {
                "location": "Bangkok",
                "salary_range": "80k-120k",
                "experience_years": "5+"
            },
            "embeddings": [0.1] * 1024  # Mock embedding vector (use 'embeddings' field name from mapping)
        }
        
        doc_id = "test-job-001"
        client.index(index='jobs_index', id=doc_id, body=test_job)
        print(f"[OK] Indexed test document: {doc_id}")
        
        # Verify document exists
        result = client.get(index='jobs_index', id=doc_id)
        print(f"[OK] Verified document exists: {result['_source']['title']}")
        print()
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to index document: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vector_search(client):
    """Test vector search"""
    print("=" * 60)
    print("Testing Vector Search")
    print("=" * 60)
    
    if not client:
        print("[SKIP] No OpenSearch client available")
        return False
    
    try:
        # Create query vector
        query_vector = [0.1] * 1024
        
        # Vector search query (use 'embeddings' field name from mapping)
        search_body = {
            "size": 5,
            "query": {
                "knn": {
                    "embeddings": {
                        "vector": query_vector,
                        "k": 5
                    }
                }
            }
        }
        
        result = client.search(index='jobs_index', body=search_body)
        hits = result.get('hits', {}).get('hits', [])
        
        print(f"[OK] Vector search returned {len(hits)} results")
        for i, hit in enumerate(hits, 1):
            print(f"     {i}. {hit['_source'].get('title', 'N/A')} (score: {hit.get('_score', 0):.4f})")
        print()
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed vector search: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_load_jobs_from_s3_and_index(client):
    """Load jobs from S3 and index them to OpenSearch"""
    print("=" * 60)
    print("Testing: Load Jobs from S3 and Index to OpenSearch")
    print("=" * 60)
    
    if not client:
        print("[SKIP] No OpenSearch client available")
        return False
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Get S3 config
        bucket_name = os.getenv('S3_BUCKET_NAME')
        s3_prefix = os.getenv('S3_PREFIX', 'resumes/')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        if not bucket_name:
            print("[ERROR] S3_BUCKET_NAME not found")
            return False
        
        # Load from S3
        s3_client = boto3.client(
            's3',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        s3_key = f"{s3_prefix}jobs_data.json"
        print(f"[INFO] Loading jobs from S3: s3://{bucket_name}/{s3_key}")
        
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        jobs_data = json.loads(response['Body'].read().decode('utf-8'))
        print(f"[OK] Loaded {len(jobs_data)} jobs from S3")
        
        # Index first 5 jobs as test
        test_count = min(5, len(jobs_data))
        print(f"[INFO] Indexing first {test_count} jobs to OpenSearch...")
        
        indexed = 0
        for i, job in enumerate(jobs_data[:test_count]):
            try:
                doc_id = job.get('_id', f"job-{i+1}")
                # Remove _id from document body
                job_body = {k: v for k, v in job.items() if k != '_id'}
                client.index(index='jobs_index', id=doc_id, body=job_body)
                indexed += 1
                print(f"     [{i+1}] Indexed: {job.get('title', 'N/A')}")
            except Exception as e:
                print(f"     [ERROR] Failed to index job {i+1}: {e}")
        
        print(f"[OK] Successfully indexed {indexed}/{test_count} jobs")
        print()
        
        return True
    except ClientError as e:
        print(f"[ERROR] S3 error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_document(client):
    """Test retrieving a document"""
    print("=" * 60)
    print("Testing Document Retrieval")
    print("=" * 60)
    
    if not client:
        print("[SKIP] No OpenSearch client available")
        return False
    
    try:
        # Try to get the test document
        result = client.get(index='jobs_index', id='test-job-001')
        doc = result['_source']
        print(f"[OK] Retrieved document: {doc.get('title', 'N/A')}")
        print(f"     Description: {doc.get('description', 'N/A')[:100]}...")
        print()
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to retrieve document: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("OpenSearch Test Suite")
    print("=" * 60 + "\n")
    
    # Test 1: Connection
    client = test_opensearch_connection()
    if not client:
        print("\n[ERROR] Cannot proceed without OpenSearch connection")
        return
    
    # Test 2: Create indices
    if not test_create_indices(client):
        print("\n[ERROR] Failed to create indices")
        return
    
    # Test 3: Index document
    test_index_document(client)
    
    # Test 4: Get document
    test_get_document(client)
    
    # Test 5: Vector search
    test_vector_search(client)
    
    # Test 6: Load from S3 and index
    test_load_jobs_from_s3_and_index(client)
    
    # Final vector search with real data
    print("=" * 60)
    print("Final Vector Search Test (with indexed jobs)")
    print("=" * 60)
    test_vector_search(client)
    
    print("\n" + "=" * 60)
    print("[OK] All tests completed!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

