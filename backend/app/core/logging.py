"""
Structured Logging Configuration
Sends logs to CloudWatch when deployed, console when local
"""
import logging
import sys
import os
from pythonjsonlogger import jsonlogger
import watchtower


def setup_logging():
    """Setup structured logging with CloudWatch support"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
    )
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)
    
    # CloudWatch handler (only if not in mock mode and AWS credentials available)
    if os.getenv("USE_MOCK", "true").lower() != "true":
        try:
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group_name="/aws/lambda/resume-matching-api",
                stream_name="app",
                use_queues=False
            )
            cloudwatch_handler.setFormatter(json_formatter)
            root_logger.addHandler(cloudwatch_handler)
        except Exception as e:
            # If CloudWatch setup fails, continue with console logging
            logging.warning(f"CloudWatch logging not available: {e}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

