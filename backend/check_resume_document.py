"""
Script to check resume document in OpenSearch
"""
import sys
import json
import io
import urllib3
from app.core.config import settings
from app.core.logging import get_logger

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import after disabling warnings
from opensearchpy import OpenSearch, RequestsHttpConnection
import boto3
from requests_aws4auth import AWS4Auth

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = get_logger(__name__)

def check_resume_document(resume_id: str):
    """Check resume document in OpenSearch"""
    print("\n" + "="*60)
    print(f"ตรวจสอบ Resume Document ใน OpenSearch")
    print("="*60)
    print(f"Resume ID: {resume_id}")
    print(f"Index: resumes_index")
    print("")
    
    if settings.USE_MOCK:
        print("[WARNING] อยู่ในโหมด MOCK")
        return
    
    try:
        # Create OpenSearch client with SSL verification disabled for testing
        endpoint = settings.OPENSEARCH_ENDPOINT
        host = endpoint.replace('https://', '').replace('http://', '')
        if ':' in host:
            host, _ = host.rsplit(':', 1)
        
        # Extract region from endpoint
        opensearch_region = settings.AWS_REGION
        if '.es.amazonaws.com' in host:
            parts = host.split('.')
            for part in parts:
                if part.startswith('ap-') or part.startswith('us-') or part.startswith('eu-'):
                    opensearch_region = part
                    break
        
        credentials = boto3.Session().get_credentials()
        if not credentials:
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                awsauth = AWS4Auth(
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY,
                    opensearch_region,
                    'es'
                )
            else:
                print("[ERROR] No AWS credentials found")
                return
        else:
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                opensearch_region,
                'es',
                session_token=credentials.token
            )
        
        # Create client with SSL verification disabled for testing
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=False,  # Disable SSL verification for testing
            connection_class=RequestsHttpConnection
        )
        
        # Get document from OpenSearch
        try:
            response = client.get(index="resumes_index", id=resume_id)
            document = response['_source']
        except Exception as e:
            print(f"[ERROR] ไม่พบ document: {e}")
            return
        
        if not document:
            print("[ERROR] ไม่พบ document ใน OpenSearch")
            return
        
        print("[OK] พบ document ใน OpenSearch")
        print("")
        print("="*60)
        print("โครงสร้าง Document:")
        print("="*60)
        
        # Check basic fields
        print(f"\n📄 Basic Fields:")
        print(f"  - id: {document.get('id', 'N/A')}")
        print(f"  - name: {document.get('name', 'N/A')}")
        print(f"  - s3_url: {document.get('s3_url', 'N/A')}")
        print(f"  - s3_key: {document.get('s3_key', 'N/A')}")
        print(f"  - created_at: {document.get('created_at', 'N/A')}")
        
        # Check embeddings
        print(f"\n🔢 Embeddings:")
        embeddings = document.get('embeddings')
        if embeddings:
            print(f"  ✅ Overall embeddings: {len(embeddings)} dimensions")
        else:
            print(f"  ❌ Overall embeddings: ไม่พบ")
        
        # Check category_embeddings
        print(f"\n🔢 Category Embeddings:")
        category_embeddings = document.get('category_embeddings', {})
        if category_embeddings:
            print(f"  ✅ พบ category_embeddings:")
            for category, embedding in category_embeddings.items():
                if isinstance(embedding, list):
                    print(f"    - {category}: {len(embedding)} dimensions")
                else:
                    print(f"    - {category}: {type(embedding).__name__}")
        else:
            print(f"  ❌ category_embeddings: ไม่พบ")
        
        # Check categories
        print(f"\n📋 Categories:")
        categories = document.get('categories', {})
        if categories:
            print(f"  ✅ พบ categories:")
            for category, data in categories.items():
                if isinstance(data, dict):
                    if data:
                        print(f"    - {category}: {len(data)} fields")
                    else:
                        print(f"    - {category}: empty dict")
                elif isinstance(data, list):
                    print(f"    - {category}: {len(data)} items")
                elif isinstance(data, str):
                    print(f"    - {category}: {len(data)} chars")
                else:
                    print(f"    - {category}: {type(data).__name__}")
        else:
            print(f"  ❌ categories: ไม่พบ")
        
        # Check structured_text
        print(f"\n📝 Structured Text:")
        structured_text = document.get('structured_text')
        if structured_text:
            print(f"  ✅ structured_text: {len(structured_text)} characters")
        else:
            print(f"  ❌ structured_text: ไม่พบ")
        
        # Check full_text
        print(f"\n📄 Full Text:")
        full_text = document.get('full_text')
        if full_text:
            print(f"  ✅ full_text: {len(full_text)} characters")
        else:
            print(f"  ❌ full_text: ไม่พบ")
        
        # Summary
        print("\n" + "="*60)
        print("สรุปผล:")
        print("="*60)
        
        has_overall_embedding = bool(embeddings)
        has_category_embeddings = bool(category_embeddings)
        has_categories = bool(categories)
        
        print(f"  Overall embedding: {'✅' if has_overall_embedding else '❌'}")
        print(f"  Category embeddings: {'✅' if has_category_embeddings else '❌'}")
        print(f"  Categories: {'✅' if has_categories else '❌'}")
        
        if has_overall_embedding and has_category_embeddings and has_categories:
            print("\n  ✅ [OK] Document ถูกเก็บครบถ้วน!")
        else:
            print("\n  ⚠️  [WARNING] Document อาจไม่ครบถ้วน")
        
        # Show full document (optional)
        print("\n" + "="*60)
        print("Full Document (JSON):")
        print("="*60)
        print(json.dumps(document, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    resume_id = sys.argv[1] if len(sys.argv) > 1 else "1675c4bc-1fe7-46c3-963b-d4cd8a118c6a"
    check_resume_document(resume_id)

