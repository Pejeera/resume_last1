"""
Test Cognito directly to check if credentials and configuration are correct
"""
import boto3
import hmac
import hashlib
import base64
import sys
import io
from botocore.exceptions import ClientError

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Cognito configuration (same as auth.py)
COGNITO_USER_POOL_ID = "ap-southeast-2_bKxx54EbY"
COGNITO_CLIENT_ID = "14keq2t7pc87ncl3i26rrf5vec"
COGNITO_CLIENT_SECRET = "jjlm1l5lg2fvb2na0i2kuv75edgv8fvbskc8dq34abv5362tmdl"
COGNITO_REGION = "ap-southeast-2"

def calculate_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    """Calculate SECRET_HASH for Cognito"""
    message = username + client_id
    secret_hash = base64.b64encode(
        hmac.new(
            client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
    ).decode('utf-8')
    return secret_hash

def test_cognito_login(username: str, password: str):
    """Test Cognito login directly"""
    print(f"\n{'='*60}")
    print(f"Testing Cognito Login Directly")
    print(f"{'='*60}\n")
    
    print(f"Configuration:")
    print(f"  User Pool ID: {COGNITO_USER_POOL_ID}")
    print(f"  Client ID: {COGNITO_CLIENT_ID}")
    print(f"  Region: {COGNITO_REGION}")
    print(f"  Username: {username}")
    print(f"\n")
    
    try:
        # Step 1: Create Cognito client
        print("[Step 1] Creating Cognito client...")
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        print("[OK] Cognito client created successfully\n")
        
        # Step 2: Calculate SECRET_HASH
        print("[Step 2] Calculating SECRET_HASH...")
        secret_hash = calculate_secret_hash(username, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
        print(f"[OK] SECRET_HASH calculated: {secret_hash[:20]}...\n")
        
        # Step 3: Test login
        print("[Step 3] Attempting login...")
        auth_response = cognito_client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            ClientId=COGNITO_CLIENT_ID,
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
                'SECRET_HASH': secret_hash
            }
        )
        
        if auth_response.get('AuthenticationResult'):
            result = auth_response['AuthenticationResult']
            print("\n[SUCCESS] LOGIN SUCCESSFUL!\n")
            print(f"IdToken: {result.get('IdToken', '')[:50]}...")
            print(f"AccessToken: {result.get('AccessToken', '')[:50]}...")
            if result.get('RefreshToken'):
                print(f"RefreshToken: {result.get('RefreshToken', '')[:50]}...")
            return True
        else:
            print("\n[ERROR] Login failed - No AuthenticationResult in response")
            print(f"Response: {auth_response}")
            return False
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"\n[ERROR] LOGIN FAILED\n")
        print(f"Error Code: {error_code}")
        print(f"Error Message: {error_message}")
        print(f"\nFull Error Response:")
        print(f"{e.response}")
        
        # Provide helpful suggestions
        if error_code == 'NotAuthorizedException':
            print("\n💡 Suggestion: Username or password is incorrect")
        elif error_code == 'UserNotConfirmedException':
            print("\n💡 Suggestion: User account is not confirmed. Please verify email first.")
        elif error_code == 'UserNotFoundException':
            print("\n💡 Suggestion: User does not exist in Cognito User Pool")
        elif error_code == 'InvalidParameterException':
            print("\n💡 Suggestion: Check SECRET_HASH calculation or client configuration")
        elif error_code == 'ResourceNotFoundException':
            print("\n💡 Suggestion: User Pool or Client ID might be incorrect")
        elif 'AccessDenied' in error_code or 'UnauthorizedOperation' in error_code:
            print("\n💡 Suggestion: Check IAM permissions for Lambda function")
            print("   Lambda needs: cognito-idp:InitiateAuth permission")
        
        return False
        
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR\n")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"\nFull Traceback:")
        import traceback
        traceback.print_exc()
        return False

def test_cognito_user_exists(username: str):
    """Test if user exists in Cognito"""
    print(f"\n{'='*60}")
    print(f"Checking if user exists in Cognito")
    print(f"{'='*60}\n")
    
    try:
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        
        # Try to get user
        response = cognito_client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username
        )
        
        print(f"[OK] User found!")
        print(f"  Username: {response.get('Username')}")
        print(f"  User Status: {response.get('UserStatus')}")
        print(f"  Enabled: {response.get('Enabled')}")
        
        # Check attributes
        attributes = {attr['Name']: attr['Value'] for attr in response.get('UserAttributes', [])}
        if 'email' in attributes:
            print(f"  Email: {attributes['email']}")
        if 'email_verified' in attributes:
            print(f"  Email Verified: {attributes['email_verified']}")
        
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'UserNotFoundException':
            print(f"[ERROR] User not found in Cognito User Pool")
            return False
        else:
            print(f"[ERROR] Error checking user: {error_code}")
            print(f"  {e.response.get('Error', {}).get('Message', str(e))}")
            return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    username = "jeerasee@metrosystems.co.th"
    password = "Namwan2546."
    
    if len(sys.argv) > 1:
        username = sys.argv[1]
    if len(sys.argv) > 2:
        password = sys.argv[2]
    
    # Test 1: Check if user exists
    user_exists = test_cognito_user_exists(username)
    
    # Test 2: Try login
    if user_exists:
        test_cognito_login(username, password)
    else:
        print("\n⚠️  User does not exist. Skipping login test.")

