"""
วินิจฉัยปัญหา OpenSearch Authentication
"""
import subprocess
import json
import sys
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = "https://k9z3rlu1ui.execute-api.us-east-1.amazonaws.com/prod"

def get_lambda_env_vars():
    """Get Lambda environment variables"""
    try:
        result = subprocess.run(
            ["aws", "lambda", "get-function-configuration",
             "--function-name", "ResumeMatchAPI",
             "--region", "us-east-1",
             "--query", "Environment.Variables",
             "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] ไม่สามารถดึง Lambda config: {e}")
        return None

def check_opensearch_domain():
    """Check OpenSearch domain configuration"""
    print("[2/4] ตรวจสอบ OpenSearch Domain Configuration...")
    print()
    
    try:
        # Try to get domain info
        result = subprocess.run(
            ["aws", "opensearch", "describe-domain",
             "--domain-name", "resume-search-dev",
             "--region", "ap-southeast-2",
             "--output", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            domain_info = json.loads(result.stdout)
            domain_status = domain_info.get("DomainStatus", {})
            
            print("   Domain Name:", domain_status.get("DomainName", "N/A"))
            print("   Endpoint:", domain_status.get("Endpoint", "N/A"))
            print("   DomainId:", domain_status.get("DomainId", "N/A"))
            print()
            
            # Check access policy
            access_policies = domain_status.get("AccessPolicies", "")
            if access_policies:
                try:
                    policies = json.loads(access_policies)
                    print("   Access Policies: มีการตั้งค่า")
                    print(f"   Policy keys: {list(policies.keys()) if isinstance(policies, dict) else 'N/A'}")
                except:
                    print("   Access Policies: มีการตั้งค่า (ไม่สามารถ parse JSON)")
            else:
                print("   Access Policies: ไม่มีการตั้งค่า")
            
            print()
            
            # Check fine-grained access control
            advanced_security = domain_status.get("AdvancedSecurityOptions", {})
            if advanced_security:
                enabled = advanced_security.get("Enabled", False)
                print(f"   Fine-Grained Access Control: {'Enabled' if enabled else 'Disabled'}")
                
                if enabled:
                    internal_user_database = advanced_security.get("InternalUserDatabaseEnabled", False)
                    print(f"   Internal User Database: {'Enabled' if internal_user_database else 'Disabled'}")
                    
                    master_user_options = advanced_security.get("MasterUserOptions", {})
                    if master_user_options:
                        master_user_arn = master_user_options.get("MasterUserARN", "")
                        master_user_name = master_user_options.get("MasterUserName", "")
                        if master_user_arn:
                            print(f"   Master User ARN: {master_user_arn}")
                        if master_user_name:
                            print(f"   Master User Name: {master_user_name}")
            
            print()
            return domain_status
        else:
            print(f"   [WARNING] ไม่สามารถดึงข้อมูล domain: {result.stderr}")
            print()
            return None
            
    except FileNotFoundError:
        print("   [WARNING] AWS CLI ไม่พบ - ข้ามการตรวจสอบ domain")
        print()
        return None
    except Exception as e:
        print(f"   [WARNING] เกิดข้อผิดพลาด: {e}")
        print()
        return None

def test_opensearch_connection_direct(endpoint, username, password):
    """Test OpenSearch connection directly"""
    print("[3/4] ทดสอบการเชื่อมต่อ OpenSearch โดยตรง...")
    print()
    
    try:
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Test basic connection
        test_url = f"{endpoint}/_cluster/health"
        
        print(f"   Testing: {test_url}")
        print(f"   Username: {username}")
        print()
        
        response = requests.get(
            test_url,
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("   [SUCCESS] เชื่อมต่อสำเร็จ!")
            data = response.json()
            print(f"   Cluster Status: {data.get('status', 'N/A')}")
            return True
        elif response.status_code == 401:
            print("   [ERROR] Authentication failed (401)")
            print("   [DIAGNOSIS] Username หรือ Password ไม่ถูกต้อง")
            return False
        elif response.status_code == 403:
            print("   [ERROR] Forbidden (403)")
            print("   [DIAGNOSIS] User ไม่มีสิทธิ์เข้าถึง")
            return False
        else:
            print(f"   [ERROR] Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   [ERROR] ไม่สามารถเชื่อมต่อได้")
        print("   [DIAGNOSIS] Endpoint อาจไม่ถูกต้อง หรือ network ไม่สามารถเข้าถึงได้")
        return False
    except Exception as e:
        print(f"   [ERROR] เกิดข้อผิดพลาด: {e}")
        return False

def suggest_fixes(env_vars, domain_info):
    """Suggest fixes based on findings"""
    print("[4/4] คำแนะนำการแก้ไข...")
    print()
    print("=" * 60)
    
    endpoint = env_vars.get("OPENSEARCH_ENDPOINT", "")
    username = env_vars.get("OPENSEARCH_USERNAME", "")
    password_set = bool(env_vars.get("OPENSEARCH_PASSWORD", ""))
    
    issues = []
    fixes = []
    
    # Check credentials
    if not endpoint or endpoint == "https://localhost:9200":
        issues.append("OPENSEARCH_ENDPOINT ไม่ถูกต้อง")
        fixes.append("ตั้งค่า endpoint ให้ชี้ไปที่ AWS OpenSearch Service")
    
    if not username:
        issues.append("OPENSEARCH_USERNAME ไม่ได้ตั้งค่า")
        fixes.append("ตั้งค่า username ให้ถูกต้อง")
    
    if not password_set:
        issues.append("OPENSEARCH_PASSWORD ไม่ได้ตั้งค่า")
        fixes.append("ตั้งค่า password ให้ถูกต้อง")
    
    if issues:
        print("พบปัญหา:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print()
        
        print("วิธีแก้ไข:")
        print()
        print("1. อัปเดต Lambda environment variables:")
        print()
        print("   .\\update_opensearch_credentials.ps1 \\")
        print(f"     -OpenSearchEndpoint '{endpoint if endpoint and endpoint != 'https://localhost:9200' else 'YOUR-OPENSEARCH-ENDPOINT'}' \\")
        print(f"     -OpenSearchUsername '{username if username else 'YOUR-USERNAME'}' \\")
        print("     -OpenSearchPassword 'YOUR-PASSWORD' \\")
        print("     -UseMock 'false'")
        print()
        
        if domain_info:
            advanced_security = domain_info.get("AdvancedSecurityOptions", {})
            if advanced_security.get("Enabled", False):
                print("2. ตรวจสอบ Fine-Grained Access Control:")
                print("   - ตรวจสอบว่า username และ password ถูกต้อง")
                print("   - ตรวจสอบว่า user มีสิทธิ์เข้าถึง domain")
                print("   - ตรวจสอบ role mapping (ถ้ามี)")
                print()
        
        print("3. ตรวจสอบ Network Access:")
        print("   - ตรวจสอบว่า Lambda สามารถเข้าถึง OpenSearch ได้")
        print("   - ตรวจสอบ VPC configuration (ถ้า OpenSearch อยู่ใน VPC)")
        print("   - ตรวจสอบ security groups")
        print()
        
        print("4. ทดสอบอีกครั้ง:")
        print("   python test_opensearch_lambda.py")
    else:
        print("การตั้งค่าพื้นฐานดูถูกต้อง")
        print()
        print("แต่ยังมีปัญหา Authentication - อาจเป็นเพราะ:")
        print("1. Password ไม่ถูกต้อง")
        print("2. Fine-Grained Access Control ต้องการการตั้งค่าเพิ่มเติม")
        print("3. Network/VPC configuration")
        print()
        print("แนะนำ:")
        print("1. ตรวจสอบ CloudWatch Logs สำหรับรายละเอียด")
        print("2. ทดสอบ credentials โดยตรง:")
        print(f"   curl -u {username}:PASSWORD {endpoint}/_cluster/health")
    
    print("=" * 60)

def main():
    print("=" * 60)
    print("วินิจฉัยปัญหา OpenSearch Authentication")
    print("=" * 60)
    print()
    
    # Get Lambda env vars
    print("[1/4] ตรวจสอบ Lambda Environment Variables...")
    print()
    env_vars = get_lambda_env_vars()
    
    if not env_vars:
        print("[ERROR] ไม่สามารถดึงข้อมูล Lambda configuration")
        return 1
    
    use_mock = env_vars.get("USE_MOCK", "true")
    endpoint = env_vars.get("OPENSEARCH_ENDPOINT", "")
    username = env_vars.get("OPENSEARCH_USERNAME", "")
    password = env_vars.get("OPENSEARCH_PASSWORD", "")
    
    print("   USE_MOCK:", use_mock)
    print("   OPENSEARCH_ENDPOINT:", endpoint)
    print("   OPENSEARCH_USERNAME:", username)
    print("   OPENSEARCH_PASSWORD:", "[SET]" if password else "[NOT SET]")
    print()
    
    if use_mock == "true":
        print("   [WARNING] USE_MOCK=true - OpenSearch จะไม่ถูกใช้งาน")
        print()
    
    # Check domain
    domain_info = check_opensearch_domain()
    
    # Test connection if credentials available
    if endpoint and username and password and endpoint != "https://localhost:9200":
        test_opensearch_connection_direct(endpoint, username, password)
    else:
        print("[3/4] ข้ามการทดสอบการเชื่อมต่อ (credentials ไม่ครบ)")
        print()
    
    # Suggest fixes
    suggest_fixes(env_vars, domain_info)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[WARNING] ยกเลิกการวินิจฉัย")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

