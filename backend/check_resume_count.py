"""
Script to check total number of resumes in OpenSearch
"""
import sys
import json
import io
import urllib3
from app.clients.opensearch_client import opensearch_client
from app.core.config import settings
from app.core.logging import get_logger

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Disable SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


def count_resumes(skip_ssl=False):
    """Count total resumes in OpenSearch"""
    print("\n" + "="*60)
    print("เช็คจำนวน Resume ใน OpenSearch")
    print("="*60)
    
    index_name = "resumes_index"
    
    # If skip_ssl is True, temporarily modify the client
    if skip_ssl and not settings.USE_MOCK and opensearch_client.client:
        try:
            # Try to disable SSL verification for local testing
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            # Note: OpenSearch client doesn't easily allow disabling SSL verification
            # This is a workaround - may not work in all cases
            print("[WARNING] Attempting to skip SSL verification (may not work)")
        except:
            pass
    
    if settings.USE_MOCK:
        print("\n[INFO] อยู่ในโหมด MOCK")
        mock_docs = opensearch_client._mock_data_storage.get(index_name, [])
        total_count = len(mock_docs)
        print(f"\nจำนวน Resume ใน Mock Storage: {total_count}")
        
        if total_count > 0:
            print("\nรายละเอียด Resume:")
            print("-" * 60)
            
            # Group by name to find duplicates
            name_groups = {}
            for doc in mock_docs:
                name = doc.get('name', 'N/A')
                resume_id = doc.get('id') or doc.get('_id', 'N/A')
                if name not in name_groups:
                    name_groups[name] = []
                name_groups[name].append({
                    'id': resume_id,
                    'created_at': doc.get('created_at', 'N/A'),
                    's3_key': doc.get('s3_key', 'N/A')
                })
            
            for name, resumes in name_groups.items():
                print(f"\n📄 {name}")
                print(f"   จำนวน: {len(resumes)}")
                for i, resume in enumerate(resumes, 1):
                    print(f"   [{i}] ID: {resume['id']}")
                    print(f"       Created: {resume['created_at']}")
                    print(f"       S3 Key: {resume['s3_key']}")
        
        return total_count
    
    try:
        # Count total documents
        count_query = {
            "query": {
                "match_all": {}
            }
        }
        
        response = opensearch_client.client.count(
            index=index_name,
            body=count_query
        )
        
        total_count = response['count']
        print(f"\nจำนวน Resume ทั้งหมด: {total_count}")
        
        if total_count > 0:
            # Get all resumes with details
            search_query = {
                "query": {
                    "match_all": {}
                },
                "size": 1000,  # Get up to 1000 resumes
                "_source": ["id", "name", "created_at", "s3_key", "s3_url"]
            }
            
            response = opensearch_client.client.search(
                index=index_name,
                body=search_query
            )
            
            hits = response['hits']['hits']
            print(f"\nแสดงรายละเอียด Resume (แสดง {len(hits)} จาก {total_count}):")
            print("-" * 60)
            
            # Group by name to find duplicates
            name_groups = {}
            for hit in hits:
                doc = hit['_source']
                name = doc.get('name', 'N/A')
                resume_id = doc.get('id') or hit.get('_id', 'N/A')
                if name not in name_groups:
                    name_groups[name] = []
                name_groups[name].append({
                    'id': resume_id,
                    'created_at': doc.get('created_at', 'N/A'),
                    's3_key': doc.get('s3_key', 'N/A'),
                    's3_url': doc.get('s3_url', 'N/A')
                })
            
            # Show duplicates first
            duplicates = {name: resumes for name, resumes in name_groups.items() if len(resumes) > 1}
            unique = {name: resumes for name, resumes in name_groups.items() if len(resumes) == 1}
            
            if duplicates:
                print("\n⚠️  พบ Resume ที่มีชื่อซ้ำกัน (Duplicates):")
                print("=" * 60)
                for name, resumes in duplicates.items():
                    print(f"\n📄 {name}")
                    print(f"   จำนวน: {len(resumes)} (ซ้ำกัน!)")
                    for i, resume in enumerate(resumes, 1):
                        print(f"   [{i}] ID: {resume['id']}")
                        print(f"       Created: {resume['created_at']}")
                        print(f"       S3 Key: {resume['s3_key']}")
            
            if unique:
                print(f"\n✅ Resume ที่ไม่ซ้ำกัน ({len(unique)} ไฟล์):")
                print("=" * 60)
                for name, resumes in list(unique.items())[:20]:  # Show first 20
                    resume = resumes[0]
                    print(f"\n📄 {name}")
                    print(f"   ID: {resume['id']}")
                    print(f"   Created: {resume['created_at']}")
                    print(f"   S3 Key: {resume['s3_key']}")
                
                if len(unique) > 20:
                    print(f"\n... และอีก {len(unique) - 20} ไฟล์")
            
            # Summary
            print("\n" + "=" * 60)
            print("สรุป:")
            print(f"  - จำนวน Resume ทั้งหมด: {total_count}")
            print(f"  - จำนวนไฟล์ที่ไม่ซ้ำ: {len(name_groups)}")
            print(f"  - จำนวนไฟล์ที่ซ้ำกัน: {len(duplicates)}")
            if duplicates:
                total_duplicates = sum(len(resumes) - 1 for resumes in duplicates.values())
                print(f"  - จำนวน Resume ที่ซ้ำ (ควรลบ): {total_duplicates}")
        
        return total_count
        
    except Exception as e:
        print(f"\n[ERROR] Error counting resumes: {e}")
        import traceback
        print(traceback.format_exc())
        return 0


def main():
    """Main function"""
    print("\n" + "="*60)
    print("Resume Count Checker")
    print("="*60)
    
    # Check for skip-ssl flag
    skip_ssl = len(sys.argv) > 1 and sys.argv[1].lower() == "--skip-ssl"
    
    print(f"\nConfiguration:")
    print(f"  - USE_MOCK: {settings.USE_MOCK}")
    print(f"  - OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    if skip_ssl:
        print(f"  - Skip SSL: True (for local testing)")
    
    count = count_resumes(skip_ssl=skip_ssl)
    
    print("\n" + "="*60)
    print(f"ผลลัพธ์: พบ Resume ทั้งหมด {count} ไฟล์")
    print("="*60)


if __name__ == "__main__":
    main()

