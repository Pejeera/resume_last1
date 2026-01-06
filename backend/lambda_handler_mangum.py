"""
Lambda Handler using Mangum + FastAPI
This handler uses FastAPI app with Mangum adapter to support API Gateway JWT Authorizer

For AWS HTTP API + JWT Authorizer:
- User claims are available at: event.requestContext.authorizer.jwt.claims
- API Gateway already verifies JWT, so we don't need to verify again
"""
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
    return handler(event, context)

