"""
Server Diagnostic Script
ตรวจสอบปัญหาที่อาจทำให้เซิร์ฟเวอร์ไม่ทำงาน
"""
import sys
import os
from pathlib import Path

def check_imports():
    """ตรวจสอบว่า import modules สำเร็จหรือไม่"""
    print("=" * 60)
    print("1. ตรวจสอบ Imports")
    print("=" * 60)
    
    issues = []
    
    try:
        import fastapi
        print("[OK] fastapi")
    except ImportError as e:
        print(f"[ERROR] fastapi: {e}")
        issues.append("fastapi")
    
    try:
        import uvicorn
        print("[OK] uvicorn")
    except ImportError as e:
        print(f"[ERROR] uvicorn: {e}")
        issues.append("uvicorn")
    
    try:
        import mangum
        print("[OK] mangum")
    except ImportError as e:
        print(f"[ERROR] mangum: {e}")
        issues.append("mangum")
    
    try:
        import boto3
        print("[OK] boto3")
    except ImportError as e:
        print(f"[ERROR] boto3: {e}")
        issues.append("boto3")
    
    try:
        import opensearchpy
        print("[OK] opensearch-py")
    except ImportError as e:
        print(f"[ERROR] opensearch-py: {e}")
        issues.append("opensearch-py")
    
    try:
        from app.core.config import settings
        print("[OK] app.core.config")
    except Exception as e:
        print(f"[ERROR] app.core.config: {e}")
        issues.append("config")
    
    try:
        from main import app
        print("[OK] main.py (FastAPI app)")
    except Exception as e:
        print(f"[ERROR] main.py: {e}")
        print(f"   Error details: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        issues.append("main")
    
    return issues


def check_environment():
    """ตรวจสอบ environment variables"""
    print("\n" + "=" * 60)
    print("2. ตรวจสอบ Environment Variables")
    print("=" * 60)
    
    env_path = Path(__file__).parent.parent / 'infra' / '.env'
    if env_path.exists():
        print(f"[OK] Found .env file: {env_path}")
    else:
        print(f"[WARN] No .env file found at: {env_path}")
        print("   Using default values from config.py")
    
    # Check important env vars
    use_mock = os.getenv("USE_MOCK", "false").lower() == "true"
    print(f"   USE_MOCK: {use_mock}")
    
    if not use_mock:
        print("\n   Production mode - checking AWS config:")
        print(f"   AWS_REGION: {os.getenv('AWS_REGION', 'ap-southeast-1')}")
        print(f"   AWS_ACCESS_KEY_ID: {'[OK] Set' if os.getenv('AWS_ACCESS_KEY_ID') else '[ERROR] Not set'}")
        print(f"   AWS_SECRET_ACCESS_KEY: {'[OK] Set' if os.getenv('AWS_SECRET_ACCESS_KEY') else '[ERROR] Not set'}")
        print(f"   S3_BUCKET_NAME: {os.getenv('S3_BUCKET_NAME', 'resume-matching-bucket')}")
        print(f"   OPENSEARCH_ENDPOINT: {os.getenv('OPENSEARCH_ENDPOINT', 'Not set')}")


def check_config():
    """ตรวจสอบ configuration"""
    print("\n" + "=" * 60)
    print("3. ตรวจสอบ Configuration")
    print("=" * 60)
    
    try:
        # Force reload config module to ensure .env is loaded fresh
        import sys
        if 'app.core.config' in sys.modules:
            del sys.modules['app.core.config']
        
        from app.core.config import settings
        print(f"[OK] Settings loaded")
        print(f"   USE_MOCK: {settings.USE_MOCK}")
        print(f"   AWS_REGION: {settings.AWS_REGION}")
        print(f"   S3_BUCKET_NAME: {settings.S3_BUCKET_NAME}")
        print(f"   OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
        
        # Check for config mismatch
        env_region = os.getenv("AWS_REGION", "")
        env_opensearch = os.getenv("OPENSEARCH_ENDPOINT", "")
        
        if env_region and settings.AWS_REGION != env_region:
            print(f"\n[WARN] Config mismatch detected!")
            print(f"   Environment AWS_REGION: {env_region}")
            print(f"   Settings AWS_REGION: {settings.AWS_REGION}")
            print(f"   -> .env file อาจไม่ถูกโหลดถูกต้อง")
        
        if env_opensearch and settings.OPENSEARCH_ENDPOINT != env_opensearch:
            print(f"\n[WARN] Config mismatch detected!")
            print(f"   Environment OPENSEARCH_ENDPOINT: {env_opensearch}")
            print(f"   Settings OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
            print(f"   -> .env file อาจไม่ถูกโหลดถูกต้อง")
            
    except Exception as e:
        print(f"[ERROR] Failed to load settings: {e}")
        import traceback
        traceback.print_exc()


def check_clients():
    """ตรวจสอบ clients initialization"""
    print("\n" + "=" * 60)
    print("4. ตรวจสอบ Clients")
    print("=" * 60)
    
    try:
        from app.clients.s3_client import s3_client
        print("[OK] S3Client initialized")
    except Exception as e:
        print(f"[ERROR] S3Client: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        from app.clients.opensearch_client import opensearch_client
        print("[OK] OpenSearchClient initialized")
    except Exception as e:
        print(f"[ERROR] OpenSearchClient: {e}")
        import traceback
        traceback.print_exc()


def check_lambda_handler():
    """ตรวจสอบ Lambda handler"""
    print("\n" + "=" * 60)
    print("5. ตรวจสอบ Lambda Handler")
    print("=" * 60)
    
    try:
        from lambda_function import handler
        print("[OK] Lambda handler imported successfully")
    except Exception as e:
        print(f"[ERROR] Lambda handler: {e}")
        import traceback
        traceback.print_exc()


def check_forbidden_files():
    """ตรวจสอบไฟล์ต้องห้ามที่อาจทำให้ Lambda error"""
    print("\n" + "=" * 60)
    print("6. ตรวจสอบไฟล์ต้องห้าม")
    print("=" * 60)
    
    forbidden = ["typing.py", "http.py", "json.py", "asyncio.py", "email.py"]
    found = []
    
    backend_dir = Path(__file__).parent
    for file in forbidden:
        file_path = backend_dir / file
        if file_path.exists():
            found.append(file)
            print(f"[ERROR] Found forbidden file: {file}")
    
    if not found:
        print("[OK] No forbidden files found at root level")
    else:
        print("\n[WARN] These files can cause Lambda import errors!")
        print("   They conflict with Python stdlib modules.")


def main():
    """Run all diagnostics"""
    print("\n" + "=" * 60)
    print("Server Diagnostic Tool")
    print("=" * 60)
    print()
    
    # Add backend to path
    backend_dir = Path(__file__).parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    issues = []
    
    # Run checks
    import_issues = check_imports()
    issues.extend(import_issues)
    
    check_environment()
    check_config()
    check_clients()
    check_lambda_handler()
    check_forbidden_files()
    
    # Summary
    print("\n" + "=" * 60)
    print("สรุปผลการตรวจสอบ")
    print("=" * 60)
    
    if not issues:
        print("[OK] ไม่พบปัญหาหลัก - เซิร์ฟเวอร์ควรทำงานได้")
        print("\n[INFO] ถ้ายังใช้งานไม่ได้ ลอง:")
        print("   1. ตรวจสอบ CloudWatch Logs (ถ้าใช้ Lambda)")
        print("   2. ตรวจสอบว่า server กำลังรันอยู่: python main.py")
        print("   3. ตรวจสอบ network/firewall")
        print("   4. ตรวจสอบ AWS credentials และ permissions")
    else:
        print(f"[ERROR] พบปัญหา {len(issues)} ข้อ:")
        for issue in set(issues):
            print(f"   - {issue}")
        print("\n[INFO] แก้ไข:")
        if "fastapi" in issues or "uvicorn" in issues or "mangum" in issues:
            print("   1. ติดตั้ง dependencies: pip install -r requirements.txt")
        if "main" in issues or "config" in issues:
            print("   2. ตรวจสอบ error message ด้านบน")
        if "boto3" in issues:
            print("   3. ติดตั้ง boto3: pip install boto3")
    
    print()


if __name__ == "__main__":
    main()

