"""
ตรวจสอบว่า OpenSearch indices อ่านได้หรือไม่
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.clients.opensearch_client import opensearch_client
from app.core.logging import get_logger

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
            "reset": "\033[0m"
        }.get(color, "")
        sys.stdout.buffer.write(f"{color_code}{message}\033[0m\n".encode('utf-8'))
    else:
        sys.stdout.buffer.write(f"{message}\n".encode('utf-8'))

def check_index(index_name: str):
    """ตรวจสอบ index ว่ามีอยู่และอ่านได้หรือไม่"""
    print_thai(f"\n{'='*60}", "cyan")
    print_thai(f"ตรวจสอบ Index: {index_name}", "cyan")
    print_thai(f"{'='*60}", "cyan")
    
    if settings.USE_MOCK:
        print_thai(f"   [INFO] กำลังใช้ MOCK mode", "yellow")
        mock_data = opensearch_client._mock_data_storage.get(index_name, [])
        count = len(mock_data)
        print_thai(f"   [OK] พบ {count} documents ใน mock storage", "green")
        if count > 0:
            print_thai(f"   [SAMPLE] ตัวอย่าง document แรก:", "white")
            print(f"      {mock_data[0]}")
        return count > 0
    
    try:
        # ตรวจสอบว่า index มีอยู่หรือไม่
        if not opensearch_client.client:
            print_thai(f"   [ERROR] OpenSearch client ไม่ได้ถูกสร้าง", "red")
            return False
        
        exists = opensearch_client.client.indices.exists(index=index_name)
        
        if not exists:
            print_thai(f"   [WARNING] Index '{index_name}' ยังไม่มี", "yellow")
            print_thai(f"   [TIP] ต้องสร้าง index ก่อน (ใช้ sync_from_s3 หรือ create_job)", "yellow")
            return False
        
        print_thai(f"   [OK] Index '{index_name}' มีอยู่", "green")
        
        # นับจำนวน documents
        try:
            count_result = opensearch_client.client.count(index=index_name)
            count = count_result.get('count', 0)
            print_thai(f"   [OK] พบ {count} documents", "green")
            
            if count == 0:
                print_thai(f"   [WARNING] Index ว่างเปล่า - ยังไม่มีข้อมูล", "yellow")
                return False
            
            # ลองอ่านข้อมูลตัวอย่าง (1 document)
            try:
                search_result = opensearch_client.client.search(
                    index=index_name,
                    body={
                        "size": 1,
                        "query": {"match_all": {}}
                    }
                )
                
                hits = search_result.get('hits', {}).get('hits', [])
                if hits:
                    doc = hits[0]
                    print_thai(f"   [OK] อ่าน document ได้สำเร็จ", "green")
                    print_thai(f"   [SAMPLE] Document ID: {doc.get('_id', 'N/A')}", "white")
                    source = doc.get('_source', {})
                    if 'title' in source:
                        print_thai(f"   [SAMPLE] Title: {source.get('title', 'N/A')}", "white")
                    elif 'text' in source:
                        text_preview = source.get('text', '')[:100]
                        print_thai(f"   [SAMPLE] Text: {text_preview}...", "white")
                else:
                    print_thai(f"   [WARNING] ไม่พบ documents ในผลลัพธ์", "yellow")
                
            except Exception as read_error:
                print_thai(f"   [ERROR] ไม่สามารถอ่าน document ได้: {read_error}", "red")
                return False
            
            return True
            
        except Exception as count_error:
            print_thai(f"   [ERROR] ไม่สามารถนับ documents ได้: {count_error}", "red")
            return False
            
    except Exception as e:
        print_thai(f"   [ERROR] เกิดข้อผิดพลาด: {e}", "red")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_thai("\n" + "="*60, "cyan")
    print_thai("ตรวจสอบ OpenSearch Indices", "cyan")
    print_thai("="*60, "cyan")
    print_thai(f"\nOpenSearch Endpoint: {settings.OPENSEARCH_ENDPOINT}", "white")
    print_thai(f"USE_MOCK: {settings.USE_MOCK}", "white")
    print_thai(f"AWS Region: {settings.AWS_REGION}", "white")
    
    # ตรวจสอบ jobs_index
    jobs_ok = check_index("jobs_index")
    
    # ตรวจสอบ resumes_index
    resumes_ok = check_index("resumes_index")
    
    # สรุปผล
    print_thai(f"\n{'='*60}", "cyan")
    print_thai("สรุปผลการตรวจสอบ", "cyan")
    print_thai(f"{'='*60}", "cyan")
    
    if jobs_ok:
        print_thai("   ✅ jobs_index: อ่านได้", "green")
    else:
        print_thai("   ❌ jobs_index: อ่านไม่ได้ หรือยังไม่มีข้อมูล", "red")
    
    if resumes_ok:
        print_thai("   ✅ resumes_index: อ่านได้", "green")
    else:
        print_thai("   ❌ resumes_index: อ่านไม่ได้ หรือยังไม่มีข้อมูล", "red")
    
    print_thai("", "reset")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_thai("\n\n[WARNING] ยกเลิกการตรวจสอบ", "yellow")
        sys.exit(1)
    except Exception as e:
        print_thai(f"\n\n[ERROR] เกิดข้อผิดพลาด: {e}", "red")
        import traceback
        traceback.print_exc()
        sys.exit(1)
