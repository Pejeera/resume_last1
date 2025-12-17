"""
Lambda Function Entry Point
This file is used by AWS Lambda to handle API Gateway requests
"""
from fastapi import FastAPI
from mangum import Mangum

# Import the FastAPI app from main.py
from main import app

# Create Lambda handler
# Handler name in Lambda console should be: lambda_function.handler
handler = Mangum(app, lifespan="off")

