"""
Test Lambda Function with Correct API Gateway Event Formats
This script tests both REST API v1 and HTTP API v2 event formats
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def load_test_events():
    """Load test events from JSON file"""
    events_file = Path(__file__).parent / 'lambda_test_events.json'
    with open(events_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_lambda_with_event(lambda_client, function_name, event_name, event_data):
    """Test Lambda with a specific event"""
    print(f"\n{'='*60}")
    print(f"Testing: {event_name}")
    print(f"{'='*60}")
    print(f"Event Type: {'REST API v1' if 'rest_api' in event_name else 'HTTP API v2'}")
    print(f"Method: {event_data.get('httpMethod') or event_data.get('requestContext', {}).get('http', {}).get('method', 'N/A')}")
    print(f"Path: {event_data.get('path') or event_data.get('rawPath', 'N/A')}")
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event_data)
        )
        
        payload = response['Payload'].read()
        result = json.loads(payload)
        
        status_code = result.get('statusCode', 'N/A')
        print(f"\nStatus Code: {status_code}")
        
        if 'FunctionError' in response:
            print(f"[ERROR] Function Error: {response.get('FunctionError')}")
            print(f"Error Message: {result.get('errorMessage', 'N/A')}")
            print(f"Error Type: {result.get('errorType', 'N/A')}")
            if 'stackTrace' in result:
                print(f"\nStack Trace:")
                for line in result['stackTrace'][:5]:  # Show first 5 lines
                    print(f"  {line}")
        elif status_code == 200:
            print(f"[SUCCESS] Success!")
            try:
                body = json.loads(result.get('body', '{}'))
                print(f"Response: {json.dumps(body, indent=2)}")
            except:
                print(f"Response Body: {result.get('body', 'N/A')}")
        elif status_code == 405:
            print(f"[WARN] Method Not Allowed")
            print(f"Response: {result.get('body', 'N/A')}")
            print(f"\nPossible causes:")
            print(f"  1. Route path mismatch")
            print(f"  2. HTTP method mismatch")
            print(f"  3. CORS preflight (OPTIONS) not handled")
        else:
            print(f"[WARN] Status: {status_code}")
            print(f"Response: {result.get('body', 'N/A')}")
        
        return status_code == 200
        
    except Exception as e:
        print(f"[ERROR] Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("="*60)
    print("Lambda Function Test - API Gateway Event Formats")
    print("="*60)
    
    # Get Lambda config
    lambda_function_name = os.getenv('LAMBDA_FUNCTION_NAME', 'ResumeMatchAPI')
    aws_region = os.getenv('AWS_REGION', 'ap-southeast-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    print(f"\nLambda Function: {lambda_function_name}")
    print(f"AWS Region: {aws_region}")
    
    # Create Lambda client
    lambda_client = boto3.client(
        'lambda',
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    
    # Try to find Lambda function
    try:
        print("\n" + "="*60)
        print("Searching for Lambda functions...")
        print("="*60)
        response = lambda_client.list_functions()
        functions = response.get('Functions', [])
        
        found = False
        for func in functions:
            if 'resume' in func['FunctionName'].lower() or 'search' in func['FunctionName'].lower():
                lambda_function_name = func['FunctionName']
                found = True
                print(f"[OK] Found: {lambda_function_name} (Runtime: {func.get('Runtime', 'N/A')})")
                break
        
        if not found:
            print(f"[WARN] Using default: {lambda_function_name}")
            print("   (Make sure this function exists)")
    except Exception as e:
        print(f"[WARN] Could not list functions: {e}")
        print(f"   Using: {lambda_function_name}")
    
    # Load test events
    try:
        test_events = load_test_events()
        print(f"\n[OK] Loaded {len(test_events)} test events")
    except Exception as e:
        print(f"[ERROR] Failed to load test events: {e}")
        return
    
    # Test REST API v1 events
    print("\n" + "="*60)
    print("Testing REST API v1 (Lambda Proxy) Events")
    print("="*60)
    
    rest_api_events = {k: v for k, v in test_events.items() if 'rest_api' in k}
    rest_results = {}
    
    for event_name, event_data in rest_api_events.items():
        success = test_lambda_with_event(lambda_client, lambda_function_name, event_name, event_data)
        rest_results[event_name] = success
    
    # Test HTTP API v2 events
    print("\n" + "="*60)
    print("Testing HTTP API v2 Events")
    print("="*60)
    
    http_api_events = {k: v for k, v in test_events.items() if 'http_api' in k}
    http_results = {}
    
    for event_name, event_data in http_api_events.items():
        success = test_lambda_with_event(lambda_client, lambda_function_name, event_name, event_data)
        http_results[event_name] = success
    
    # Test CORS preflight
    print("\n" + "="*60)
    print("Testing CORS Preflight (OPTIONS)")
    print("="*60)
    
    cors_event = test_events.get('cors_preflight_options')
    if cors_event:
        cors_success = test_lambda_with_event(
            lambda_client, 
            lambda_function_name, 
            'cors_preflight_options', 
            cors_event
        )
    else:
        cors_success = False
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    print(f"\nREST API v1 Results:")
    for event_name, success in rest_results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} - {event_name}")
    
    print(f"\nHTTP API v2 Results:")
    for event_name, success in http_results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} - {event_name}")
    
    print(f"\nCORS Preflight:")
    status = "[PASS]" if cors_success else "[FAIL]"
    print(f"  {status} - OPTIONS request")
    
    # Recommendations
    print("\n" + "="*60)
    print("Recommendations")
    print("="*60)
    
    rest_pass_count = sum(1 for v in rest_results.values() if v)
    http_pass_count = sum(1 for v in http_results.values() if v)
    
    if rest_pass_count > http_pass_count:
        print("\n[OK] REST API v1 events work better")
        print("   -> Your API Gateway is likely REST API with Lambda Proxy")
        print("   -> Use REST API v1 event format")
    elif http_pass_count > rest_pass_count:
        print("\n[OK] HTTP API v2 events work better")
        print("   -> Your API Gateway is likely HTTP API")
        print("   -> Use HTTP API v2 event format")
    else:
        print("\n[WARN] Both formats have issues")
        print("   -> Check API Gateway configuration")
        print("   -> Check CloudWatch Logs for details")
    
    if not cors_success:
        print("\n[WARN] CORS preflight (OPTIONS) not handled")
        print("   -> Add OPTIONS handler in FastAPI")
        print("   -> Or ensure CORS middleware handles it")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()

