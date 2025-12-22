"""Check if .env is loaded correctly"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Check .env file directly
env_path = Path(__file__).parent.parent / 'infra' / '.env'
print(f"Env file path: {env_path.resolve()}")
print(f"Env file exists: {env_path.exists()}")
print()

if env_path.exists():
    print("Reading .env file directly:")
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if 'OPENSEARCH' in key or 'AWS' in key:
                    print(f"  {key} = {value[:50]}..." if len(value) > 50 else f"  {key} = {value}")
    print()

print("Checking os.environ:")
print(f"  OPENSEARCH_ENDPOINT: {os.environ.get('OPENSEARCH_ENDPOINT', 'NOT SET')}")
print(f"  AWS_ACCESS_KEY_ID: {os.environ.get('AWS_ACCESS_KEY_ID', 'NOT SET')[:20]}...")
print()

print("Loading settings...")
from app.core.config import settings
print(f"  settings.OPENSEARCH_ENDPOINT: {settings.OPENSEARCH_ENDPOINT}")
print(f"  settings.AWS_REGION: {settings.AWS_REGION}")
print(f"  settings.AWS_ACCESS_KEY_ID: {settings.AWS_ACCESS_KEY_ID[:20] if settings.AWS_ACCESS_KEY_ID else 'NOT SET'}...")

