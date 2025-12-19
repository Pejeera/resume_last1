"""
ตรวจสอบสถานะการตั้งค่า OpenSearch
"""
import json
import subprocess
import sys

def check_lambda_opensearch_config():
    """Check OpenSearch configuration in Lambda"""
    print("=" * 60)
    print("ตรวจสอบการตั้งค่า OpenSearch ใน Lambda")
    print("=" * 60)
    print()
    
    function_name = "ResumeMatchAPI"
    region = "us-east-1"
    
    try:
        # Get Lambda configuration
        print(f"[1/3] กำลังดึงข้อมูลจาก Lambda: {function_name}...")
        result = subprocess.run(
            ["aws", "lambda", "get-function-configuration",
             "--function-name", function_name,
             "--region", region,
             "--query", "Environment.Variables",
             "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        
        env_vars = json.loads(result.stdout)
        
        print("[2/3] ตรวจสอบการตั้งค่า...")
        print()
        
        # Check USE_MOCK
        use_mock = env_vars.get("USE_MOCK", "true")
        print(f"   USE_MOCK: {use_mock}")
        if use_mock == "true":
            print("   [WARNING] กำลังใช้ MOCK mode - OpenSearch จะไม่ถูกใช้งาน")
            print("   [ACTION] ตั้ง USE_MOCK=false เพื่อใช้ OpenSearch จริง")
        else:
            print("   [OK] ตั้งค่าให้ใช้ OpenSearch จริง")
        print()
        
        # Check OpenSearch endpoint
        endpoint = env_vars.get("OPENSEARCH_ENDPOINT", "")
        username = env_vars.get("OPENSEARCH_USERNAME", "")
        password = env_vars.get("OPENSEARCH_PASSWORD", "")
        
        print(f"   OPENSEARCH_ENDPOINT: {endpoint if endpoint else '[NOT SET]'}")
        print(f"   OPENSEARCH_USERNAME: {username if username else '[NOT SET]'}")
        print(f"   OPENSEARCH_PASSWORD: {'[SET]' if password else '[NOT SET]'}")
        print()
        
        if not endpoint:
            print("   [ERROR] OPENSEARCH_ENDPOINT ไม่ได้ถูกตั้งค่า")
            print("   [ACTION] ใช้สคริปต์ update_opensearch_credentials.ps1 เพื่อตั้งค่า")
        elif endpoint == "https://localhost:9200":
            print("   [WARNING] ใช้ localhost - ควรเป็น AWS OpenSearch endpoint")
            print("   [ACTION] ตั้งค่า endpoint ของ AWS OpenSearch Service")
        else:
            print("   [OK] OpenSearch endpoint ถูกตั้งค่าแล้ว")
        
        print()
        
        # Summary
        print("[3/3] สรุป:")
        print("=" * 60)
        
        if use_mock == "true":
            print("[STATUS] OpenSearch ยังไม่พร้อมใช้งาน (USE_MOCK=true)")
            print()
            print("วิธีเปิดใช้งาน OpenSearch:")
            print("1. ตั้งค่า USE_MOCK=false")
            print("2. ตั้งค่า OPENSEARCH_ENDPOINT ให้ชี้ไปที่ AWS OpenSearch")
            print("3. ตั้งค่า OPENSEARCH_USERNAME และ OPENSEARCH_PASSWORD")
            print()
            print("ใช้สคริปต์:")
            print("  .\\update_opensearch_credentials.ps1 \\")
            print("    -OpenSearchEndpoint 'https://search-xxx.us-east-1.es.amazonaws.com' \\")
            print("    -OpenSearchUsername 'admin' \\")
            print("    -OpenSearchPassword 'your-password' \\")
            print("    -UseMock 'false'")
        elif not endpoint or endpoint == "https://localhost:9200":
            print("[STATUS] OpenSearch ยังไม่พร้อมใช้งาน (endpoint ไม่ถูกต้อง)")
            print()
            print("วิธีแก้ไข:")
            print("  .\\update_opensearch_credentials.ps1 \\")
            print("    -OpenSearchEndpoint 'https://search-xxx.us-east-1.es.amazonaws.com' \\")
            print("    -OpenSearchUsername 'admin' \\")
            print("    -OpenSearchPassword 'your-password'")
        else:
            print("[STATUS] OpenSearch พร้อมใช้งาน!")
            print()
            print("ทดสอบการเชื่อมต่อ:")
            print("  python test_opensearch_connection.py")
            print()
            print("หรือทดสอบผ่าน API:")
            print("  python test_api_server.py")
        
        print("=" * 60)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ไม่สามารถเชื่อมต่อกับ AWS Lambda ได้")
        print(f"   {e.stderr}")
        print()
        print("ตรวจสอบว่า:")
        print("1. AWS CLI ถูกติดตั้งและตั้งค่าแล้ว")
        print("2. มีสิทธิ์เข้าถึง Lambda function")
        print("3. Function name และ region ถูกต้อง")
        return False
    except FileNotFoundError:
        print("[ERROR] ไม่พบ AWS CLI")
        print("   ติดตั้ง AWS CLI: https://aws.amazon.com/cli/")
        return False
    except Exception as e:
        print(f"[ERROR] เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = check_lambda_opensearch_config()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] ยกเลิกการตรวจสอบ")
        sys.exit(1)

