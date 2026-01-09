"""
Test API Script - ทดสอบ API ตั้งแต่ login
Usage: python test_api.py
"""
import requests
import json
import sys
import os
from typing import Optional, Dict, Any

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Disable SSL warnings (for self-signed certificates)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API Configuration
API_BASE_URL = "https://tm0ch5vc2e.execute-api.ap-southeast-2.amazonaws.com"
API_PREFIX = "/api"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(message: str):
    try:
        print(f"{Colors.GREEN}[OK] {message}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[OK] {message}")

def print_error(message: str):
    try:
        print(f"{Colors.RED}[ERROR] {message}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[ERROR] {message}")

def print_info(message: str):
    try:
        print(f"{Colors.CYAN}[INFO] {message}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[INFO] {message}")

def print_warning(message: str):
    try:
        print(f"{Colors.YELLOW}[WARN] {message}{Colors.RESET}")
    except UnicodeEncodeError:
        print(f"[WARN] {message}")

def print_header(message: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_step(step: int, message: str):
    print(f"\n{Colors.CYAN}[Step {step}] {message}{Colors.RESET}")

class APITester:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.email: Optional[str] = None
        
    def get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {
            "Content-Type": "application/json"
        }
        if include_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def test_health(self) -> bool:
        """Test health endpoint (no auth required)"""
        print_step(1, "Testing /api/health endpoint (no auth required)")
        try:
            url = f"{self.base_url}{API_PREFIX}/health"
            response = requests.get(url, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Health check passed!")
                print_info(f"  Status: {data.get('status')}")
                print_info(f"  Service: {data.get('service')}")
                print_info(f"  Version: {data.get('version')}")
                return True
            else:
                print_error(f"Health check failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', error_data.get('message', response.text))}")
                except:
                    print_error(f"  Response: {response.text}")
                print_info(f"  Note: Health endpoint may require authentication on API Gateway")
                return False
        except requests.exceptions.RequestException as e:
            print_error(f"Health check failed: {str(e)}")
            return False
    
    def test_login(self, username: str, password: str) -> bool:
        """Test login endpoint"""
        print_step(2, f"Testing /api/auth/login endpoint")
        print_info(f"  Username: {username}")
        
        try:
            url = f"{self.base_url}{API_PREFIX}/auth/login"
            payload = {
                "username": username,
                "password": password
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=self.get_headers(include_auth=False),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("idToken")
                self.email = data.get("email")
                
                if self.token:
                    print_success("Login successful!")
                    print_info(f"  Email: {self.email}")
                    print_info(f"  Token: {self.token[:50]}...")
                    print_info(f"  Access Token: {data.get('accessToken', '')[:50]}...")
                    if data.get('refreshToken'):
                        print_info(f"  Refresh Token: {data.get('refreshToken', '')[:50]}...")
                    print_info(f"  Message: {data.get('message', '')}")
                    return True
                else:
                    print_error("Login response missing idToken")
                    return False
            else:
                print_error(f"Login failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    detail = error_data.get('detail', error_data.get('message', response.text))
                    print_error(f"  Error: {detail}")
                    # Print full response for debugging
                    print_info(f"  Full response: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print_error(f"  Response: {response.text}")
                    print_info(f"  Status code: {response.status_code}")
                    print_info(f"  Headers: {dict(response.headers)}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Login request failed: {str(e)}")
            return False
    
    def test_jobs_list(self) -> bool:
        """Test jobs list endpoint"""
        print_step(3, "Testing /api/jobs/list endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            url = f"{self.base_url}{API_PREFIX}/jobs/list"
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                jobs = data.get("jobs", [])
                
                print_success(f"Jobs list retrieved successfully!")
                print_info(f"  Total jobs: {total}")
                
                if jobs:
                    print_info(f"  First job: {jobs[0].get('title', 'N/A')} (ID: {jobs[0].get('job_id', 'N/A')})")
                    if len(jobs) > 1:
                        print_info(f"  Showing {min(3, len(jobs))} jobs:")
                        for i, job in enumerate(jobs[:3], 1):
                            print_info(f"    {i}. {job.get('title', 'N/A')} - {job.get('job_id', 'N/A')}")
                else:
                    print_warning("  No jobs found in the system")
                
                return True
            else:
                print_error(f"Jobs list failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', response.text)}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Jobs list request failed: {str(e)}")
            return False
    
    def test_resumes_list(self) -> bool:
        """Test resumes list endpoint"""
        print_step(4, "Testing /api/resumes/list endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            url = f"{self.base_url}{API_PREFIX}/resumes/list"
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                resumes = data.get("resumes", [])
                
                print_success(f"Resumes list retrieved successfully!")
                print_info(f"  Total resumes: {total}")
                
                if resumes:
                    print_info(f"  First resume: {resumes[0].get('name', 'N/A')} (ID: {resumes[0].get('resume_id', 'N/A')})")
                    if len(resumes) > 1:
                        print_info(f"  Showing {min(3, len(resumes))} resumes:")
                        for i, resume in enumerate(resumes[:3], 1):
                            print_info(f"    {i}. {resume.get('name', 'N/A')} - {resume.get('resume_id', 'N/A')}")
                else:
                    print_warning("  No resumes found in the system")
                
                return True
            else:
                print_error(f"Resumes list failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', response.text)}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Resumes list request failed: {str(e)}")
            return False
    
    def test_job_create(self, title: str = "Test Job", description: str = "This is a test job created by API test script") -> bool:
        """Test job create endpoint"""
        print_step(5, "Testing /api/jobs/create endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            url = f"{self.base_url}{API_PREFIX}/jobs/create"
            payload = {
                "title": title,
                "description": description,
                "metadata": {
                    "test": True,
                    "created_by": "test_api.py"
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=self.get_headers(),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Job created successfully!")
                print_info(f"  Job ID: {data.get('job_id')}")
                print_info(f"  Title: {data.get('title')}")
                print_info(f"  Created at: {data.get('created_at')}")
                return True
            else:
                print_error(f"Job create failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', response.text)}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Job create request failed: {str(e)}")
            return False
    
    def test_job_update(self, job_id: str) -> bool:
        """Test job update endpoint"""
        print_step(6, f"Testing /api/jobs/{{job_id}} PUT endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            url = f"{self.base_url}{API_PREFIX}/jobs/{job_id}"
            payload = {
                "job": {
                    "id": job_id,
                    "job_id": job_id,
                    "title": "Updated Test Job",
                    "description": "This is an updated test job",
                    "location": "Bangkok",
                    "department": "Engineering",
                    "skills": ["Python", "JavaScript"],
                    "metadata": {
                        "test": True,
                        "updated_by": "test_api.py"
                    }
                }
            }
            
            response = requests.put(
                url,
                json=payload,
                headers=self.get_headers(),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Job updated successfully!")
                print_info(f"  Job ID: {data.get('job_id')}")
                print_info(f"  Message: {data.get('message')}")
                return True
            else:
                print_error(f"Job update failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', error_data.get('error', response.text))}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Job update request failed: {str(e)}")
            return False
    
    def test_jobs_sync_from_s3(self) -> bool:
        """Test jobs sync from S3 endpoint"""
        print_step(7, "Testing /api/jobs/sync_from_s3 endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            url = f"{self.base_url}{API_PREFIX}/jobs/sync_from_s3"
            response = requests.post(
                url,
                headers=self.get_headers(),
                timeout=120,  # Sync may take longer
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Jobs sync completed!")
                print_info(f"  Synced: {data.get('synced', 0)}")
                print_info(f"  Skipped: {data.get('skipped', 0)}")
                print_info(f"  Total: {data.get('total', 0)}")
                print_info(f"  Message: {data.get('message', '')}")
                return True
            else:
                print_error(f"Jobs sync failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', response.text)}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Jobs sync request failed: {str(e)}")
            return False
    
    def test_resumes_upload_to_s3(self) -> bool:
        """Test resumes upload to S3 endpoint"""
        print_step(8, "Testing /api/resumes/upload_to_s3 endpoint")
        
        if not self.token:
            print_error("No token available. Please login first.")
            return False
        
        try:
            # Create a dummy file content
            file_content = b"Test resume content for API testing"
            files = {
                'file': ('test_resume.txt', file_content, 'text/plain')
            }
            
            url = f"{self.base_url}{API_PREFIX}/resumes/upload_to_s3"
            headers = {
                "Authorization": f"Bearer {self.token}"
            }
            
            response = requests.post(
                url,
                files=files,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Resume uploaded to S3 successfully!")
                print_info(f"  Resume ID: {data.get('resume_id')}")
                print_info(f"  Name: {data.get('name')}")
                print_info(f"  S3 URL: {data.get('s3_url')}")
                return True
            else:
                print_error(f"Resume upload failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print_error(f"  Error: {error_data.get('detail', response.text)}")
                except:
                    print_error(f"  Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Resume upload request failed: {str(e)}")
            return False
    
    def run_all_tests(self, username: str, password: str):
        """Run all API tests"""
        print_header("API Test Suite - Resume Matching API")
        
        results = {
            "health": False,
            "login": False,
            "jobs_list": False,
            "resumes_list": False,
            "job_create": False,
            "job_update": False,
            "jobs_sync": False,
            "resume_upload": False
        }
        
        # Test 1: Health check (no auth)
        results["health"] = self.test_health()
        
        if not results["health"]:
            print_warning("Health check failed. Continuing with other tests...")
        
        # Test 2: Login
        results["login"] = self.test_login(username, password)
        
        if not results["login"]:
            print_error("Login failed. Cannot continue with authenticated tests.")
            self.print_summary(results)
            return
        
        # Test 3: Jobs list
        results["jobs_list"] = self.test_jobs_list()
        
        # Test 4: Resumes list
        results["resumes_list"] = self.test_resumes_list()
        
        # Test 5: Job create
        results["job_create"] = self.test_job_create()
        
        # Test 6: Job update (if we have a job)
        if results["jobs_list"]:
            # Try to get first job ID
            try:
                url = f"{self.base_url}{API_PREFIX}/jobs/list"
                response = requests.get(
                    url,
                    headers=self.get_headers(),
                    timeout=30,
                    verify=False
                )
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])
                    if jobs:
                        job_id = jobs[0].get("id") or jobs[0].get("job_id")
                        if job_id:
                            results["job_update"] = self.test_job_update(job_id)
                        else:
                            print_warning("  No job ID found, skipping update test")
                    else:
                        # Use the job we just created
                        if results["job_create"]:
                            # We need to get the job_id from create response
                            # For now, skip if no jobs available
                            print_warning("  No jobs available for update test")
            except:
                print_warning("  Failed to get job for update test")
        else:
            print_warning("  Skipping job update test (jobs list failed)")
        
        # Test 7: Jobs sync from S3 (optional, may take time)
        print_info("\n  Note: Sync test may take a while and may fail if no jobs in S3")
        results["jobs_sync"] = self.test_jobs_sync_from_s3()
        
        # Test 8: Resume upload to S3
        results["resume_upload"] = self.test_resumes_upload_to_s3()
        
        # Print summary
        self.print_summary(results)
    
    def print_summary(self, results: Dict[str, bool]):
        """Print test summary"""
        print_header("Test Summary")
        
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            color = Colors.GREEN if result else Colors.RED
            print(f"{color}{status}{Colors.RESET} - {test_name.replace('_', ' ').title()}")
        
        print(f"\n{Colors.BOLD}Total: {total} | Passed: {Colors.GREEN}{passed}{Colors.RESET}{Colors.BOLD} | Failed: {Colors.RED}{failed}{Colors.RESET}{Colors.BOLD}{Colors.RESET}")
        
        if failed == 0:
            print_success("\nAll tests passed!")
        else:
            print_warning(f"\n{failed} test(s) failed. Please check the errors above.")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Resume Matching API")
    parser.add_argument(
        "--username",
        type=str,
        help="Username (email) for login",
        default=None
    )
    parser.add_argument(
        "--password",
        type=str,
        help="Password for login",
        default=None
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="API base URL",
        default=API_BASE_URL
    )
    
    args = parser.parse_args()
    
    # Get credentials
    username = args.username
    password = args.password
    
    if not username:
        username = input(f"{Colors.CYAN}Enter username (email): {Colors.RESET}").strip()
    
    if not password:
        import getpass
        password = getpass.getpass(f"{Colors.CYAN}Enter password: {Colors.RESET}")
    
    if not username or not password:
        print_error("Username and password are required!")
        sys.exit(1)
    
    # Create tester and run tests
    tester = APITester(base_url=args.base_url)
    tester.run_all_tests(username, password)


if __name__ == "__main__":
    main()

