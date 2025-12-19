"""
Test OpenSearch Connection
ตรวจสอบว่า OpenSearch ใช้งานได้หรือไม่
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_opensearch_connection():
    """Test OpenSearch connection and configuration"""
    print("=" * 60)
    print("ทดสอบการเชื่อมต่อ OpenSearch")
    print("=" * 60)
    print()
    
    # Check configuration
    print("[1/4] ตรวจสอบการตั้งค่า...")
    print(f"   USE_MOCK: {settings.USE_MOCK}")
    print(f"   OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    print(f"   OPENSEARCH_USERNAME: {settings.OPENSEARCH_USERNAME}")
    print(f"   OPENSEARCH_USE_SSL: {settings.OPENSEARCH_USE_SSL}")
    print(f"   OPENSEARCH_VERIFY_CERTS: {settings.OPENSEARCH_VERIFY_CERTS}")
    print()
    
    if settings.USE_MOCK:
        print("   [WARNING] กำลังใช้ MOCK mode - OpenSearch จริงจะไม่ถูกใช้งาน")
        print("   [TIP] ตั้ง USE_MOCK=false เพื่อใช้ OpenSearch จริง")
        print()
        return False
    
    # Test connection
    print("[2/4] ทดสอบการเชื่อมต่อ...")
    try:
        if opensearch_client.client is None:
            print("   [ERROR] OpenSearch client ไม่ได้ถูกสร้าง")
            return False
        
        # Try to get cluster info
        info = opensearch_client.client.info()
        print(f"   [OK] เชื่อมต่อสำเร็จ!")
        print(f"   Cluster Name: {info.get('cluster_name', 'N/A')}")
        print(f"   Version: {info.get('version', {}).get('number', 'N/A')}")
        print()
    except Exception as e:
        print(f"   [ERROR] ไม่สามารถเชื่อมต่อได้: {e}")
        print()
        return False
    
    # Test index operations
    print("[3/4] ทดสอบการสร้าง index...")
    try:
        test_index = "test_index_connection"
        test_mapping = {
            "mappings": {
                "properties": {
                    "test_field": {"type": "text"}
                }
            }
        }
        
        result = opensearch_client.create_index_if_not_exists(test_index, test_mapping)
        if result:
            print(f"   [OK] สร้าง index '{test_index}' สำเร็จ")
        print()
    except Exception as e:
        print(f"   [ERROR] ไม่สามารถสร้าง index ได้: {e}")
        print()
        return False
    
    # Test document indexing
    print("[4/4] ทดสอบการ index document...")
    try:
        test_doc = {
            "test_field": "Hello OpenSearch",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        result = opensearch_client.index_document(test_index, "test_doc_1", test_doc)
        if result:
            print(f"   [OK] Index document สำเร็จ")
        
        # Try to retrieve it
        retrieved = opensearch_client.get_document(test_index, "test_doc_1")
        if retrieved:
            print(f"   [OK] ดึง document กลับมาได้: {retrieved.get('test_field')}")
        print()
    except Exception as e:
        print(f"   [ERROR] ไม่สามารถ index document ได้: {e}")
        print()
        return False
    
    # Cleanup test index
    try:
        if opensearch_client.client and opensearch_client.client.indices.exists(index=test_index):
            opensearch_client.client.indices.delete(index=test_index)
            print(f"   [CLEANUP] ลบ test index '{test_index}' แล้ว")
    except:
        pass
    
    print("=" * 60)
    print("[SUCCESS] ทุกอย่างทำงานได้ปกติ! OpenSearch พร้อมใช้งาน")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_opensearch_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] ยกเลิกการทดสอบ")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

