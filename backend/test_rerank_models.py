"""
Test different Bedrock rerank model IDs to find the correct one
"""
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings
import boto3
import json
from botocore.exceptions import ClientError

def test_model_id(model_id, region):
    """Test a specific model ID"""
    try:
        client_kwargs = {
            'service_name': 'bedrock-runtime',
            'region_name': region
        }
        
        if (settings.AWS_ACCESS_KEY_ID and 
            settings.AWS_SECRET_ACCESS_KEY and 
            settings.AWS_ACCESS_KEY_ID.strip() != "" and 
            settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
            client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        client = boto3.client(**client_kwargs)
        
        # Simple test prompt
        body = json.dumps({
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, test"
                }
            ],
            "inferenceConfig": {
                "maxTokens": 10,
                "temperature": 0.3
            }
        })
        
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        
        return True, "Model works!"
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        if error_code == 'ValidationException':
            return False, f"Invalid model ID: {error_msg}"
        elif error_code == 'AccessDeniedException':
            return False, f"Access denied: {error_msg}"
        else:
            return False, f"Error ({error_code}): {error_msg}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def test_multiple_models():
    """Test multiple model ID formats"""
    print("=" * 60)
    print("  Testing Bedrock Rerank Model IDs")
    print("=" * 60)
    print()
    print(f"Region: {settings.BEDROCK_REGION}")
    print()
    
    # List of model IDs to test
    model_ids = [
        "amazon.nova-lite-v1:0",
        "us.amazon.nova-lite-v1:0",
        "amazon.nova-lite-v1",
        "us.amazon.nova-lite-v1",
        "amazon.nova-pro-v1:0",
        "us.amazon.nova-pro-v1:0",
        "amazon.nova-micro-v1:0",
        "us.amazon.nova-micro-v1:0",
    ]
    
    # Also try us-east-1 region (common region for Bedrock)
    regions_to_test = [settings.BEDROCK_REGION, "us-east-1"]
    
    print("Testing model IDs...")
    print()
    
    found_working = False
    
    for region in regions_to_test:
        print(f"Region: {region}")
        print("-" * 60)
        
        for model_id in model_ids:
            print(f"Testing: {model_id}...", end=" ")
            success, message = test_model_id(model_id, region)
            
            if success:
                print(f"[OK] {message}")
                print()
                print(f"[SUCCESS] Working model found!")
                print(f"  Model ID: {model_id}")
                print(f"  Region: {region}")
                print()
                found_working = True
                break
            else:
                print(f"[FAIL] {message}")
        
        if found_working:
            break
        print()
    
    if not found_working:
        print()
        print("[WARNING] No working model ID found")
        print()
        print("Possible issues:")
        print("  1. Nova Lite model may not be available in your region")
        print("  2. Model may need to be enabled in Bedrock console")
        print("  3. AWS credentials may not have Bedrock access")
        print("  4. Model ID format may be different")
        print()
        print("Try:")
        print("  - Check Bedrock console for available models")
        print("  - Verify model is enabled in your AWS account")
        print("  - Check AWS credentials permissions")
    
    return found_working

if __name__ == "__main__":
    success = test_multiple_models()
    sys.exit(0 if success else 1)

