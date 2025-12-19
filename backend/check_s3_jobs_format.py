"""
ตรวจสอบ format ของ jobs_data.json ใน S3
"""
import sys
import os
import json
import boto3
from botocore.exceptions import ClientError

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

bucket_name = "resume-matching-533267343789"
s3_key = "resumes/jobs_data.json"

print("=" * 60)
print("ตรวจสอบ format ของ jobs_data.json ใน S3")
print("=" * 60)
print(f"Bucket: {bucket_name}")
print(f"S3 Key: {s3_key}")
print()

try:
    s3_client = boto3.client('s3')
    
    # ดึง object จาก S3
    response = s3_client.get_object(
        Bucket=bucket_name,
        Key=s3_key
    )
    
    # อ่านข้อมูล
    content = response['Body'].read().decode('utf-8')
    data = json.loads(content)
    
    print("✅ อ่าน jobs_data.json สำเร็จ")
    print()
    print("Format Analysis:")
    print(f"  Type: {type(data).__name__}")
    
    if isinstance(data, list):
        print(f"  ✅ เป็น List (Array)")
        print(f"  จำนวน items: {len(data)}")
        if len(data) > 0:
            print(f"\n  ตัวอย่าง item แรก:")
            first_item = data[0]
            print(f"    Keys: {list(first_item.keys())}")
            print(f"    ID: {first_item.get('_id', first_item.get('id', first_item.get('job_id', 'N/A')))}")
            print(f"    Title: {first_item.get('title', 'N/A')}")
    elif isinstance(data, dict):
        print(f"  ⚠️  เป็น Dict (Object)")
        print(f"  Keys: {list(data.keys())}")
        
        if "jobs" in data:
            jobs = data["jobs"]
            print(f"  ✅ มี key 'jobs'")
            print(f"  จำนวน jobs: {len(jobs) if isinstance(jobs, list) else 'N/A'}")
            if isinstance(jobs, list) and len(jobs) > 0:
                print(f"\n  ตัวอย่าง job แรก:")
                first_job = jobs[0]
                print(f"    Keys: {list(first_job.keys())}")
                print(f"    ID: {first_job.get('_id', first_job.get('id', first_job.get('job_id', 'N/A')))}")
                print(f"    Title: {first_job.get('title', 'N/A')}")
        else:
            print(f"  ⚠️  ไม่มี key 'jobs'")
            print(f"  Keys ที่มี: {list(data.keys())}")
    else:
        print(f"  ❌ Format ไม่ถูกต้อง: {type(data)}")
    
    print()
    print("=" * 60)
    print("สรุป:")
    print("=" * 60)
    if isinstance(data, list):
        print("✅ Format ถูกต้อง - เป็น List")
        print("   โค้ดที่แก้ไขจะอ่านได้เลย")
    elif isinstance(data, dict) and "jobs" in data:
        print("✅ Format ถูกต้อง - เป็น Dict ที่มี key 'jobs'")
        print("   โค้ดที่แก้ไขจะอ่านได้เลย")
    else:
        print("❌ Format ไม่ถูกต้อง")
        print("   ต้องแก้ไข jobs_data.json ใน S3")
    
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'NoSuchKey':
        print(f"❌ ไม่พบไฟล์ {s3_key} ใน bucket {bucket_name}")
    elif error_code == 'AccessDenied':
        print(f"❌ ไม่มี permission อ่าน S3")
        print(f"   Error: {e}")
    else:
        print(f"❌ S3 Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

