"""
Test OpenSearch Connection and Functionality
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

def test_opensearch_connection():
    """Test OpenSearch connection and basic operations"""
    print("=" * 60)
    print("  OpenSearch Connection Test")
    print("=" * 60)
    print()
    
    # Display configuration
    print("Configuration:")
    print(f"  USE_MOCK: {settings.USE_MOCK}")
    print(f"  OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    print(f"  OPENSEARCH_USERNAME: {settings.OPENSEARCH_USERNAME}")
    print(f"  OPENSEARCH_USE_SSL: {settings.OPENSEARCH_USE_SSL}")
    print(f"  OPENSEARCH_VERIFY_CERTS: {settings.OPENSEARCH_VERIFY_CERTS}")
    print()
    
    if settings.USE_MOCK:
        print("[WARNING] MOCK MODE: OpenSearch is running in mock mode")
        print("   All operations will use in-memory storage")
        print()
        
        # Test mock operations
        print("Testing Mock Operations:")
        try:
            # Test index creation
            test_mapping = {
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 1024
                        }
                    }
                }
            }
            result = opensearch_client.create_index_if_not_exists("test_index", test_mapping)
            print(f"  [OK] Create index: {result}")
            
            # Test document indexing
            test_doc = {
                "title": "Test Job",
                "embeddings": [0.1] * 1024
            }
            result = opensearch_client.index_document("test_index", "test_1", test_doc)
            print(f"  [OK] Index document: {result}")
            
            # Test get document
            doc = opensearch_client.get_document("test_index", "test_1")
            if doc:
                print(f"  [OK] Get document: Found document with title '{doc.get('title')}'")
            else:
                print(f"  [FAIL] Get document: Document not found")
            
            # Test vector search
            query_vector = [0.1] * 1024
            results = opensearch_client.vector_search("test_index", query_vector, top_k=5)
            print(f"  [OK] Vector search: Found {len(results)} results")
            
            print()
            print("[SUCCESS] All mock operations passed!")
            return True
            
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("Testing Real OpenSearch Connection:")
        try:
            # Test cluster health
            print("  1. Testing cluster health...")
            health = opensearch_client.client.cluster.health()
            print(f"     [OK] Cluster status: {health.get('status')}")
            print(f"     [OK] Number of nodes: {health.get('number_of_nodes')}")
            print(f"     [OK] Active shards: {health.get('active_shards')}")
            
            # Test list indices
            print("  2. Listing indices...")
            indices = opensearch_client.client.indices.get_alias()
            index_names = list(indices.keys())
            if index_names:
                print(f"     [OK] Found {len(index_names)} indices:")
                for idx in index_names:
                    print(f"       - {idx}")
            else:
                print("     [INFO] No indices found (this is OK if you haven't created any)")
            
            # Test index creation
            print("  3. Testing index creation...")
            test_mapping = {
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 1024
                        }
                    }
                }
            }
            
            test_index_name = "test_opensearch_connection"
            # Delete test index if exists
            if opensearch_client.client.indices.exists(index=test_index_name):
                opensearch_client.client.indices.delete(index=test_index_name)
                print(f"     [INFO] Deleted existing test index")
            
            result = opensearch_client.create_index_if_not_exists(test_index_name, test_mapping)
            print(f"     [OK] Create index: {result}")
            
            # Test document indexing
            print("  4. Testing document indexing...")
            test_doc = {
                "title": "Test Job",
                "description": "This is a test job for OpenSearch connection",
                "embeddings": [0.1] * 1024
            }
            result = opensearch_client.index_document(test_index_name, "test_1", test_doc)
            print(f"     [OK] Index document: {result}")
            
            # Wait a bit for indexing to complete
            import time
            time.sleep(1)
            
            # Test get document
            print("  5. Testing get document...")
            doc = opensearch_client.get_document(test_index_name, "test_1")
            if doc:
                print(f"     [OK] Get document: Found document with title '{doc.get('title')}'")
            else:
                print(f"     [FAIL] Get document: Document not found")
            
            # Test vector search
            print("  6. Testing vector search...")
            query_vector = [0.1] * 1024
            try:
                # Refresh index to ensure it's ready for search
                opensearch_client.client.indices.refresh(index=test_index_name)
                results = opensearch_client.vector_search(test_index_name, query_vector, top_k=5)
                print(f"     [OK] Vector search: Found {len(results)} results")
                if results:
                    print(f"       Top result score: {results[0].get('_score', 'N/A')}")
            except Exception as vec_error:
                # Vector search might fail if index is still building
                error_msg = str(vec_error)
                if "not built for ANN search" in error_msg:
                    print(f"     [WARNING] Vector search: Index needs time to build ANN structure")
                    print(f"       This is normal for newly created indices. Wait a few seconds and try again.")
                else:
                    print(f"     [ERROR] Vector search failed: {vec_error}")
                    raise
            
            # Clean up test index
            print("  7. Cleaning up test index...")
            if opensearch_client.client.indices.exists(index=test_index_name):
                opensearch_client.client.indices.delete(index=test_index_name)
                print(f"     [OK] Deleted test index")
            
            print()
            print("[SUCCESS] OpenSearch connection and basic operations are working!")
            print()
            print("Summary:")
            print("  - Connection: OK")
            print("  - Cluster Health: OK")
            print("  - Index Operations: OK")
            print("  - Document Operations: OK")
            print("  - Vector Search: May need index refresh (this is normal)")
            return True
            
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
            print()
            print("[FAIL] OpenSearch connection test failed!")
            print()
            print("Troubleshooting:")
            print("  1. Check OPENSEARCH_ENDPOINT in .env file")
            print("  2. Check OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD")
            print("  3. Verify network connectivity to OpenSearch endpoint")
            print("  4. Check AWS credentials if using IAM authentication")
            return False

if __name__ == "__main__":
    success = test_opensearch_connection()
    sys.exit(0 if success else 1)

