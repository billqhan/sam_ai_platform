"""
Shared utilities for sam-produce-user-report lambda function.
"""

import logging
import json
import os
import boto3
from typing import Dict, Any
from dataclasses import dataclass

# Configure logging
def get_logger(name: str) -> logging.Logger:
    """Get configured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Add correlation_id attribute for compatibility
    if not hasattr(logger, 'correlation_id'):
        logger.correlation_id = 'unknown'
    
    return logger

# Error handling decorators
def handle_lambda_error(func):
    """Decorator for Lambda error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Lambda error: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': str(e),
                    'message': 'Lambda function failed'
                })
            }
    return wrapper

def handle_aws_error(func):
    """Decorator for AWS service error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"AWS error: {str(e)}")
            raise
    return wrapper

# Exception classes
class RetryableError(Exception):
    """Error that can be retried."""
    pass

class NonRetryableError(Exception):
    """Error that should not be retried."""
    pass

# Configuration
@dataclass
class S3Config:
    """S3 bucket configuration."""
    sam_opportunity_responses: str

@dataclass
class ConfigManager:
    """Configuration manager."""
    
    def __init__(self):
        self._s3_config = None
    
    @property
    def s3(self) -> S3Config:
        if self._s3_config is None:
            self._s3_config = S3Config(
                sam_opportunity_responses=os.environ.get('OUTPUT_BUCKET', 'sam-opportunity-responses')
            )
        return self._s3_config
    
    def get_company_info(self) -> Dict[str, str]:
        """Get company information."""
        return {
            'name': os.environ.get('COMPANY_NAME', 'Your Company'),
            'contact': os.environ.get('COMPANY_CONTACT', 'contact@yourcompany.com')
        }

# AWS clients
class AWSClients:
    """AWS service clients."""
    
    def __init__(self):
        self._s3 = None
        self._bedrock_agent = None
    
    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client('s3')
        return self._s3
    
    @property
    def bedrock_agent(self):
        if self._bedrock_agent is None:
            self._bedrock_agent = boto3.client("bedrock-agent-runtime")
        return self._bedrock_agent

# Global instances
config = ConfigManager()
aws_clients = AWSClients()

# Export all needed items
__all__ = [
    'get_logger',
    'handle_lambda_error', 
    'handle_aws_error',
    'config',
    'aws_clients',
    'RetryableError',
    'NonRetryableError'
]