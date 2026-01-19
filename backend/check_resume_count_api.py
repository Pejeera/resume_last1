"""
Script to check total number of resumes via API endpoint
This avoids SSL issues by using the API Gateway endpoint
"""
import sys
import json
import io
import requests
import urllib3
from typing import Dict, Any

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def check_resumes_via_api(api_url: str = None):
    """Check resumes via API endpoint"""
    print("\n" + "="*60)
    print("เช็คจำนวน Resume ผ่าน API Endpoint")
    print("="*60)
    
    # Default API URL
    if not api_url:
        api_url = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"
    
    # Try to get resume list via API
    list_url = f"{api_url}/api/resumes/list"
    
    print(f"\nเรียก API: {list_url}")
    
    try:
        # Disable SSL verification for local testing (if needed)
        # In production, this should be True
        response = requests.get(list_url, timeout=30, verify=False)
        response.raise_for_status()
        
        data = response.json()
        
        resumes = data.get('resumes', [])
        total = data.get('total', 0)
        
        print(f"\nจำนวน Resume จาก API: {total}")
        
        if total > 0:
            print("\nรายละเอียด Resume:")
            print("-" * 60)
            
            # Group by name to find duplicates
            name_groups = {}
            for resume in resumes:
                name = resume.get('name', 'N/A')
                resume_id = resume.get('resume_id', 'N/A')
                if name not in name_groups:
                    name_groups[name] = []
                name_groups[name].append({
                    'id': resume_id,
                    's3_key': resume.get('s3_key', 'N/A'),
                    'created_at': resume.get('created_at', 'N/A')
                })
            
            # Show duplicates first
            duplicates = {name: resumes for name, resumes in name_groups.items() if len(resumes) > 1}
            unique = {name: resumes for name, resumes in name_groups.items() if len(resumes) == 1}
            
            if duplicates:
                print("\n⚠️  พบ Resume ที่มีชื่อซ้ำกัน (Duplicates):")
                print("=" * 60)
                for name, resume_list in duplicates.items():
                    print(f"\n📄 {name}")
                    print(f"   จำนวน: {len(resume_list)} (ซ้ำกัน!)")
                    for i, resume in enumerate(resume_list, 1):
                        print(f"   [{i}] ID: {resume['id']}")
                        print(f"       Created: {resume['created_at']}")
                        print(f"       S3 Key: {resume['s3_key']}")
            
            if unique:
                print(f"\n✅ Resume ที่ไม่ซ้ำกัน ({len(unique)} ไฟล์):")
                print("=" * 60)
                for name, resume_list in list(unique.items())[:20]:  # Show first 20
                    resume = resume_list[0]
                    print(f"\n📄 {name}")
                    print(f"   ID: {resume['id']}")
                    print(f"   Created: {resume['created_at']}")
                    print(f"   S3 Key: {resume['s3_key']}")
                
                if len(unique) > 20:
                    print(f"\n... และอีก {len(unique) - 20} ไฟล์")
            
            # Summary
            print("\n" + "=" * 60)
            print("สรุป:")
            print(f"  - จำนวน Resume ทั้งหมด (จาก API): {total}")
            print(f"  - จำนวนไฟล์ที่ไม่ซ้ำ: {len(name_groups)}")
            print(f"  - จำนวนไฟล์ที่ซ้ำกัน: {len(duplicates)}")
            if duplicates:
                total_duplicates = sum(len(resumes) - 1 for resumes in duplicates.values())
                print(f"  - จำนวน Resume ที่ซ้ำ (ควรลบ): {total_duplicates}")
        
        return total
        
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Error calling API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text[:500]}")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        print(traceback.format_exc())
        return 0


def main():
    """Main function"""
    print("\n" + "="*60)
    print("Resume Count Checker (via API)")
    print("="*60)
    
    # Get API URL from command line or use default
    api_url = sys.argv[1] if len(sys.argv) > 1 else None
    
    if api_url:
        print(f"\nใช้ API URL: {api_url}")
    else:
        print(f"\nใช้ API URL เริ่มต้น: https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com")
        print("(สามารถระบุ API URL เป็น argument ได้)")
    
    count = check_resumes_via_api(api_url)
    
    print("\n" + "="*60)
    print(f"ผลลัพธ์: พบ Resume ทั้งหมด {count} ไฟล์ (จาก API)")
    print("="*60)


if __name__ == "__main__":
    main()

