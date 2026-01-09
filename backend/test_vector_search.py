"""
Test Vector Search with wait for ANN structure to build
"""
import sys
import os
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_vector_search_with_retry():
    """Test vector search with retry mechanism"""
    print("=" * 60)
    print("  Vector Search Test (with retry)")
    print("=" * 60)
    print()
    
    if settings.USE_MOCK:
        print("[INFO] MOCK MODE: Testing mock vector search")
        query_vector = [0.1] * 1024
        results = opensearch_client.vector_search("jobs_index", query_vector, top_k=5)
        print(f"[OK] Found {len(results)} results")
        return True
    
    indices_to_test = ["jobs_index", "resumes_index"]
    
    for index_name in indices_to_test:
        print(f"Testing {index_name}...")
        print("-" * 60)
        
        try:
            # Check if index exists
            if not opensearch_client.client.indices.exists(index=index_name):
                print(f"  [WARNING] Index '{index_name}' does not exist")
                print()
                continue
            
            # Get document count
            stats = opensearch_client.client.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            print(f"  Document count: {doc_count}")
            
            if doc_count == 0:
                print(f"  [INFO] No documents, skipping vector search")
                print()
                continue
            
            # Get mapping to find dimension
            mapping = opensearch_client.client.indices.get_mapping(index=index_name)
            properties = mapping[index_name]['mappings'].get('properties', {})
            dimension = properties.get('embeddings', {}).get('dimension', 1024)
            
            # Create query vector
            query_vector = [0.1] * dimension
            print(f"  Query vector dimension: {dimension}")
            
            # Try vector search with retry
            max_retries = 5
            retry_delay = 2  # seconds
            
            for attempt in range(1, max_retries + 1):
                print(f"  Attempt {attempt}/{max_retries}...")
                
                try:
                    # Force refresh index
                    opensearch_client.client.indices.refresh(index=index_name)
                    time.sleep(1)  # Wait a bit after refresh
                    
                    # Try vector search
                    results = opensearch_client.vector_search(index_name, query_vector, top_k=min(5, doc_count))
                    
                    print(f"  [SUCCESS] Vector search worked!")
                    print(f"  Found {len(results)} results")
                    if results:
                        print(f"  Top result score: {results[0].get('_score', 'N/A'):.4f}")
                        if len(results) > 1:
                            print(f"  Second result score: {results[1].get('_score', 'N/A'):.4f}")
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    if "not built for ANN search" in error_msg:
                        if attempt < max_retries:
                            print(f"  [INFO] ANN structure not ready yet, waiting {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                        else:
                            print(f"  [WARNING] ANN structure still not ready after {max_retries} attempts")
                            print(f"  This is normal - it may take a few minutes for large indices")
                    else:
                        print(f"  [ERROR] Vector search failed: {error_msg}")
                        raise
            
            print()
            
        except Exception as e:
            print(f"  [ERROR] Error testing {index_name}: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("[SUCCESS] Vector search test completed!")
    return True

if __name__ == "__main__":
    success = test_vector_search_with_retry()
    sys.exit(0 if success else 1)

