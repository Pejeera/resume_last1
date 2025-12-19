"""
ทดสอบ OpenSearch ผ่าน Lambda API
"""
import requests
import json
import sys
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://k9z3rlu1ui.execute-api.us-east-1.amazonaws.com/prod"

def test_opensearch_sync():
    """Test OpenSearch sync from S3"""
    print("=" * 60)
    print("ทดสอบ OpenSearch Sync จาก S3")
    print("=" * 60)
    print()
    
    url = f"{API_BASE_URL}/api/jobs/sync_from_s3"
    
    print(f"[1/2] เรียก API: {url}")
    print()
    
    try:
        response = requests.post(url, timeout=60, verify=False)
        
        print(f"   Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("   [SUCCESS] Sync สำเร็จ!")
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            error_data = response.json() if response.content else {}
            print(f"   [ERROR] Sync ล้มเหลว")
            print(f"   Response: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            
            error_detail = error_data.get("detail", "")
            if "AuthenticationException" in error_detail or "401" in error_detail:
                print()
                print("   [DIAGNOSIS] ปัญหา Authentication:")
                print("      - ตรวจสอบ OPENSEARCH_USERNAME และ OPENSEARCH_PASSWORD")
                print("      - ตรวจสอบว่า credentials ถูกต้อง")
                print("      - ตรวจสอบว่า OpenSearch domain มี fine-grained access control")
            elif "Connection" in error_detail or "timeout" in error_detail.lower():
                print()
                print("   [DIAGNOSIS] ปัญหา Connection:")
                print("      - ตรวจสอบว่า Lambda สามารถเข้าถึง OpenSearch ได้")
                print("      - ตรวจสอบ VPC configuration (ถ้า OpenSearch อยู่ใน VPC)")
                print("      - ตรวจสอบ security groups และ network ACLs")
            
            return False
            
    except requests.exceptions.Timeout:
        print("   [ERROR] Request timeout (เกิน 60 วินาที)")
        print("   [TIP] ตรวจสอบ Lambda timeout settings")
        return False
    except Exception as e:
        print(f"   [ERROR] เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_jobs_list():
    """Test jobs list (uses OpenSearch if available)"""
    print()
    print("=" * 60)
    print("ทดสอบ Jobs List (ตรวจสอบว่า OpenSearch ทำงาน)")
    print("=" * 60)
    print()
    
    url = f"{API_BASE_URL}/api/jobs/list"
    
    print(f"[1/2] เรียก API: {url}")
    print()
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        
        print(f"   Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])
            print(f"   [SUCCESS] พบ {len(jobs)} jobs")
            
            if len(jobs) > 0:
                print()
                print("   ตัวอย่าง jobs (3 ตัวแรก):")
                for i, job in enumerate(jobs[:3], 1):
                    title = job.get("title", "N/A")
                    job_id = job.get("id", "N/A")
                    print(f"      {i}. {title} (ID: {job_id})")
            
            return True
        else:
            error_data = response.json() if response.content else {}
            print(f"   [ERROR] ไม่สามารถดึง jobs ได้")
            print(f"   Response: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            return False
            
    except Exception as e:
        print(f"   [ERROR] เกิดข้อผิดพลาด: {e}")
        return False

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("ทดสอบ OpenSearch ผ่าน Lambda API")
    print("=" * 60)
    print()
    
    # Test 1: Jobs List (should work)
    jobs_ok = test_jobs_list()
    
    # Test 2: Sync from S3 (tests OpenSearch connection)
    sync_ok = test_opensearch_sync()
    
    # Summary
    print()
    print("=" * 60)
    print("สรุปผลการทดสอบ")
    print("=" * 60)
    print()
    
    if jobs_ok:
        print("   [OK] Jobs List ทำงานได้")
    else:
        print("   [FAIL] Jobs List ไม่ทำงาน")
    
    if sync_ok:
        print("   [OK] OpenSearch Sync ทำงานได้")
        print()
        print("   ✅ OpenSearch พร้อมใช้งาน!")
    else:
        print("   [FAIL] OpenSearch Sync ไม่ทำงาน")
        print()
        print("   [WARNING] OpenSearch ยังมีปัญหา")
        print()
        print("   วิธีแก้ไข:")
        print("   1. ตรวจสอบ OpenSearch credentials:")
        print("      .\\update_opensearch_credentials.ps1 \\")
        print("        -OpenSearchEndpoint 'your-endpoint' \\")
        print("        -OpenSearchUsername 'your-username' \\")
        print("        -OpenSearchPassword 'your-password'")
        print()
        print("   2. ตรวจสอบ Lambda VPC configuration:")
        print("      .\\check_opensearch_access.ps1")
        print()
        print("   3. ตรวจสอบ CloudWatch Logs สำหรับรายละเอียด")
    
    print("=" * 60)
    print()
    
    sys.exit(0 if (jobs_ok and sync_ok) else 1)

