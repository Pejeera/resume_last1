"""
สคริปต์ทดสอบ API บนเซิร์ฟเวอร์ (Lambda + API Gateway)
ตรวจสอบว่า API ใช้งานได้หรือไม่
"""
import sys
import os
import json
import requests
import urllib3
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Bypass SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API Gateway URL
API_URL = "https://k9z3rlu1ui.execute-api.us-east-1.amazonaws.com/prod"

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_test(test_num, total, name):
    """Print test header"""
    print(f"\n[{test_num}/{total}] {name}")
    print("-" * 70)

def test_endpoint(method, endpoint, data=None, description=""):
    """Test an API endpoint"""
    url = f"{API_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10, verify=False)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30, verify=False)
        else:
            return False, f"Unsupported method: {method}"
        
        status_ok = 200 <= response.status_code < 300
        
        if status_ok:
            try:
                result = response.json()
                return True, result
            except:
                return True, response.text
        else:
            return False, f"Status {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection error - API might be down"
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print_header("🔍 ตรวจสอบ API บนเซิร์ฟเวอร์")
    print(f"API URL: {API_URL}")
    print(f"เวลา: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: Root endpoint
    print_test(1, 6, "Root Endpoint (/)")
    success, result = test_endpoint("GET", "/")
    if success:
        print(f"✅ ผ่าน - API ทำงานได้")
        print(f"   Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        results.append(("Root", True))
    else:
        print(f"❌ ล้มเหลว - {result}")
        results.append(("Root", False))
    
    # Test 2: Health check
    print_test(2, 6, "Health Check (/api/health)")
    success, result = test_endpoint("GET", "/api/health")
    if success:
        print(f"✅ ผ่าน - Health check สำเร็จ")
        print(f"   Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        results.append(("Health", True))
    else:
        print(f"❌ ล้มเหลว - {result}")
        results.append(("Health", False))
    
    # Test 3: Jobs List
    print_test(3, 6, "Jobs List (/api/jobs/list)")
    success, result = test_endpoint("GET", "/api/jobs/list")
    if success:
        total = result.get("total", 0)
        jobs = result.get("jobs", [])
        print(f"✅ ผ่าน - พบ {total} jobs")
        if total > 0:
            print(f"\n   ตัวอย่าง jobs (3 ตัวแรก):")
            for i, job in enumerate(jobs[:3], 1):
                title = job.get('title', 'N/A')
                job_id = job.get('job_id', 'N/A')
                print(f"      {i}. {title} (ID: {job_id})")
        else:
            print(f"   ⚠️  ไม่พบ jobs ในระบบ")
        results.append(("Jobs List", True))
    else:
        print(f"❌ ล้มเหลว - {result}")
        results.append(("Jobs List", False))
    
    # Test 4: Create Job (test endpoint)
    print_test(4, 6, "Create Job (/api/jobs/create)")
    test_job_data = {
        "title": f"Test Job - {datetime.now().strftime('%Y%m%d%H%M%S')}",
        "description": "This is a test job created by API test script",
        "metadata": {"test": True}
    }
    success, result = test_endpoint("POST", "/api/jobs/create", test_job_data)
    if success:
        job_id = result.get("job_id", "N/A")
        print(f"✅ ผ่าน - สร้าง job สำเร็จ")
        print(f"   Job ID: {job_id}")
        print(f"   Title: {result.get('title', 'N/A')}")
        results.append(("Create Job", True))
    else:
        print(f"❌ ล้มเหลว - {result}")
        results.append(("Create Job", False))
    
    # Test 5: Sync from S3
    print_test(5, 6, "Sync from S3 (/api/jobs/sync_from_s3)")
    print("   (สำหรับ PRODUCTION mode - USE_MOCK=false)")
    success, result = test_endpoint("POST", "/api/jobs/sync_from_s3")
    if success:
        synced = result.get("synced", 0)
        skipped = result.get("skipped", 0)
        total = result.get("total", 0)
        print(f"✅ ผ่าน - Sync สำเร็จ")
        print(f"   Synced: {synced}, Skipped: {skipped}, Total: {total}")
        results.append(("Sync S3", True))
    else:
        # This might fail if USE_MOCK=true, which is expected
        if "USE_MOCK" in str(result) or "mock" in str(result).lower():
            print(f"⚠️  ข้าม - อยู่ใน Mock mode (ไม่รองรับ sync)")
        else:
            print(f"❌ ล้มเหลว - {result}")
        results.append(("Sync S3", False))
    
    # Test 6: Resumes endpoints (if available)
    print_test(6, 6, "Resumes Endpoints")
    # Try to get resume list or check if endpoint exists
    success, result = test_endpoint("GET", "/api/resumes")
    if success:
        print(f"✅ ผ่าน - Resumes endpoint ทำงานได้")
        results.append(("Resumes", True))
    else:
        # This endpoint might not exist or require auth
        if "404" in str(result) or "Not Found" in str(result):
            print(f"⚠️  Endpoint ไม่มีหรือต้อง authentication")
        else:
            print(f"❌ ล้มเหลว - {result}")
        results.append(("Resumes", False))
    
    # Summary
    print_header("📊 สรุปผลการทดสอบ")
    passed = sum(1 for _, success in results if success)
    total_tests = len(results)
    
    for name, success in results:
        status = "✅ ผ่าน" if success else "❌ ล้มเหลว"
        print(f"   {status} - {name}")
    
    print(f"\nผลรวม: {passed}/{total_tests} tests ผ่าน")
    
    if passed == total_tests:
        print("\n🎉 API ใช้งานได้ทั้งหมด!")
    elif passed > 0:
        print(f"\n⚠️  API ใช้งานได้บางส่วน ({passed}/{total_tests})")
        print("   ตรวจสอบ endpoints ที่ล้มเหลว")
    else:
        print("\n❌ API ไม่สามารถใช้งานได้")
        print("   ตรวจสอบ:")
        print("   1. Lambda function ทำงานหรือไม่")
        print("   2. API Gateway configuration")
        print("   3. CloudWatch Logs สำหรับ error details")
    
    print("\n" + "=" * 70)
    print("💡 Tips:")
    print("   - ตรวจสอบ Lambda CloudWatch Logs สำหรับรายละเอียด")
    print("   - ตรวจสอบ API Gateway configuration")
    print("   - ตรวจสอบ Lambda environment variables")
    print("=" * 70)

if __name__ == "__main__":
    main()

