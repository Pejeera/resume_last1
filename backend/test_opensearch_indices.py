"""
Test OpenSearch Indices (jobs_index and resumes_index)
"""
import sys
import os
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

def test_production_indices():
    """Test the actual production indices (jobs_index and resumes_index)"""
    print("=" * 60)
    print("  OpenSearch Production Indices Test")
    print("=" * 60)
    print()
    
    if settings.USE_MOCK:
        print("[WARNING] MOCK MODE: Testing mock indices")
        print()
        return test_mock_indices()
    
    print("Testing Production Indices:")
    print()
    
    indices_to_test = ["jobs_index", "resumes_index"]
    
    for index_name in indices_to_test:
        print(f"Testing {index_name}...")
        print("-" * 60)
        
        try:
            # Check if index exists
            exists = opensearch_client.client.indices.exists(index=index_name)
            if not exists:
                print(f"  [WARNING] Index '{index_name}' does not exist")
                print(f"  Run 'python infra/create_opensearch_indices.py' to create it")
                print()
                continue
            
            print(f"  [OK] Index exists")
            
            # Get index stats
            stats = opensearch_client.client.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            print(f"  [OK] Document count: {doc_count}")
            
            # Get index mapping
            mapping = opensearch_client.client.indices.get_mapping(index=index_name)
            properties = mapping[index_name]['mappings'].get('properties', {})
            
            # Check if embeddings field exists
            if 'embeddings' in properties:
                emb_type = properties['embeddings'].get('type', 'unknown')
                emb_dim = properties['embeddings'].get('dimension', 'unknown')
                print(f"  [OK] Embeddings field: type={emb_type}, dimension={emb_dim}")
            else:
                print(f"  [WARNING] Embeddings field not found in mapping")
            
            # Test vector search if embeddings exist and we have documents
            if 'embeddings' in properties and doc_count > 0:
                print(f"  Testing vector search...")
                try:
                    # Create a dummy query vector with correct dimension
                    dimension = properties['embeddings'].get('dimension', 1024)
                    query_vector = [0.1] * dimension
                    
                    # Refresh index first
                    opensearch_client.client.indices.refresh(index=index_name)
                    
                    results = opensearch_client.vector_search(index_name, query_vector, top_k=3)
                    print(f"  [OK] Vector search: Found {len(results)} results")
                    if results:
                        print(f"       Top result score: {results[0].get('_score', 'N/A'):.4f}")
                except Exception as vec_error:
                    error_msg = str(vec_error)
                    if "not built for ANN search" in error_msg:
                        print(f"  [WARNING] Vector search: Index needs time to build ANN structure")
                        print(f"       Wait a few seconds and the index will be ready")
                    else:
                        print(f"  [ERROR] Vector search failed: {vec_error}")
            elif doc_count == 0:
                print(f"  [INFO] No documents in index, skipping vector search test")
            
            print()
            
        except Exception as e:
            print(f"  [ERROR] Error testing {index_name}: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("[SUCCESS] Production indices test completed!")
    return True

def test_mock_indices():
    """Test mock indices"""
    print("Mock indices status:")
    for index_name in ["jobs_index", "resumes_index"]:
        count = len(opensearch_client._mock_data_storage.get(index_name, []))
        print(f"  {index_name}: {count} documents")
    print()
    print("[SUCCESS] Mock indices test completed!")
    return True

if __name__ == "__main__":
    success = test_production_indices()
    sys.exit(0 if success else 1)

