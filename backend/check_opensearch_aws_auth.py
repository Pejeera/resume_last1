"""
Script to check OpenSearch counts using AWS IAM authentication
"""
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3
from app.core.config import settings

def check_opensearch_counts():
    """Count documents in OpenSearch indices using AWS IAM auth"""
    try:
        # Parse endpoint
        endpoint = settings.OPENSEARCH_ENDPOINT
        host = endpoint.replace('https://', '').replace('http://', '')
        if ':' in host:
            host, _ = host.rsplit(':', 1)
        
        port = 443
        
        # Extract region
        opensearch_region = settings.AWS_REGION
        if '.es.amazonaws.com' in host or '.aoss.amazonaws.com' in host:
            parts = host.split('.')
            for part in parts:
                if part.startswith('ap-') or part.startswith('us-') or part.startswith('eu-') or part.startswith('sa-') or part.startswith('ca-') or part.startswith('cn-'):
                    opensearch_region = part
                    break
        
        print(f"Connecting to OpenSearch...")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Region: {opensearch_region}")
        print()
        
        # Get AWS credentials
        credentials = boto3.Session().get_credentials()
        if not credentials:
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                print("Using credentials from settings...")
                awsauth = AWS4Auth(
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY,
                    opensearch_region,
                    'es'
                )
            else:
                print("[ERROR] No AWS credentials found!")
                return None, None
        else:
            print("Using IAM role credentials...")
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
            verify_certs=False,  # Set to False for local testing (SSL cert issues)
            ssl_show_warn=False,
            connection_class=RequestsHttpConnection
        )
        
        # Test connection
        print("Testing connection...")
        info = opensearch_client.info()
        print(f"  [OK] Connected! OpenSearch version: {info.get('version', {}).get('number', 'unknown')}")
        print()
        
        # Count resumes
        resumes_count = 0
        try:
            response = opensearch_client.count(index="resumes_index")
            resumes_count = response.get('count', 0)
            print(f"  [OK] Resumes index count: {resumes_count}")
        except Exception as e:
            print(f"  [WARNING] Error counting resumes: {e}")
            try:
                exists = opensearch_client.indices.exists(index="resumes_index")
                print(f"  Index 'resumes_index' exists: {exists}")
                if exists:
                    # Try to get some sample documents
                    search_response = opensearch_client.search(index="resumes_index", body={"size": 0})
                    resumes_count = search_response.get('hits', {}).get('total', {}).get('value', 0)
                    print(f"  Resumes count (from search): {resumes_count}")
            except Exception as e2:
                print(f"  Could not check index: {e2}")
        
        # Count jobs
        jobs_count = 0
        try:
            response = opensearch_client.count(index="jobs_index")
            jobs_count = response.get('count', 0)
            print(f"  [OK] Jobs index count: {jobs_count}")
        except Exception as e:
            print(f"  [WARNING] Error counting jobs: {e}")
            try:
                exists = opensearch_client.indices.exists(index="jobs_index")
                print(f"  Index 'jobs_index' exists: {exists}")
                if exists:
                    # Try to get some sample documents
                    search_response = opensearch_client.search(index="jobs_index", body={"size": 0})
                    jobs_count = search_response.get('hits', {}).get('total', {}).get('value', 0)
                    print(f"  Jobs count (from search): {jobs_count}")
            except Exception as e2:
                print(f"  Could not check index: {e2}")
        
        # List all indices
        print()
        print("All indices in OpenSearch:")
        try:
            indices = opensearch_client.indices.get_alias()
            for index_name in indices.keys():
                try:
                    count_response = opensearch_client.count(index=index_name)
                    count = count_response.get('count', 0)
                    print(f"  - {index_name}: {count} documents")
                except:
                    try:
                        search_response = opensearch_client.search(index=index_name, body={"size": 0})
                        count = search_response.get('hits', {}).get('total', {}).get('value', 0)
                        print(f"  - {index_name}: {count} documents (from search)")
                    except:
                        print(f"  - {index_name}: (could not count)")
        except Exception as e:
            print(f"  [ERROR] Could not list indices: {e}")
        
        return resumes_count, jobs_count
    except Exception as e:
        print(f"[ERROR] Failed to connect to OpenSearch: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    print("=" * 60)
    print("Checking OpenSearch with AWS IAM Authentication")
    print("=" * 60)
    print(f"OpenSearch Endpoint: {settings.OPENSEARCH_ENDPOINT}")
    print(f"AWS Region: {settings.AWS_REGION}")
    print()
    
    resumes_count, jobs_count = check_opensearch_counts()
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Resumes in OpenSearch: {resumes_count if resumes_count is not None else 'N/A'}")
    print(f"Jobs in OpenSearch: {jobs_count if jobs_count is not None else 'N/A'}")
    print("=" * 60)

if __name__ == "__main__":
    main()
