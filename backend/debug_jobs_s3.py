"""
สคริปต์ debug เพื่อตรวจสอบปัญหา jobs จาก S3
"""
import sys
import os
import json
import requests

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Default API URL
DEFAULT_API_URL = os.getenv("API_GATEWAY_URL", "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com")

def check_s3_directly():
    """ตรวจสอบ S3 โดยตรง (ถ้ามี AWS credentials)"""
    print("=" * 60)
    print("ตรวจสอบ S3 โดยตรง")
    print("=" * 60)
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # ใช้ environment variables หรือ default
        bucket_name = os.getenv("S3_BUCKET_NAME", "resume-matching-533267343789")
        s3_prefix = os.getenv("S3_PREFIX", "resumes/")
        s3_key = f"{s3_prefix}jobs_data.json"
        
        print(f"Bucket: {bucket_name}")
        print(f"S3 Key: {s3_key}")
        print()
        
        # สร้าง S3 client
        s3_client = boto3.client('s3')
        
        try:
            # ดึง object จาก S3
            response = s3_client.get_object(
                Bucket=bucket_name,
                Key=s3_key
            )
            
            # อ่านข้อมูล
            content = response['Body'].read().decode('utf-8')
            jobs_data = json.loads(content)
            
            print(f"✅ พบ jobs_data.json ใน S3")
            print(f"   จำนวน jobs: {len(jobs_data) if isinstance(jobs_data, list) else 'N/A'}")
            print(f"   ขนาดไฟล์: {len(content)} bytes")
            
            if isinstance(jobs_data, list) and len(jobs_data) > 0:
                print(f"\nตัวอย่าง job แรก:")
                first_job = jobs_data[0]
                print(f"   - ID: {first_job.get('_id', first_job.get('id', first_job.get('job_id', 'N/A')))}")
                print(f"   - Title: {first_job.get('title', 'N/A')}")
            else:
                print("   ⚠️  jobs_data.json ว่างเปล่าหรือไม่ใช่ array")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                print(f"❌ ไม่พบไฟล์ {s3_key} ใน bucket {bucket_name}")
            elif error_code == 'AccessDenied':
                print(f"❌ ไม่มี permission อ่าน S3")
                print(f"   Error: {e}")
            else:
                print(f"❌ S3 Error: {e}")
                
    except ImportError:
        print("⚠️  boto3 ไม่พบ - ไม่สามารถตรวจสอบ S3 โดยตรงได้")
        print("   Install: pip install boto3")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_api_endpoints():
    """ตรวจสอบ API endpoints"""
    print()
    print("=" * 60)
    print("ตรวจสอบ API Endpoints")
    print("=" * 60)
    
    # Bypass SSL verification สำหรับการทดสอบ
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 1. เช็ค health
    print("\n1. Health Check:")
    try:
        response = requests.get(f"{DEFAULT_API_URL}/api/health", timeout=5, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. เช็ค jobs list
    print("\n2. Jobs List:")
    try:
        response = requests.get(f"{DEFAULT_API_URL}/api/jobs/list", timeout=10, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            jobs = data.get("jobs", [])
            print(f"   Total jobs: {total}")
            if total == 0:
                print("   ⚠️  ไม่พบ jobs")
                print("   💡 แม้ว่าจะมี jobs_data.json ใน S3 แล้ว")
                print("   💡 อาจเป็นเพราะ:")
                print("      - USE_MOCK=true ใน Lambda (ไม่อ่านจาก S3)")
                print("      - Lambda ไม่มี permission อ่าน S3")
                print("      - S3_BUCKET_NAME หรือ S3_PREFIX ไม่ตรง")
            else:
                print(f"   ✅ พบ {total} jobs")
                if jobs:
                    print(f"\n   ตัวอย่าง jobs (3 ตัวแรก):")
                    for i, job in enumerate(jobs[:3], 1):
                        print(f"      {i}. {job.get('title', 'N/A')} (ID: {job.get('job_id', 'N/A')})")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. ลอง sync จาก S3
    print("\n3. Sync from S3:")
    print("   (สำหรับ PRODUCTION mode เท่านั้น - USE_MOCK=false)")
    try:
        response = requests.post(f"{DEFAULT_API_URL}/api/jobs/sync_from_s3", timeout=30, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   Response: {response.text}")
            if response.status_code == 400:
                error_data = response.json()
                detail = error_data.get('detail', '')
                if 'USE_MOCK' in detail or 'mock' in detail.lower():
                    print("   ⚠️  Lambda ใช้ MOCK mode - ต้องตั้ง USE_MOCK=false")
    except Exception as e:
        print(f"   Error: {e}")

def check_lambda_config():
    """ตรวจสอบ Lambda configuration (ถ้าเข้าถึงได้)"""
    print()
    print("=" * 60)
    print("ตรวจสอบ Lambda Configuration")
    print("=" * 60)
    print("\n💡 ตรวจสอบใน AWS Console:")
    print("   1. Lambda Function → Configuration → Environment variables")
    print("      - USE_MOCK: ควรเป็น 'false' สำหรับ production")
    print("      - S3_BUCKET_NAME: ควรเป็น 'resume-matching-533267343789'")
    print("      - S3_PREFIX: ควรเป็น 'resumes/'")
    print()
    print("   2. Lambda Function → Configuration → Permissions")
    print("      - ตรวจสอบว่า Lambda execution role มี permission อ่าน S3")
    print("      - ต้องมี policy: s3:GetObject สำหรับ bucket resume-matching-533267343789")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("Debug Jobs from S3")
    print("=" * 60)
    print(f"API URL: {DEFAULT_API_URL}")
    print()
    
    # ตรวจสอบ S3 โดยตรง
    check_s3_directly()
    
    # ตรวจสอบ API endpoints
    check_api_endpoints()
    
    # ตรวจสอบ Lambda config
    check_lambda_config()
    
    print()
    print("=" * 60)
    print("สรุป")
    print("=" * 60)
    print("ปัญหาที่เป็นไปได้:")
    print("1. USE_MOCK=true → Lambda ไม่อ่านจาก S3 จริง (อ่านจาก local file แทน)")
    print("2. Lambda ไม่มี permission อ่าน S3")
    print("3. S3_BUCKET_NAME หรือ S3_PREFIX ไม่ตรง")
    print("4. jobs_data.json ว่างเปล่าหรือ format ไม่ถูกต้อง")
    print("=" * 60)

