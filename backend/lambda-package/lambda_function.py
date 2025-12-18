"""
Lambda Function Entry Point for AWS Lambda + API Gateway
Handler: lambda_function.handler
"""
from mangum import Mangum
from main import app

# Create Mangum handler for Lambda
# This handles both REST API v1 and HTTP API v2 event formats
handler = Mangum(app, lifespan="off")

