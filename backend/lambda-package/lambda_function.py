"""
Lambda Function Entry Point for AWS Lambda + API Gateway
Handler: lambda_function.handler
"""
import sys
import os

# Add python/ directory to sys.path so Lambda can find dependencies
# Dependencies are installed in python/ directory to avoid conflicts with stdlib
python_path = os.path.join(os.path.dirname(__file__), 'python')
if python_path not in sys.path:
    sys.path.insert(0, python_path)

from mangum import Mangum
from main import app

# Create Mangum handler for Lambda
# This handles both REST API v1 and HTTP API v2 event formats
handler = Mangum(app, lifespan="off")

