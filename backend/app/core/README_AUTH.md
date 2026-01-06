# Authentication with API Gateway JWT Authorizer

## Overview

This backend uses **AWS API Gateway JWT Authorizer** with Cognito User Pool. API Gateway verifies JWT tokens **before** requests reach the backend, so the backend does **NOT** verify JWT tokens again.

## Key Points

1. **No JWT Verification in Backend**: API Gateway already authenticates requests
2. **No 401 Errors**: Backend assumes all requests from API Gateway are authenticated
3. **User Claims Available**: Read user info from `event.requestContext.authorizer.jwt.claims`

## Usage

### Reading User Information

```python
from fastapi import Request, Depends
from app.core.auth import get_user_from_api_gateway, get_user_email, get_user_sub

# Option 1: Get user claims (optional - returns None if not available)
@router.get("/example")
async def example_endpoint(request: Request):
    user = get_user_from_api_gateway(request)
    if user:
        email = user.get("email")
        sub = user.get("sub")
        # Use user info...
    return {"message": "success"}

# Option 2: Get specific fields
@router.get("/example2")
async def example_endpoint2(request: Request):
    email = get_user_email(request)  # Returns None if not available
    user_id = get_user_sub(request)  # Returns None if not available
    return {"email": email, "user_id": user_id}

# Option 3: Use as dependency
from app.core.auth import get_current_user_optional

@router.get("/example3")
async def example_endpoint3(user: dict = Depends(get_current_user_optional)):
    if user:
        email = user.get("email")
        # Use user info...
    return {"message": "success"}
```

## API Gateway Event Structure

For AWS HTTP API (v2.0) with JWT Authorizer:

```json
{
  "requestContext": {
    "authorizer": {
      "jwt": {
        "claims": {
          "sub": "user-id-123",
          "email": "user@example.com",
          "cognito:username": "username",
          // ... other claims
        }
      }
    }
  }
}
```

## Lambda Handler

Use `lambda_handler_mangum.py` for FastAPI + Mangum deployment:

```python
# lambda_handler_mangum.py
from mangum import Mangum
from main import app

handler = Mangum(app, lifespan="on")

def lambda_handler(event, context):
    return handler(event, context)
```

Set Lambda handler to: `lambda_handler_mangum.lambda_handler`

## Important Notes

- **Never verify JWT in backend** - API Gateway already did this
- **Never return 401** - If request reached backend, it's authenticated
- **Claims may be empty** - Handle None/empty gracefully
- **Local development** - Claims won't be available, handle gracefully

