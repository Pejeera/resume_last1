"""
Test different path formats to find the correct one for Mangum
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def test_path_variations():
    """Test different path variations"""
    lambda_function_name = os.getenv('LAMBDA_FUNCTION_NAME', 'ResumeMatchAPI')
    aws_region = os.getenv('AWS_REGION', 'ap-southeast-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    lambda_client = boto3.client(
        'lambda',
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    
    # Try to find Lambda function
    try:
        response = lambda_client.list_functions()
        functions = response.get('Functions', [])
        for func in functions:
            if 'resume' in func['FunctionName'].lower() or 'search' in func['FunctionName'].lower():
                lambda_function_name = func['FunctionName']
                break
    except:
        pass
    
    print("="*60)
    print("Testing Path Variations for Mangum")
    print("="*60)
    print(f"Lambda Function: {lambda_function_name}\n")
    
    # Test different path formats
    test_cases = [
        {
            "name": "Path with /api prefix (current)",
            "event": {
                "version": "2.0",
                "routeKey": "GET /api/health",
                "rawPath": "/api/health",
                "rawQueryString": "",
                "headers": {"accept": "application/json"},
                "requestContext": {
                    "http": {
                        "method": "GET",
                        "path": "/api/health",
                        "protocol": "HTTP/1.1",
                        "sourceIp": "127.0.0.1"
                    },
                    "requestId": "test-1",
                    "routeKey": "GET /api/health",
                    "stage": "$default",
                    "timeEpoch": 1704067200
                },
                "body": None,
                "isBase64Encoded": False
            }
        },
        {
            "name": "Path without /api prefix",
            "event": {
                "version": "2.0",
                "routeKey": "GET /health",
                "rawPath": "/health",
                "rawQueryString": "",
                "headers": {"accept": "application/json"},
                "requestContext": {
                    "http": {
                        "method": "GET",
                        "path": "/health",
                        "protocol": "HTTP/1.1",
                        "sourceIp": "127.0.0.1"
                    },
                    "requestId": "test-2",
                    "routeKey": "GET /health",
                    "stage": "$default",
                    "timeEpoch": 1704067200
                },
                "body": None,
                "isBase64Encoded": False
            }
        },
        {
            "name": "Path with stage prefix",
            "event": {
                "version": "2.0",
                "routeKey": "GET /api/health",
                "rawPath": "/prod/api/health",
                "rawQueryString": "",
                "headers": {"accept": "application/json"},
                "requestContext": {
                    "http": {
                        "method": "GET",
                        "path": "/prod/api/health",
                        "protocol": "HTTP/1.1",
                        "sourceIp": "127.0.0.1"
                    },
                    "requestId": "test-3",
                    "routeKey": "GET /api/health",
                    "stage": "prod",
                    "timeEpoch": 1704067200
                },
                "body": None,
                "isBase64Encoded": False
            }
        },
        {
            "name": "REST API v1 format with proxy",
            "event": {
                "resource": "/{proxy+}",
                "path": "/api/health",
                "httpMethod": "GET",
                "headers": {"Accept": "application/json"},
                "queryStringParameters": None,
                "pathParameters": {
                    "proxy": "api/health"
                },
                "requestContext": {
                    "resourcePath": "/{proxy+}",
                    "httpMethod": "GET",
                    "path": "/prod/api/health",
                    "accountId": "123456789012",
                    "protocol": "HTTP/1.1",
                    "stage": "prod",
                    "requestId": "test-4",
                    "requestTimeEpoch": 1704067200,
                    "identity": {"sourceIp": "127.0.0.1"},
                    "apiId": "test-api-id"
                },
                "body": None,
                "isBase64Encoded": False
            }
        },
        {
            "name": "REST API v1 format without proxy",
            "event": {
                "resource": "/api/health",
                "path": "/api/health",
                "httpMethod": "GET",
                "headers": {"Accept": "application/json"},
                "queryStringParameters": None,
                "pathParameters": None,
                "requestContext": {
                    "resourcePath": "/api/health",
                    "httpMethod": "GET",
                    "path": "/prod/api/health",
                    "accountId": "123456789012",
                    "protocol": "HTTP/1.1",
                    "stage": "prod",
                    "requestId": "test-5",
                    "requestTimeEpoch": 1704067200,
                    "identity": {"sourceIp": "127.0.0.1"},
                    "apiId": "test-api-id"
                },
                "body": None,
                "isBase64Encoded": False
            }
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test_case['name']}")
        print(f"{'='*60}")
        
        try:
            response = lambda_client.invoke(
                FunctionName=lambda_function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_case['event'])
            )
            
            payload = response['Payload'].read()
            result = json.loads(payload)
            
            status_code = result.get('statusCode', 'N/A')
            print(f"Status Code: {status_code}")
            
            if status_code == 200:
                print("[SUCCESS] Path format works!")
                try:
                    body = json.loads(result.get('body', '{}'))
                    print(f"Response: {json.dumps(body, indent=2)}")
                except:
                    print(f"Response: {result.get('body', 'N/A')}")
                results.append((test_case['name'], True, status_code))
            elif status_code == 405:
                print("[FAIL] Method Not Allowed")
                print(f"Response: {result.get('body', 'N/A')}")
                results.append((test_case['name'], False, status_code))
            else:
                print(f"[WARN] Status: {status_code}")
                print(f"Response: {result.get('body', 'N/A')}")
                results.append((test_case['name'], False, status_code))
                
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append((test_case['name'], False, 'ERROR'))
    
    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    for name, success, status in results:
        status_text = "[PASS]" if success else f"[FAIL - {status}]"
        print(f"{status_text} - {name}")
    
    # Find working format
    working = [r for r in results if r[1]]
    if working:
        print(f"\n[OK] Found {len(working)} working path format(s):")
        for name, _, _ in working:
            print(f"  - {name}")
    else:
        print("\n[WARN] No working path format found")
        print("  -> Check CloudWatch Logs for more details")
        print("  -> Verify API Gateway configuration")

if __name__ == "__main__":
    test_path_variations()

