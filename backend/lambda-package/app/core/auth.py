"""
Authentication utilities for API Gateway JWT Authorizer

This module provides utilities to read user information from API Gateway's
JWT Authorizer claims. Since API Gateway already verifies the JWT, we don't
need to verify it again in the backend.

For AWS HTTP API + JWT Authorizer:
- User claims are available at: event.requestContext.authorizer.jwt.claims
- The request is already authenticated by API Gateway
"""
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_user_from_api_gateway(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extract user information from API Gateway JWT Authorizer claims.
    
    This function reads from the Lambda event's requestContext.authorizer.jwt.claims
    which is made available through Mangum/Starlette's request scope.
    
    For AWS HTTP API + JWT Authorizer:
    - Claims are at: event.requestContext.authorizer.jwt.claims
    - The request is already authenticated by API Gateway, so we don't verify JWT again
    
    Returns:
        Dict with user claims (email, sub, etc.) or None if not available
    """
    try:
        # For Lambda + Mangum, the event is stored in request.scope["aws.event"]
        # API Gateway JWT Authorizer puts claims at: event.requestContext.authorizer.jwt.claims
        
        # Check if we're running in Lambda (via Mangum)
        if "aws.event" in request.scope:
            event = request.scope["aws.event"]
            
            # Extract claims from API Gateway JWT Authorizer
            # For HTTP API (v2.0), structure is: requestContext.authorizer.jwt.claims
            request_context = event.get("requestContext", {})
            authorizer = request_context.get("authorizer", {})
            
            # Try HTTP API format first (v2.0)
            jwt_data = authorizer.get("jwt", {})
            if jwt_data:
                claims = jwt_data.get("claims", {})
                if claims:
                    logger.info(f"User authenticated via API Gateway JWT: {claims.get('email', claims.get('sub', 'unknown'))}")
                    return claims
            
            # Try REST API format (v1.0) - claims might be directly in authorizer
            if authorizer and "claims" not in jwt_data:
                # Check if claims are directly in authorizer (some configurations)
                if "sub" in authorizer or "email" in authorizer:
                    logger.info(f"User authenticated via API Gateway: {authorizer.get('email', authorizer.get('sub', 'unknown'))}")
                    return authorizer
            
            logger.debug("No JWT claims found in API Gateway authorizer")
            return None
        else:
            # Not running in Lambda - this is local development
            logger.debug("Not running in Lambda context - skipping API Gateway claims extraction")
            return None
            
    except Exception as e:
        logger.warning(f"Error extracting user from API Gateway claims: {e}")
        return None


def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current user from API Gateway claims (optional - doesn't raise error if not found).
    
    Use this when user info is optional for the endpoint.
    
    Returns:
        Dict with user claims or None
    """
    return get_user_from_api_gateway(request)


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Get current user from API Gateway claims.
    
    Since API Gateway already authenticates requests, we assume all requests
    are authenticated. If claims are not available, return empty dict instead
    of raising 401.
    
    Use this when user info is needed but not strictly required.
    
    Returns:
        Dict with user claims (or empty dict if not available)
    """
    user = get_user_from_api_gateway(request)
    
    if user is None:
        # API Gateway already authenticated the request, so we don't raise 401
        # Just return empty dict - the endpoint can check if needed
        logger.debug("User info not available from API Gateway claims, but request is authenticated")
        return {}
    
    return user


def get_user_email(request: Request) -> Optional[str]:
    """Get user email from API Gateway claims"""
    user = get_user_from_api_gateway(request)
    if user:
        return user.get("email")
    return None


def get_user_sub(request: Request) -> Optional[str]:
    """Get user sub (user ID) from API Gateway claims"""
    user = get_user_from_api_gateway(request)
    if user:
        return user.get("sub")
    return None

