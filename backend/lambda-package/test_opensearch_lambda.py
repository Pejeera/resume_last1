"""
Test OpenSearch through Lambda Function
This script invokes the Lambda function to test OpenSearch operations
"""
import json
import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / 'infra' / '.env'
load_dotenv(env_path)

def invoke_lambda_test_opensearch():
    """Invoke Lambda function to test OpenSearch"""
    print("=" * 60)
    print("Testing OpenSearch via Lambda Function")
    print("=" * 60)
    
    # Get Lambda config
    lambda_function_name = os.getenv('LAMBDA_FUNCTION_NAME', 'resume-search-api')
    aws_region = os.getenv('AWS_REGION', 'ap-southeast-1')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    print(f"Lambda Function: {lambda_function_name}")
    print(f"AWS Region: {aws_region}")
    print()
    
    # Create Lambda client
    lambda_client = boto3.client(
        'lambda',
        region_name=aws_region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    
    # Try to list Lambda functions to find the correct name
    try:
        print("=" * 60)
        print("Searching for Lambda functions...")
        print("=" * 60)
        response = lambda_client.list_functions()
        functions = response.get('Functions', [])
        print(f"Found {len(functions)} Lambda functions:")
        for func in functions:
            print(f"  - {func['FunctionName']} (Runtime: {func.get('Runtime', 'N/A')})")
            # Auto-detect if function name contains 'resume' or 'search'
            if 'resume' in func['FunctionName'].lower() or 'search' in func['FunctionName'].lower():
                lambda_function_name = func['FunctionName']
                print(f"  -> Using: {lambda_function_name}")
        print()
    except Exception as e:
        print(f"[WARNING] Could not list Lambda functions: {e}")
        print(f"Using default function name: {lambda_function_name}")
        print()
    
    try:
        # Test 1: Health check
        print("=" * 60)
        print("Test 1: Health Check")
        print("=" * 60)
        
        # Try REST API v1 format (most common for Lambda)
        health_payload = {
            "resource": "/api/health",
            "path": "/api/health",
            "httpMethod": "GET",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            "multiValueHeaders": {},
            "queryStringParameters": None,
            "multiValueQueryStringParameters": None,
            "pathParameters": None,
            "stageVariables": None,
            "requestContext": {
                "resourceId": "test",
                "resourcePath": "/api/health",
                "httpMethod": "GET",
                "requestId": "test-request-id-1",
                "path": "/api/health",
                "accountId": "123456789012",
                "protocol": "HTTP/1.1",
                "stage": "test",
                "domainPrefix": "test",
                "requestTime": "01/Jan/2024:00:00:00 +0000",
                "requestTimeEpoch": 1704067200,
                "identity": {
                    "sourceIp": "127.0.0.1"
                },
                "apiId": "test-api-id"
            },
            "body": None,
            "isBase64Encoded": False
        }
        
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(health_payload)
        )
        
        payload = response['Payload'].read()
        result = json.loads(payload)
        print(f"Status Code: {result.get('statusCode', 'N/A')}")
        if result.get('statusCode') == 200:
            print(f"✅ Health check successful!")
            body = json.loads(result.get('body', '{}'))
            print(f"   Status: {body.get('status', 'N/A')}")
            print(f"   Service: {body.get('service', 'N/A')}")
        else:
            print(f"Response Body: {result.get('body', 'N/A')}")
        if 'FunctionError' in response:
            print(f"Function Error: {response.get('FunctionError')}")
        print()
        
        # Test 2: Test OpenSearch connection (via custom endpoint if exists)
        # For now, let's test by creating a job which uses OpenSearch
        print("=" * 60)
        print("Test 2: Create Job (tests OpenSearch indexing)")
        print("=" * 60)
        
        test_job = {
            "title": "Test Senior Backend Engineer - Lambda Test",
            "description": "We are looking for a Senior Backend Engineer with experience in Python, FastAPI, AWS Lambda, and OpenSearch.",
            "metadata": {
                "location": "Bangkok",
                "salary_range": "80k-120k",
                "experience_years": "5+"
            }
        }
        
        create_job_payload = {
            "resource": "/api/jobs/create",
            "path": "/api/jobs/create",
            "httpMethod": "POST",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            "multiValueHeaders": {},
            "queryStringParameters": None,
            "multiValueQueryStringParameters": None,
            "pathParameters": None,
            "stageVariables": None,
            "requestContext": {
                "resourceId": "test",
                "resourcePath": "/api/jobs/create",
                "httpMethod": "POST",
                "requestId": "test-request-id-2",
                "path": "/api/jobs/create",
                "accountId": "123456789012",
                "protocol": "HTTP/1.1",
                "stage": "test",
                "domainPrefix": "test",
                "requestTime": "01/Jan/2024:00:00:00 +0000",
                "requestTimeEpoch": 1704067200,
                "identity": {
                    "sourceIp": "127.0.0.1"
                },
                "apiId": "test-api-id"
            },
            "body": json.dumps(test_job),
            "isBase64Encoded": False
        }
        
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(create_job_payload)
        )
        
        payload = response['Payload'].read()
        result = json.loads(payload)
        print(f"Status Code: {result.get('statusCode', 'N/A')}")
        print(f"Response Body: {result.get('body', 'N/A')}")
        if 'FunctionError' in response:
            print(f"Function Error: {response.get('FunctionError')}")
            print(f"Error Details: {result}")
        print()
        
        # Test 3: List jobs (tests OpenSearch search)
        print("=" * 60)
        print("Test 3: List Jobs (tests OpenSearch search)")
        print("=" * 60)
        
        list_jobs_payload = {
            "resource": "/api/jobs/list",
            "path": "/api/jobs/list",
            "httpMethod": "GET",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            "multiValueHeaders": {},
            "queryStringParameters": None,
            "multiValueQueryStringParameters": None,
            "pathParameters": None,
            "stageVariables": None,
            "requestContext": {
                "resourceId": "test",
                "resourcePath": "/api/jobs/list",
                "httpMethod": "GET",
                "requestId": "test-request-id-3",
                "path": "/api/jobs/list",
                "accountId": "123456789012",
                "protocol": "HTTP/1.1",
                "stage": "test",
                "domainPrefix": "test",
                "requestTime": "01/Jan/2024:00:00:00 +0000",
                "requestTimeEpoch": 1704067200,
                "identity": {
                    "sourceIp": "127.0.0.1"
                },
                "apiId": "test-api-id"
            },
            "body": None,
            "isBase64Encoded": False
        }
        
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(list_jobs_payload)
        )
        
        payload = response['Payload'].read()
        result = json.loads(payload)
        print(f"Status Code: {result.get('statusCode', 'N/A')}")
        if result.get('statusCode') == 200:
            body = json.loads(result.get('body', '{}'))
            jobs = body.get('jobs', [])
            print(f"Found {len(jobs)} jobs")
            for i, job in enumerate(jobs[:3], 1):
                print(f"  {i}. {job.get('title', 'N/A')}")
        else:
            print(f"Response: {result.get('body', 'N/A')}")
        if 'FunctionError' in response:
            print(f"Function Error: {response.get('FunctionError')}")
        print()
        
        print("=" * 60)
        print("[OK] All Lambda tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Failed to invoke Lambda: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    invoke_lambda_test_opensearch()

