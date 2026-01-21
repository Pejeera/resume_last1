"""
Script to check OpenSearch counts with provided credentials
"""
from opensearchpy import OpenSearch
import sys

# Credentials provided
OPENSEARCH_ENDPOINT = "https://search-resume-search-dev-hfdsgupxj4uwviltrlqhpc2liu.ap-southeast-2.es.amazonaws.com"
OPENSEARCH_USERNAME = "jeerasee@metrosystems.co.th"
OPENSEARCH_PASSWORD = "Namwan2546."

def check_opensearch_counts():
    """Count documents in OpenSearch indices"""
    try:
        # Parse endpoint
        endpoint = OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '')
        host = endpoint.split(':')[0] if ':' not in endpoint else endpoint.split(':')[0]
        port = int(endpoint.split(':')[1]) if ':' in endpoint else 443
        
        print(f"Connecting to OpenSearch...")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Username: {OPENSEARCH_USERNAME}")
        print()
        
        opensearch_client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
            use_ssl=True,
            verify_certs=False,  # Set to False for self-signed certs
            ssl_show_warn=False
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
            # Try to check if index exists
            try:
                exists = opensearch_client.indices.exists(index="resumes_index")
                print(f"  Index 'resumes_index' exists: {exists}")
            except:
                pass
        
        # Count jobs
        jobs_count = 0
        try:
            response = opensearch_client.count(index="jobs_index")
            jobs_count = response.get('count', 0)
            print(f"  [OK] Jobs index count: {jobs_count}")
        except Exception as e:
            print(f"  [WARNING] Error counting jobs: {e}")
            # Try to check if index exists
            try:
                exists = opensearch_client.indices.exists(index="jobs_index")
                print(f"  Index 'jobs_index' exists: {exists}")
            except:
                pass
        
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
    print("Checking OpenSearch with provided credentials")
    print("=" * 60)
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
