"""
Application Configuration
Loads settings from environment variables with support for Secrets Manager
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import List
import os
import json
import boto3
from pathlib import Path
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# Determine .env file path and load it BEFORE Settings class is used
env_path = Path(__file__).parent.parent.parent / 'infra' / '.env'
env_file_str = str(env_path.resolve()) if env_path.exists() else None

# Load .env file into os.environ - this MUST happen before Settings() is instantiated
# This ensures that when Settings() is created, os.environ already has the values
if env_path.exists():
    # Always manually populate os.environ first (more reliable than load_dotenv in some contexts)
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value  # Always set to ensure values are available
    # Also call load_dotenv as backup
    load_dotenv(env_path, override=True)


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Resume Matching API"
    DEBUG: bool = False
    USE_MOCK: str = "false"  # Will be converted to bool in __init__
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # AWS Configuration
    AWS_REGION: str = "ap-southeast-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    
    # S3
    S3_BUCKET_NAME: str = "resume-matching-bucket"
    S3_PREFIX: str = "resumes/"
    
    # OpenSearch
    OPENSEARCH_ENDPOINT: str = "https://localhost:9200"
    OPENSEARCH_USERNAME: str = "admin"
    OPENSEARCH_PASSWORD: str = "admin"
    OPENSEARCH_USE_SSL: str = "true"  # Will be converted to bool in __init__
    OPENSEARCH_VERIFY_CERTS: str = "false"  # Will be converted to bool in __init__
    
    # Bedrock
    BEDROCK_REGION: str = "ap-southeast-1"
    BEDROCK_EMBEDDING_MODEL: str = "cohere.embed-multilingual-v3"
    BEDROCK_RERANK_MODEL: str = "us.amazon.nova-lite-v1:0"
    
    # Secrets Manager (optional)
    SECRETS_MANAGER_SECRET_NAME: str = ""
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Pydantic v2 settings config
    # BaseSettings reads from os.environ automatically
    # We also specify env_file as backup, but load_dotenv() above should populate os.environ
    model_config = SettingsConfigDict(
        env_file=env_file_str,  # Path to .env file (absolute path)
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
        # env_ignore_empty=True,  # Don't use empty strings from env
    )
    
    @model_validator(mode='after')
    def load_from_env(self):
        """Load values from os.environ after initialization"""
        # Override with environment variables if they exist
        # Always check os.environ and reload .env if needed
        env_path = Path(__file__).parent.parent.parent / 'infra' / '.env'
        if env_path.exists():
            # Ensure .env is loaded
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key:
                            os.environ[key] = value
        
        # Now read from os.environ
        if 'AWS_REGION' in os.environ:
            self.AWS_REGION = os.environ['AWS_REGION']
        if 'AWS_ACCESS_KEY_ID' in os.environ:
            self.AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
        if 'AWS_SECRET_ACCESS_KEY' in os.environ:
            self.AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
        if 'S3_BUCKET_NAME' in os.environ:
            self.S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
        if 'S3_PREFIX' in os.environ:
            self.S3_PREFIX = os.environ['S3_PREFIX']
        if 'OPENSEARCH_ENDPOINT' in os.environ:
            self.OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
        if 'OPENSEARCH_USERNAME' in os.environ:
            self.OPENSEARCH_USERNAME = os.environ['OPENSEARCH_USERNAME']
        if 'OPENSEARCH_PASSWORD' in os.environ:
            self.OPENSEARCH_PASSWORD = os.environ['OPENSEARCH_PASSWORD']
        if 'BEDROCK_REGION' in os.environ:
            self.BEDROCK_REGION = os.environ['BEDROCK_REGION']
        if 'BEDROCK_EMBEDDING_MODEL' in os.environ:
            self.BEDROCK_EMBEDDING_MODEL = os.environ['BEDROCK_EMBEDDING_MODEL']
        if 'BEDROCK_RERANK_MODEL' in os.environ:
            self.BEDROCK_RERANK_MODEL = os.environ['BEDROCK_RERANK_MODEL']
        if 'SECRETS_MANAGER_SECRET_NAME' in os.environ:
            self.SECRETS_MANAGER_SECRET_NAME = os.environ['SECRETS_MANAGER_SECRET_NAME']
        if 'RATE_LIMIT_PER_MINUTE' in os.environ:
            self.RATE_LIMIT_PER_MINUTE = int(os.environ['RATE_LIMIT_PER_MINUTE'])
        
        # Convert string booleans to actual booleans
        self.USE_MOCK = str(self.USE_MOCK).lower() == "true"
        self.OPENSEARCH_USE_SSL = str(self.OPENSEARCH_USE_SSL).lower() == "true"
        self.OPENSEARCH_VERIFY_CERTS = str(self.OPENSEARCH_VERIFY_CERTS).lower() == "true"
        
        # Load secrets from Secrets Manager if configured
        if self.SECRETS_MANAGER_SECRET_NAME and not self.USE_MOCK:
            self._load_secrets_from_manager()
        
        return self

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


# Create settings instance - BaseSettings will read from os.environ (populated above)
# Verify os.environ has values before creating Settings
if env_path.exists() and not os.environ.get('AWS_REGION'):
    # Re-populate if somehow missing
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value

settings = Settings()

# Debug: Verify settings loaded correctly (only in development)
if os.getenv("DEBUG", "false").lower() == "true":
    print(f"[DEBUG] Settings loaded:")
    print(f"  AWS_REGION: {settings.AWS_REGION}")
    print(f"  OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
    print(f"  S3_BUCKET_NAME: {settings.S3_BUCKET_NAME}")

