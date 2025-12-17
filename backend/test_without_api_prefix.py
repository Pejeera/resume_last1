"""
Test paths without /api prefix to see if Mangum strips it
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def test_paths_without_api_prefix():
    """Test paths without /api prefix"""
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
    print("Testing Paths WITHOUT /api prefix")
    print("="*60)
    print(f"Lambda Function: {lambda_function_name}\n")
    
    # Test different paths without /api prefix
    test_paths = [
        ("/health", "GET /health"),
        ("/jobs/list", "GET /jobs/list"),
    ]
    
    for path, route_key in test_paths:
        print(f"\n{'='*60}")
        print(f"Testing: {path}")
        print(f"{'='*60}")
        
        event = {
            "version": "2.0",
            "routeKey": route_key,
            "rawPath": path,
            "rawQueryString": "",
            "headers": {"accept": "application/json"},
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1"
                },
                "requestId": f"test-{path.replace('/', '-')}",
                "routeKey": route_key,
                "stage": "$default",
                "timeEpoch": 1704067200
            },
            "body": None,
            "isBase64Encoded": False
        }
        
        try:
            response = lambda_client.invoke(
                FunctionName=lambda_function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(event)
            )
            
            payload = response['Payload'].read()
            result = json.loads(payload)
            
            status_code = result.get('statusCode', 'N/A')
            print(f"Status Code: {status_code}")
            
            if status_code == 200:
                print("[SUCCESS] Path works!")
                try:
                    body = json.loads(result.get('body', '{}'))
                    print(f"Response: {json.dumps(body, indent=2)}")
                except:
                    print(f"Response: {result.get('body', 'N/A')}")
            elif status_code == 404:
                print("[INFO] 404 Not Found - Path doesn't exist (expected)")
                print(f"Response: {result.get('body', 'N/A')}")
            elif status_code == 405:
                print("[WARN] 405 Method Not Allowed")
                print(f"Response: {result.get('body', 'N/A')}")
            else:
                print(f"[WARN] Status: {status_code}")
                print(f"Response: {result.get('body', 'N/A')}")
                
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    test_paths_without_api_prefix()

