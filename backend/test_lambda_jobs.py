"""
ทดสอบ Lambda jobs/list endpoint โดยตรง
"""
import sys
import os
import json
import requests
import urllib3

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Bypass SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://k9z3rlu1ui.execute-api.us-east-1.amazonaws.com/prod"

print("=" * 60)
print("ทดสอบ Lambda Jobs List Endpoint")
print("=" * 60)
print(f"API URL: {API_URL}")
print()

# Test 1: Health check
print("[1/3] Health Check:")
try:
    response = requests.get(f"{API_URL}/api/health", timeout=5, verify=False)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ API ทำงานได้")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Jobs List
print("[2/3] Jobs List:")
try:
    response = requests.get(f"{API_URL}/api/jobs/list", timeout=10, verify=False)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        total = data.get("total", 0)
        jobs = data.get("jobs", [])
        
        print(f"   Total: {total}")
        
        if total > 0:
            print(f"   ✅ พบ {total} jobs!")
            print(f"\n   ตัวอย่าง jobs (3 ตัวแรก):")
            for i, job in enumerate(jobs[:3], 1):
                print(f"      {i}. {job.get('title', 'N/A')} (ID: {job.get('job_id', 'N/A')})")
        else:
            print(f"   ⚠️  ไม่พบ jobs")
            print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"   ❌ Error Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Sync from S3
print("[3/3] Sync from S3:")
print("   (สำหรับ PRODUCTION mode - USE_MOCK=false)")
try:
    response = requests.post(f"{API_URL}/api/jobs/sync_from_s3", timeout=30, verify=False)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Response:")
        print(f"   {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        synced = data.get("synced", 0)
        if synced > 0:
            print(f"\n   ✅ Sync สำเร็จ: {synced} jobs")
        else:
            print(f"\n   ⚠️  ไม่พบ jobs ใน S3 หรือ sync ไม่สำเร็จ")
    else:
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 60)
print("สรุป")
print("=" * 60)
print("💡 ถ้ายังได้ total=0:")
print("   1. ตรวจสอบ Lambda CloudWatch Logs")
print("   2. ตรวจสอบ Lambda execution role มี S3 permissions")
print("   3. ตรวจสอบว่า Lambda อ่าน S3 ได้จริง")
print("=" * 60)

