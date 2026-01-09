"""
Test getting resume by s3_key directly
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
from app.repositories.resume_repository import resume_repository
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_resume_by_key():
    """Test getting resume by s3_key"""
    print("=" * 70)
    print("  Test Resume by S3 Key")
    print("=" * 70)
    print()
    
    # Test with the exact s3_key from the error
    s3_key = "resumes/Candidate/test_resume.txt"
    resume_id = "493dc0bf-2855-4b61-9a94-26b468e917cd"
    
    print(f"Testing with:")
    print(f"  s3_key: {s3_key}")
    print(f"  resume_id: {resume_id}")
    print()
    
    # Test 1: Get by s3_key
    print("Test 1: Get resume by s3_key")
    print("-" * 70)
    try:
        resume = resume_repository.get_resume_from_s3_by_key(s3_key)
        if resume:
            print(f"[OK] Found resume by s3_key")
            print(f"  Resume ID: {resume.get('id', 'N/A')}")
            print(f"  Name: {resume.get('name', 'N/A')}")
            print(f"  S3 Key: {resume.get('s3_key', 'N/A')}")
            print(f"  Text length: {len(resume.get('full_text', ''))}")
            print(f"  Has embeddings: {bool(resume.get('embeddings'))}")
        else:
            print(f"[FAIL] Resume not found by s3_key")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 2: Get by resume_id
    print("Test 2: Get resume by resume_id")
    print("-" * 70)
    try:
        resume = resume_repository.get_resume(resume_id)
        if resume:
            print(f"[OK] Found resume by resume_id")
            print(f"  Resume ID: {resume.get('id', 'N/A')}")
            print(f"  Name: {resume.get('name', 'N/A')}")
            print(f"  S3 Key: {resume.get('s3_key', 'N/A')}")
        else:
            print(f"[FAIL] Resume not found by resume_id")
            print("  Trying get_resume_from_s3...")
            resume = resume_repository.get_resume_from_s3(resume_id)
            if resume:
                print(f"[OK] Found resume from S3")
            else:
                print(f"[FAIL] Resume not found in S3 either")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 3: Check S3 file directly
    print("Test 3: Check S3 file directly")
    print("-" * 70)
    try:
        from app.clients.s3_client import s3_client
        import boto3
        
        if hasattr(s3_client, 'client') and s3_client.client:
            s3_client_boto = s3_client.client
        else:
            s3_client_boto = boto3.client('s3', region_name=settings.AWS_REGION)
        
        # Check if file exists
        try:
            response = s3_client_boto.head_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            print(f"[OK] File exists in S3")
            print(f"  Size: {response.get('ContentLength', 0)} bytes")
            print(f"  ContentType: {response.get('ContentType', 'N/A')}")
            metadata = response.get('Metadata', {})
            if metadata:
                print(f"  Metadata: {metadata}")
            
            # Try to read file
            file_obj = s3_client_boto.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            file_content = file_obj['Body'].read()
            print(f"  File content length: {len(file_content)} bytes")
            if len(file_content) < 200:
                print(f"  Content preview: {file_content.decode('utf-8', errors='ignore')[:100]}")
            
        except Exception as e:
            print(f"[FAIL] File check failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
    print()

if __name__ == "__main__":
    test_resume_by_key()

