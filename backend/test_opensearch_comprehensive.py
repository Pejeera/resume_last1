"""
ทดสอบ OpenSearch อย่างครอบคลุม
- ทดสอบการเชื่อมต่อ
- สร้าง index พร้อม mapping
- ทดสอบการ index document
- ทดสอบการค้นหา
- ทดสอบ vector search
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger
from datetime import datetime
import json

logger = get_logger(__name__)

def print_thai(message, color=None):
    """Helper to print Thai characters"""
    if color:
        color_code = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "blue": "\033[94m",
            "reset": "\033[0m"
        }.get(color, "")
        sys.stdout.buffer.write(f"{color_code}{message}\033[0m\n".encode('utf-8'))
    else:
        sys.stdout.buffer.write(f"{message}\n".encode('utf-8'))

def test_connection():
    """ทดสอบการเชื่อมต่อ"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ทดสอบการเชื่อมต่อ OpenSearch", "cyan")
    print_thai("="*70, "cyan")
    
    if settings.USE_MOCK:
        print_thai("   [WARNING] กำลังใช้ MOCK mode", "yellow")
        return False
    
    try:
        if opensearch_client.client is None:
            print_thai("   [ERROR] OpenSearch client ไม่ได้ถูกสร้าง", "red")
            return False
        
        info = opensearch_client.client.info()
        print_thai(f"   [OK] เชื่อมต่อสำเร็จ!", "green")
        print_thai(f"   Cluster: {info.get('cluster_name', 'N/A')}", "white")
        print_thai(f"   Version: {info.get('version', {}).get('number', 'N/A')}", "white")
        return True
    except Exception as e:
        print_thai(f"   [ERROR] ไม่สามารถเชื่อมต่อได้: {e}", "red")
        return False

