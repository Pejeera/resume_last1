"""
Check documents in OpenSearch indices to see if they have embeddings
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

def check_documents():
    """Check documents in indices"""
    print("=" * 60)
    print("  OpenSearch Documents Check")
    print("=" * 60)
    print()
    
    if settings.USE_MOCK:
        print("[INFO] MOCK MODE")
        for index_name in ["jobs_index", "resumes_index"]:
            docs = opensearch_client._mock_data_storage.get(index_name, [])
            print(f"{index_name}: {len(docs)} documents")
        return
    
    indices_to_check = ["jobs_index", "resumes_index"]
    
    for index_name in indices_to_check:
        print(f"Checking {index_name}...")
        print("-" * 60)
        
        try:
            if not opensearch_client.client.indices.exists(index=index_name):
                print(f"  [WARNING] Index does not exist")
                print()
                continue
            
            # Get all documents (limit to 10 for display)
            response = opensearch_client.client.search(
                index=index_name,
                body={
                    "size": 10,
                    "query": {"match_all": {}},
                    "_source": ["id", "title", "name", "embeddings"]
                }
            )
            
            hits = response['hits']['hits']
            total = response['hits']['total']['value']
            
            print(f"  Total documents: {total}")
            print(f"  Showing first {len(hits)} documents:")
            print()
            
            docs_with_embeddings = 0
            docs_without_embeddings = 0
            
            for i, hit in enumerate(hits, 1):
                doc = hit['_source']
                doc_id = doc.get('id') or hit.get('_id', 'N/A')
                title = doc.get('title') or doc.get('name', 'N/A')
                embeddings = doc.get('embeddings')
                
                has_embeddings = embeddings is not None and len(embeddings) > 0
                
                if has_embeddings:
                    docs_with_embeddings += 1
                    emb_len = len(embeddings)
                    print(f"  [{i}] ID: {doc_id}")
                    print(f"      Title: {title[:50]}...")
                    print(f"      Embeddings: {emb_len} dimensions [OK]")
                else:
                    docs_without_embeddings += 1
                    print(f"  [{i}] ID: {doc_id}")
                    print(f"      Title: {title[:50]}...")
                    print(f"      Embeddings: MISSING [WARNING]")
                print()
            
            print(f"  Summary:")
            print(f"    Documents with embeddings: {docs_with_embeddings}")
            print(f"    Documents without embeddings: {docs_without_embeddings}")
            print()
            
            if docs_without_embeddings > 0:
                print(f"  [WARNING] Some documents are missing embeddings!")
                print(f"  Vector search requires embeddings to be present.")
                print(f"  Make sure documents are indexed with embeddings field.")
            elif docs_with_embeddings > 0:
                print(f"  [INFO] All checked documents have embeddings.")
                print(f"  ANN structure should build automatically.")
                print(f"  If vector search still fails, wait a few more minutes.")
            
            print()
            
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
            print()

if __name__ == "__main__":
    check_documents()

