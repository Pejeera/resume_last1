"""
List available Bedrock models in the region
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
from botocore.exceptions import ClientError

def list_bedrock_models():
    """List available Bedrock models"""
    print("=" * 60)
    print("  Available Bedrock Models")
    print("=" * 60)
    print()
    print(f"Region: {settings.BEDROCK_REGION}")
    print()
    
    try:
        # Create Bedrock client (not bedrock-runtime)
        client_kwargs = {
            'service_name': 'bedrock',
            'region_name': settings.BEDROCK_REGION
        }
        
        if (settings.AWS_ACCESS_KEY_ID and 
            settings.AWS_SECRET_ACCESS_KEY and 
            settings.AWS_ACCESS_KEY_ID.strip() != "" and 
            settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
            client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        bedrock = boto3.client(**client_kwargs)
        
        # List foundation models
        print("Fetching available models...")
        response = bedrock.list_foundation_models()
        
        models = response.get('modelSummaries', [])
        
        print(f"Found {len(models)} models")
        print()
        
        # Filter for Nova models
        nova_models = [m for m in models if 'nova' in m.get('modelId', '').lower()]
        
        if nova_models:
            print("Nova Models:")
            print("-" * 60)
            for model in nova_models:
                model_id = model.get('modelId', 'N/A')
                model_name = model.get('modelName', 'N/A')
                provider = model.get('providerName', 'N/A')
                print(f"  Model ID: {model_id}")
                print(f"  Name: {model_name}")
                print(f"  Provider: {provider}")
                print()
        else:
            print("[WARNING] No Nova models found")
            print()
        
        # Show all models (first 20)
        print("All Models (first 20):")
        print("-" * 60)
        for i, model in enumerate(models[:20], 1):
            model_id = model.get('modelId', 'N/A')
            model_name = model.get('modelName', 'N/A')
            provider = model.get('providerName', 'N/A')
            print(f"  [{i}] {model_id}")
            print(f"      Name: {model_name}")
            print(f"      Provider: {provider}")
            print()
        
        if len(models) > 20:
            print(f"... and {len(models) - 20} more models")
        
        return True
        
    except ClientError as e:
        print(f"[ERROR] Failed to list models: {e}")
        print()
        print("Possible issues:")
        print("  1. AWS credentials don't have Bedrock permissions")
        print("  2. Region doesn't support Bedrock")
        print("  3. Bedrock service not enabled in your account")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = list_bedrock_models()
    sys.exit(0 if success else 1)

