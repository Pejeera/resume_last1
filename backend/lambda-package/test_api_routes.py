"""
Test API routes with detailed logging
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def test_api_route(path, method="GET", body=None):
    """Test a specific API route"""
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
    
    # Find Lambda function
    try:
        response = lambda_client.list_functions()
        functions = response.get('Functions', [])
        for func in functions:
            if 'resume' in func['FunctionName'].lower() or 'search' in func['FunctionName'].lower():
                lambda_function_name = func['FunctionName']
                break
    except:
        pass
    
    # Try both REST API v1 and HTTP API v2 formats
    events = [
        {
            "name": "REST API v1",
            "event": {
                "resource": "/{proxy+}",
                "path": path,
                "httpMethod": method,
                "headers": {"Accept": "application/json", "Content-Type": "application/json"},
                "queryStringParameters": None,
                "pathParameters": {"proxy": path.lstrip("/")},
                "requestContext": {
                    "resourcePath": "/{proxy+}",
                    "httpMethod": method,
                    "path": f"/prod{path}",
                    "accountId": "123456789012",
                    "protocol": "HTTP/1.1",
                    "stage": "prod",
                    "requestId": "test-request",
                    "requestTimeEpoch": 1704067200,
                    "identity": {"sourceIp": "127.0.0.1"},
                    "apiId": "test-api-id"
                },
                "body": json.dumps(body) if body else None,
                "isBase64Encoded": False
            }
        },
        {
            "name": "HTTP API v2",
            "event": {
                "version": "2.0",
                "routeKey": f"{method} {path}",
                "rawPath": path,
                "rawQueryString": "",
                "headers": {"accept": "application/json", "content-type": "application/json"},
                "requestContext": {
                    "http": {
                        "method": method,
                        "path": path,
                        "protocol": "HTTP/1.1",
                        "sourceIp": "127.0.0.1"
                    },
                    "requestId": "test-request",
                    "routeKey": f"{method} {path}",
                    "stage": "$default",
                    "timeEpoch": 1704067200
                },
                "body": json.dumps(body) if body else None,
                "isBase64Encoded": False
            }
        }
    ]
    
    print(f"\n{'='*60}")
    print(f"Testing: {method} {path}")
    print(f"{'='*60}")
    
    for event_config in events:
        print(f"\n[{event_config['name']}]")
        try:
            response = lambda_client.invoke(
                FunctionName=lambda_function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(event_config['event'])
            )
            
            payload = response['Payload'].read()
            result = json.loads(payload)
            status_code = result.get('statusCode', 'N/A')
            
            if status_code == 200:
                print(f"  [SUCCESS] Status: {status_code}")
                try:
                    body = json.loads(result.get('body', '{}'))
                    print(f"  Response: {json.dumps(body, indent=4)}")
                except:
                    print(f"  Response: {result.get('body', 'N/A')}")
                return True
            elif status_code == 405:
                print(f"  [FAIL] Status: {status_code} - Method Not Allowed")
                print(f"  Response: {result.get('body', 'N/A')}")
            else:
                print(f"  [WARN] Status: {status_code}")
                print(f"  Response: {result.get('body', 'N/A')}")
                
            if 'FunctionError' in response:
                print(f"  Error: {result.get('errorMessage', 'N/A')}")
                
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    return False

def main():
    print("="*60)
    print("API Routes Test")
    print("="*60)
    
    # Test routes
    routes = [
        ("/", "GET"),
        ("/api/health", "GET"),
        ("/api/jobs/list", "GET"),
        ("/api/jobs/create", "POST", {"title": "Test Job", "description": "Test", "metadata": {}}),
    ]
    
    results = {}
    for route_info in routes:
        path = route_info[0]
        method = route_info[1]
        body = route_info[2] if len(route_info) > 2 else None
        results[path] = test_api_route(path, method, body)
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for path, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {path}")
    
    if not any(results.values()):
        print("\n[WARN] No routes working except root path")
        print("  -> Lambda function may need code update")
        print("  -> Run: .\\deploy_lambda.ps1")

if __name__ == "__main__":
    main()

