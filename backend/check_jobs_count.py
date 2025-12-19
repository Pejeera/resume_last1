"""
สคริปต์เช็คจำนวน jobs บน API Gateway หรือ local server
"""
import sys
import os
import json
import argparse

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Default API URL - สามารถ override ได้ด้วย environment variable หรือ argument
DEFAULT_API_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")

def check_jobs_from_file():
    """เช็คจำนวน jobs จากไฟล์ JSON"""
    jobs_file = os.path.join(os.path.dirname(__file__), "jobs_data.json")
    
    if os.path.exists(jobs_file):
        try:
            with open(jobs_file, 'r', encoding='utf-8') as f:
                jobs_data = json.load(f)
                count = len(jobs_data) if isinstance(jobs_data, list) else 0
                return count, jobs_data[:5] if isinstance(jobs_data, list) else []
        except Exception as e:
            print(f"Error reading jobs_data.json: {e}")
            return 0, []
    return 0, []

def check_jobs_count():
    """เช็คจำนวน jobs บน server"""
    print("=" * 60)
    print("กำลังเช็คจำนวน jobs...")
    print("=" * 60)
    print()
    
    # 1. เช็คจากไฟล์ JSON ก่อน
    file_count, sample_jobs = check_jobs_from_file()
    if file_count > 0:
        print(f"[ไฟล์] พบ jobs ใน jobs_data.json: {file_count} jobs")
        if sample_jobs:
            print("\nตัวอย่าง jobs จากไฟล์ (5 ตัวแรก):")
            for i, job in enumerate(sample_jobs, 1):
                title = job.get('title', 'N/A')
                job_id = job.get('_id', job.get('id', 'N/A'))
                print(f"   {i}. {title} (ID: {job_id})")
        print()
    
    # 2. เช็คจาก server (ถ้า server รันอยู่)
    if HAS_REQUESTS:
        print("=" * 60)
        print("กำลังเช็คจาก server...")
        print(f"URL: {DEFAULT_API_URL}/api/jobs/list")
        print()
        
        try:
            response = requests.get(f"{DEFAULT_API_URL}/api/jobs/list", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", [])
                total = data.get("total", 0)
                
                # ตรวจสอบว่าใช้ source ไหน
                print("=" * 60)
                print("ข้อมูล Source ของ Jobs:")
                print("=" * 60)
                print("📌 ตามโค้ดใน jobs.py:")
                print("   - ถ้า USE_MOCK=true: ดึงจาก Mock Storage (Memory) → S3 (fallback)")
                print("   - ถ้า USE_MOCK=false: ดึงจาก OpenSearch → S3 (fallback)")
                print()
                print("💡 เนื่องจากได้ total=0 แสดงว่า:")
                print("   - ไม่มี jobs ใน Mock Storage/OpenSearch")
                print("   - และไม่มี jobs_data.json ใน S3")
                print()
                print(f"[Server] พบ jobs บน server: {total} jobs")
                print()
                
                if jobs:
                    print("ตัวอย่าง jobs จาก server (5 ตัวแรก):")
                    for i, job in enumerate(jobs[:5], 1):
                        title = job.get('title', 'N/A')
                        job_id = job.get('job_id', 'N/A')
                        print(f"   {i}. {title} (ID: {job_id})")
                    print()
                else:
                    print("❌ ไม่พบ jobs บน server")
                    print()
                    print("=" * 60)
                    print("การวิเคราะห์ปัญหา:")
                    print("=" * 60)
                    print("1. ถ้าใช้ MOCK mode:")
                    print("   - Mock Storage (Memory) ว่างเปล่า")
                    print("   - และไม่มี jobs_data.json ใน S3")
                    print()
                    print("2. ถ้าใช้ PRODUCTION mode:")
                    print("   - OpenSearch index 'jobs_index' ว่างเปล่าหรือไม่มี")
                    print("   - และไม่มี jobs_data.json ใน S3")
                    print()
                    print("=" * 60)
                    print("วิธีแก้ไข:")
                    print("=" * 60)
                    print("1. อัปโหลด jobs_data.json ไปยัง S3:")
                    print("   - Bucket: resume-matching-533267343789")
                    print("   - Path: resumes/jobs_data.json")
                    print()
                    print("2. Sync jobs จาก S3 ไปยัง OpenSearch:")
                    print(f"   POST {DEFAULT_API_URL}/api/jobs/sync_from_s3")
                    print()
                    print("3. หรือสร้าง jobs ใหม่:")
                    print(f"   POST {DEFAULT_API_URL}/api/jobs/create")
                    print("=" * 60)
            else:
                print(f"[Server] Error: Status Code {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Detail: {error_data.get('detail', 'Unknown error')}")
                except:
                    print(f"   Response: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print("[Server] ไม่สามารถเชื่อมต่อกับ server ได้")
            print("\nคำแนะนำ:")
            print("   - ตรวจสอบ API Gateway URL")
            print("   - ตรวจสอบ Network connection")
            print(f"   - URL ที่ใช้: {DEFAULT_API_URL}")
        except requests.exceptions.Timeout:
            print("[Server] Timeout: Server ใช้เวลาตอบสนองนานเกินไป")
        except Exception as e:
            print(f"[Server] Error: {e}")
    else:
        print("[Server] ไม่สามารถเช็คจาก server ได้ (requests module ไม่พบ)")
        print("   Install: pip install requests")
    
    print()
    print("=" * 60)
    print("สรุป:")
    if file_count > 0:
        print(f"   - ไฟล์ jobs_data.json: {file_count} jobs")
    if HAS_REQUESTS:
        print("   - Server: ดูผลลัพธ์ด้านบน")
    print("=" * 60)

if __name__ == "__main__":
    check_jobs_count()