def test_create_jobs_index():
    """ทดสอบการสร้าง jobs_index"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ทดสอบการสร้าง jobs_index", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        index_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "text_excerpt": {"type": "text"},
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": 1024
                    },
                    "metadata": {"type": "object"},
                    "created_at": {"type": "date"}
                }
            }
        }
        
        result = opensearch_client.create_index_if_not_exists("jobs_index", index_mapping)
        if result:
            print_thai("   [OK] สร้าง jobs_index สำเร็จ", "green")
            
            # ตรวจสอบว่า index มีอยู่จริง
            if opensearch_client.client and opensearch_client.client.indices.exists(index="jobs_index"):
                print_thai("   [OK] ตรวจสอบว่า index มีอยู่จริง", "green")
                
                # ดู mapping
                mapping = opensearch_client.client.indices.get_mapping(index="jobs_index")
                print_thai("   [INFO] Index mapping:", "white")
                print(f"      {json.dumps(mapping, indent=2)}")
            return True
        return False
    except Exception as e:
        print_thai(f"   [ERROR] ไม่สามารถสร้าง index ได้: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def test_index_document():
    """ทดสอบการ index document"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ทดสอบการ index document", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        # สร้าง test document
        test_doc = {
            "id": "test_job_001",
            "title": "Software Engineer - Test Position",
            "description": "This is a test job description for OpenSearch testing. We need a skilled developer.",
            "text_excerpt": "Test job for OpenSearch",
            "embeddings": [0.1] * 1024,  # Dummy embedding vector
            "metadata": {
                "location": "Bangkok",
                "salary": "50000-70000",
                "type": "full-time"
            },
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = opensearch_client.index_document("jobs_index", "test_job_001", test_doc)
        if result:
            print_thai("   [OK] Index document สำเร็จ", "green")
            
            # รอให้ index refresh
            if opensearch_client.client:
                opensearch_client.client.indices.refresh(index="jobs_index")
            
            # ลองดึงกลับมา
            retrieved = opensearch_client.get_document("jobs_index", "test_job_001")
            if retrieved:
                print_thai("   [OK] ดึง document กลับมาได้", "green")
                print_thai(f"   Title: {retrieved.get('title', 'N/A')}", "white")
                print_thai(f"   Description: {retrieved.get('description', 'N/A')[:50]}...", "white")
                return True
            else:
                print_thai("   [WARNING] ไม่สามารถดึง document กลับมาได้", "yellow")
                return False
        return False
    except Exception as e:
        print_thai(f"   [ERROR] ไม่สามารถ index document ได้: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def test_search():
    """ทดสอบการค้นหาแบบปกติ"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ทดสอบการค้นหาแบบปกติ (text search)", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        if not opensearch_client.client:
            print_thai("   [ERROR] OpenSearch client ไม่มี", "red")
            return False
        
        # ค้นหาด้วย text
        query = {
            "size": 5,
            "query": {
                "match": {
                    "title": "Software Engineer"
                }
            }
        }
        
        response = opensearch_client.client.search(index="jobs_index", body=query)
        hits = response.get('hits', {}).get('hits', [])
        
        print_thai(f"   [OK] พบ {len(hits)} results", "green")
        for i, hit in enumerate(hits, 1):
            title = hit.get('_source', {}).get('title', 'N/A')
            score = hit.get('_score', 0)
            print_thai(f"   {i}. {title} (score: {score:.2f})", "white")
        
        return len(hits) > 0
    except Exception as e:
        print_thai(f"   [ERROR] ไม่สามารถค้นหาได้: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def test_vector_search():
    """ทดสอบ vector search"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ทดสอบ Vector Search (KNN)", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        # สร้าง query vector (dummy)
        query_vector = [0.1] * 1024
        
        results = opensearch_client.vector_search(
            index_name="jobs_index",
            query_vector=query_vector,
            top_k=5
        )
        
        print_thai(f"   [OK] Vector search สำเร็จ - พบ {len(results)} results", "green")
        for i, result in enumerate(results, 1):
            title = result.get('title', 'N/A')
            score = result.get('_score', 0)
            print_thai(f"   {i}. {title} (score: {score:.4f})", "white")
        
        return len(results) > 0
    except Exception as e:
        print_thai(f"   [ERROR] Vector search ล้มเหลว: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def test_count_documents():
    """นับจำนวน documents"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("นับจำนวน documents ใน jobs_index", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        if not opensearch_client.client:
            print_thai("   [ERROR] OpenSearch client ไม่มี", "red")
            return False
        
        count_result = opensearch_client.client.count(index="jobs_index")
        count = count_result.get('count', 0)
        
        print_thai(f"   [OK] พบ {count} documents ใน jobs_index", "green")
        return True
    except Exception as e:
        print_thai(f"   [ERROR] ไม่สามารถนับ documents ได้: {e}", "red")
        return False

def cleanup_test_data():
    """ลบ test document"""
    print_thai("\n" + "="*70, "cyan")
    print_thai("ลบ test document", "cyan")
    print_thai("="*70, "cyan")
    
    try:
        if opensearch_client.client:
            if opensearch_client.client.exists(index="jobs_index", id="test_job_001"):
                opensearch_client.client.delete(index="jobs_index", id="test_job_001")
                print_thai("   [OK] ลบ test document สำเร็จ", "green")
            else:
                print_thai("   [INFO] test document ไม่มีอยู่แล้ว", "white")
        return True
    except Exception as e:
        print_thai(f"   [WARNING] ไม่สามารถลบ test document ได้: {e}", "yellow")
        return False

def main():
    print_thai("\n" + "="*70, "blue")
    print_thai("ทดสอบ OpenSearch อย่างครอบคลุม", "blue")
    print_thai("="*70, "blue")
    print_thai(f"\nOpenSearch Endpoint: {settings.OPENSEARCH_ENDPOINT}", "white")
    print_thai(f"USE_MOCK: {settings.USE_MOCK}", "white")
    print_thai(f"AWS Region: {settings.AWS_REGION}", "white")
    
    results = {}
    
    # Test 1: Connection
    results['connection'] = test_connection()
    
    if not results['connection']:
        print_thai("\n[ERROR] ไม่สามารถเชื่อมต่อ OpenSearch ได้ - หยุดการทดสอบ", "red")
        return
    
    # Test 2: Create index
    results['create_index'] = test_create_jobs_index()
    
    # Test 3: Index document
    results['index_document'] = test_index_document()
    
    # Test 4: Search
    if results['index_document']:
        results['search'] = test_search()
        results['vector_search'] = test_vector_search()
    
    # Test 5: Count
    results['count'] = test_count_documents()
    
    # Cleanup
    cleanup_test_data()
    
    # Summary
    print_thai("\n" + "="*70, "blue")
    print_thai("สรุปผลการทดสอบ", "blue")
    print_thai("="*70, "blue")
    
    for test_name, passed in results.items():
        if passed:
            print_thai(f"   ✅ {test_name}: ผ่าน", "green")
        else:
            print_thai(f"   ❌ {test_name}: ไม่ผ่าน", "red")
    
    all_passed = all(results.values())
    if all_passed:
        print_thai("\n🎉 ทุกการทดสอบผ่าน! OpenSearch พร้อมใช้งาน", "green")
    else:
        print_thai("\n⚠️  มีบางการทดสอบไม่ผ่าน - ตรวจสอบข้อผิดพลาดด้านบน", "yellow")
    
    print_thai("="*70 + "\n", "blue")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_thai("\n\n[WARNING] ยกเลิกการทดสอบ", "yellow")
        sys.exit(1)
    except Exception as e:
        print_thai(f"\n\n[ERROR] เกิดข้อผิดพลาด: {e}", "red")
        import traceback
        traceback.print_exc()
        sys.exit(1)

