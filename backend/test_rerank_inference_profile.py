"""
Test Bedrock rerank with inference profile
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

def test_with_inference_profile():
    """Test rerank with inference profile format"""
    print("=" * 60)
    print("  Testing Bedrock Rerank with Inference Profile")
    print("=" * 60)
    print()
    print(f"Region: {settings.BEDROCK_REGION}")
    print()
    
    # Try different inference profile formats
    inference_profiles = [
        "us.amazon.nova-lite-v1:0",  # Inference profile format
        "amazon.nova-lite-v1:0",     # Direct model ID
    ]
    
    # Test query and candidates
    query = "Looking for Full Stack Developer"
    prompt = f"""คุณเป็น AI ที่เชี่ยวชาญในการจับคู่ Resume กับ Job

**คำถาม/Query:**
{query}

**รายการผู้สมัคร (Candidates):**
1. Full Stack Developer - React, Python, Node.js
2. Frontend Developer - React, TypeScript
3. Backend Developer - Python, Django

**งานของคุณ:**
จัดอันดับ Top 3 ที่เหมาะสมที่สุด

**รูปแบบผลลัพธ์ (JSON):**
{{
  "ranked_candidates": [
    {{
      "candidate_index": 0,
      "rerank_score": 0.95,
      "reason": "เหตุผลสั้นๆ"
    }}
  ]
}}

กรุณาให้ผลลัพธ์เป็น JSON เท่านั้น:"""
    
    try:
        client_kwargs = {
            'service_name': 'bedrock-runtime',
            'region_name': settings.BEDROCK_REGION
        }
        
        if (settings.AWS_ACCESS_KEY_ID and 
            settings.AWS_SECRET_ACCESS_KEY and 
            settings.AWS_ACCESS_KEY_ID.strip() != "" and 
            settings.AWS_SECRET_ACCESS_KEY.strip() != ""):
            client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        client = boto3.client(**client_kwargs)
        
        for profile_id in inference_profiles:
            print(f"Testing inference profile: {profile_id}")
            print("-" * 60)
            
            # Try different request formats
            formats = [
                # Format 1: Messages with content as string (current format)
                {
                    "name": "Messages with string content",
                    "body": {
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "inferenceConfig": {
                            "maxTokens": 500,
                            "temperature": 0.3,
                            "topP": 0.9
                        },
                        "responseFormat": {
                            "type": "json"
                        }
                    }
                },
                # Format 2: Messages with content as array (Nova format)
                {
                    "name": "Messages with array content",
                    "body": {
                        "messages": [
                            {
                                "role": "user",
                                "content": [{"text": prompt}]
                            }
                        ],
                        "inferenceConfig": {
                            "maxTokens": 500,
                            "temperature": 0.3,
                            "topP": 0.9
                        },
                        "responseFormat": {
                            "type": "json"
                        }
                    }
                },
                # Format 3: Simple text input (Titan format)
                {
                    "name": "Simple text input",
                    "body": {
                        "inputText": prompt,
                        "textGenerationConfig": {
                            "maxTokenCount": 500,
                            "temperature": 0.3,
                            "topP": 0.9
                        }
                    }
                }
            ]
            
            for fmt in formats:
                print(f"  Trying {fmt['name']}...", end=" ")
                try:
                    response = client.invoke_model(
                        modelId=profile_id,
                        body=json.dumps(fmt['body']),
                        contentType="application/json",
                        accept="application/json"
                    )
                    
                    response_body = json.loads(response['body'].read())
                    print("[OK] Success!")
                    print(f"      Response keys: {list(response_body.keys())}")
                    
                    # Try to extract result
                    if 'content' in response_body:
                        content = response_body['content']
                        if isinstance(content, list) and len(content) > 0:
                            text = content[0].get('text', '')
                            print(f"      Response length: {len(text)} chars")
                            if text:
                                try:
                                    result_json = json.loads(text)
                                    print(f"      Parsed JSON: {list(result_json.keys())}")
                                except:
                                    print(f"      Response preview: {text[:100]}...")
                    
                    print()
                    print(f"[SUCCESS] Working configuration found!")
                    print(f"  Inference Profile: {profile_id}")
                    print(f"  Format: {fmt['name']}")
                    print()
                    return True
                    
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    error_msg = e.response.get('Error', {}).get('Message', str(e))
                    
                    if 'Malformed' in error_msg or 'expected type' in error_msg:
                        print(f"[FAIL] Format error: {error_msg[:80]}...")
                    elif 'Invalid' in error_msg or 'not supported' in error_msg:
                        print(f"[FAIL] Invalid: {error_msg[:80]}...")
                    else:
                        print(f"[FAIL] {error_code}: {error_msg[:80]}...")
                except Exception as e:
                    print(f"[FAIL] Error: {str(e)[:80]}...")
            
            print()
        
        print("[WARNING] No working configuration found")
        return False
        
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_with_inference_profile()
    sys.exit(0 if success else 1)

