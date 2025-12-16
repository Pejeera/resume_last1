"""
Application Configuration
Loads settings from environment variables with support for Secrets Manager
"""
from pydantic_settings import BaseSettings
from typing import List
import os
import json
import boto3
from botocore.exceptions import ClientError


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Resume Matching API"
    DEBUG: bool = False
    USE_MOCK: bool = os.getenv("USE_MOCK", "true").lower() == "true"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-southeast-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    # S3
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "resume-matching-bucket")
    S3_PREFIX: str = os.getenv("S3_PREFIX", "resumes/")
    
    # OpenSearch
    OPENSEARCH_ENDPOINT: str = os.getenv("OPENSEARCH_ENDPOINT", "https://localhost:9200")
    OPENSEARCH_USERNAME: str = os.getenv("OPENSEARCH_USERNAME", "admin")
    OPENSEARCH_PASSWORD: str = os.getenv("OPENSEARCH_PASSWORD", "admin")
    OPENSEARCH_USE_SSL: bool = os.getenv("OPENSEARCH_USE_SSL", "true").lower() == "true"
    OPENSEARCH_VERIFY_CERTS: bool = os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true"
    
    # Bedrock
    BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "ap-southeast-1")
    BEDROCK_EMBEDDING_MODEL: str = os.getenv("BEDROCK_EMBEDDING_MODEL", "cohere.embed-multilingual-v3")
    BEDROCK_RERANK_MODEL: str = os.getenv("BEDROCK_RERANK_MODEL", "us.amazon.nova-lite-v1:0")
    
    # Secrets Manager (optional)
    SECRETS_MANAGER_SECRET_NAME: str = os.getenv("SECRETS_MANAGER_SECRET_NAME", "")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load secrets from Secrets Manager if configured
        if self.SECRETS_MANAGER_SECRET_NAME and not self.USE_MOCK:
            self._load_secrets_from_manager()

    def _load_secrets_from_manager(self):
        """Load secrets from AWS Secrets Manager"""
        try:
            session = boto3.Session(
                aws_access_key_id=self.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY or None,
                region_name=self.AWS_REGION
            )
            client = session.client('secretsmanager')
            response = client.get_secret_value(SecretId=self.SECRETS_MANAGER_SECRET_NAME)
            secrets = json.loads(response['SecretString'])
            
            # Update settings from secrets
            for key, value in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        except ClientError as e:
            # Log error but continue with env vars
            print(f"Warning: Could not load secrets from Secrets Manager: {e}")


settings = Settings()

