"""
Test root path to see if Mangum is working at all
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def test_root_path():
    """Test root path"""
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
    print("Testing Root Path")
    print("="*60)
    print(f"Lambda Function: {lambda_function_name}\n")
    
    # Test root path
    root_event = {
        "version": "2.0",
        "routeKey": "GET /",
        "rawPath": "/",
        "rawQueryString": "",
        "headers": {"accept": "application/json"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "requestId": "test-root",
            "routeKey": "GET /",
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
            Payload=json.dumps(root_event)
        )
        
        payload = response['Payload'].read()
        result = json.loads(payload)
        
        status_code = result.get('statusCode', 'N/A')
        print(f"Status Code: {status_code}")
        
        if status_code == 200:
            print("[SUCCESS] Root path works!")
            try:
                body = json.loads(result.get('body', '{}'))
                print(f"Response: {json.dumps(body, indent=2)}")
            except:
                print(f"Response: {result.get('body', 'N/A')}")
        else:
            print(f"[FAIL] Status: {status_code}")
            print(f"Response: {result.get('body', 'N/A')}")
            if 'FunctionError' in response:
                print(f"Error: {result.get('errorMessage', 'N/A')}")
                
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_root_path()

