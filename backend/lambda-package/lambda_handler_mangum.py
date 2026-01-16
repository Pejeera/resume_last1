"""
Lambda Handler using Mangum + FastAPI
This handler uses FastAPI app with Mangum adapter to support API Gateway JWT Authorizer

For AWS HTTP API + JWT Authorizer:
- User claims are available at: event.requestContext.authorizer.jwt.claims
- API Gateway already verifies JWT, so we don't need to verify again
"""
import sys
import os

# Add python directory to path if it exists
python_dir = os.path.join(os.path.dirname(__file__), 'python')
if os.path.exists(python_dir):
    sys.path.insert(0, python_dir)

from mangum import Mangum
from main import app

# Create Mangum adapter for FastAPI app
# This will handle API Gateway events and pass them to FastAPI
handler = Mangum(app, lifespan="on")

def lambda_handler(event, context):
    """
    Lambda handler entry point
    
    This handler uses Mangum to adapt FastAPI for Lambda.
    API Gateway JWT Authorizer claims are automatically available in:
    - event.requestContext.authorizer.jwt.claims (for HTTP API v2.0)
    
    The FastAPI app can access these claims via request.scope["aws.event"]
    """
    # Detect HTTP method for CORS preflight
    http_method = None
    if 'requestContext' in event and 'http' in event['requestContext']:
        # HTTP API v2.0 format
        http_method = event['requestContext']['http'].get('method')
    elif 'httpMethod' in event:
        # REST API format
        http_method = event['httpMethod']
    
    # Handle CORS preflight (OPTIONS) requests
    if http_method == 'OPTIONS':
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, X-Requested-With",
                "Access-Control-Expose-Headers": "*",
                "Access-Control-Max-Age": "3600",
                "Content-Type": "application/json"
            },
            "body": ""
        }
    
    # Call Mangum handler
    try:
        response = handler(event, context)
    except Exception as e:
        # If handler fails, return error with CORS headers
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, X-Requested-With",
                "Content-Type": "application/json"
            },
            "body": '{"error": "Internal server error"}'
        }
    
    # Ensure CORS headers are present in all responses
    if not isinstance(response, dict):
        return response
    
    # Initialize headers if missing
    if "headers" not in response:
        response["headers"] = {}
    
    # CORS headers to add
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, X-Requested-With",
        "Access-Control-Expose-Headers": "*"
    }
    
    # Merge CORS headers (don't override if already set by FastAPI)
    for key, value in cors_headers.items():
        if key.lower() not in {k.lower() for k in response["headers"].keys()}:
            response["headers"][key] = value
    
    return response

