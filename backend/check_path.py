"""Check path resolution"""
from pathlib import Path

config_file = Path(__file__).parent / 'app' / 'core' / 'config.py'
print(f"Config file: {config_file.resolve()}")
print(f"Config parent: {config_file.parent}")
print(f"Config parent.parent: {config_file.parent.parent}")
print(f"Config parent.parent.parent: {config_file.parent.parent.parent}")
print()

expected_env = config_file.parent.parent.parent / 'infra' / '.env'
print(f"Expected .env (from config.py logic): {expected_env.resolve()}")
print(f"Expected .env exists: {expected_env.exists()}")
print()

actual_env = Path(__file__).parent.parent / 'infra' / '.env'
print(f"Actual .env (from project root): {actual_env.resolve()}")
print(f"Actual .env exists: {actual_env.exists()}")

