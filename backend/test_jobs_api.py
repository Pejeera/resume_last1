"""
ทดสอบ API endpoint สำหรับดึงรายการ jobs
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
API_URL = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def test_jobs_list():
    """Test /api/jobs/list endpoint"""
    print_header("ทดสอบ API: GET /api/jobs/list")
    print(f"API URL: {API_URL}")
    print(f"เวลา: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    url = f"{API_URL}/api/jobs/list"
    
    print(f"Request URL: {url}")
    print("กำลังส่ง request...")
    print()
    
    try:
        # เพิ่ม timeout เป็น 60 วินาที
        response = requests.get(url, timeout=60, verify=False)
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            try:
                data = response.json()
                total = data.get("total", 0)
                jobs = data.get("jobs", [])
                
                print("✅ สำเร็จ!")
                print(f"Total jobs: {total}")
                print()
                
                if total > 0:
                    print(f"พบ {total} jobs:")
                    print("-" * 70)
                    
                    # แสดง 5 jobs แรก
                    for i, job in enumerate(jobs[:5], 1):
                        job_id = job.get('job_id', 'N/A')
                        title = job.get('title', 'N/A')
                        description = job.get('description', 'N/A')
                        created_at = job.get('created_at', 'N/A')
                        
                        print(f"\n[{i}] Job ID: {job_id}")
                        print(f"    Title: {title}")
                        print(f"    Description: {description[:100]}..." if len(description) > 100 else f"    Description: {description}")
                        print(f"    Created At: {created_at}")
                    
                    if total > 5:
                        print(f"\n... และอีก {total - 5} jobs")
                    
                    print()
                    print("=" * 70)
                    print("✅ API ใช้งานได้ปกติ!")
                    print("=" * 70)
                else:
                    print("⚠️  ไม่พบ jobs ในระบบ")
                    print()
                    print("Response data:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    
            except json.JSONDecodeError:
                print("❌ ไม่สามารถ parse JSON response ได้")
                print(f"Response text: {response.text[:500]}")
        else:
            print(f"❌ Error Status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timeout (เกิน 60 วินาที)")
        print("   อาจเป็นเพราะ:")
        print("   - Lambda cold start")
        print("   - OpenSearch connection timeout")
        print("   - Network issues")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - API Gateway อาจไม่สามารถเข้าถึงได้")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jobs_list()

