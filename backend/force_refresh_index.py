"""
Force refresh OpenSearch index to build ANN structure
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

def force_refresh_indices():
    """Force refresh indices to build ANN structure"""
    print("=" * 60)
    print("  Force Refresh OpenSearch Indices")
    print("=" * 60)
    print()
    
    if settings.USE_MOCK:
        print("[INFO] MOCK MODE: Skipping refresh")
        return True
    
    indices = ["jobs_index", "resumes_index"]
    
    for index_name in indices:
        print(f"Refreshing {index_name}...")
        try:
            # Force refresh
            opensearch_client.client.indices.refresh(index=index_name)
            print(f"  [OK] Refreshed {index_name}")
            
            # Force flush (writes all pending changes to disk)
            opensearch_client.client.indices.flush(index=index_name)
            print(f"  [OK] Flushed {index_name}")
            
            # Wait a bit
            time.sleep(2)
            
        except Exception as e:
            print(f"  [ERROR] Failed to refresh {index_name}: {e}")
    
    print()
    print("[SUCCESS] Indices refreshed!")
    print()
    print("Note: ANN structure may still need time to build.")
    print("If vector search still fails, wait a few more minutes.")
    return True

if __name__ == "__main__":
    force_refresh_indices()

