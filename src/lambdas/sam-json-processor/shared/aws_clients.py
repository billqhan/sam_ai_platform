"""
AWS service clients with standardized configuration and error handling.
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from typing import Optional
from .logging_config import get_logger
from .tracing import TracingContext

logger = get_logger(__name__)

class AWSClientManager:
    """Centralized AWS client management with retry configuration."""
    
    def __init__(self, region_name: str = 'us-east-1'):
        self.region_name = region_name
        self.config = Config(
            region_name=region_name,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
        self._s3_client = None
        self._sqs_client = None
        self._bedrock_client = None
        self._bedrock_agent_runtime_client = None
    
    @property
    def s3(self):
        """Get S3 client with retry configuration."""
        if self._s3_client is None:
            with TracingContext("initialize_s3_client", "AWS"):
                logger.info("Initializing S3 client", region=self.region_name)
                self._s3_client = boto3.client('s3', config=self.config)
                logger.debug("S3 client initialized successfully")
        return self._s3_client
    
    @property
    def sqs(self):
        """Get SQS client with retry configuration."""
        if self._sqs_client is None:
            with TracingContext("initialize_sqs_client", "AWS"):
                logger.info("Initializing SQS client", region=self.region_name)
                self._sqs_client = boto3.client('sqs', config=self.config)
                logger.debug("SQS client initialized successfully")
        return self._sqs_client
    
    @property
    def bedrock(self):
        """Get Bedrock client with retry configuration."""
        if self._bedrock_client is None:
            with TracingContext("initialize_bedrock_client", "AWS"):
                logger.info("Initializing Bedrock client", region=self.region_name)
                self._bedrock_client = boto3.client('bedrock-runtime', config=self.config)
                logger.debug("Bedrock client initialized successfully")
        return self._bedrock_client
    
    @property
    def bedrock_agent_runtime(self):
        """Get Bedrock Agent Runtime client for knowledge base queries."""
        if self._bedrock_agent_runtime_client is None:
            self._bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', config=self.config)
        return self._bedrock_agent_runtime_client

def handle_aws_error(func):
    """Decorator to handle AWS service errors consistently."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS ClientError in {func.__name__}: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"AWS BotoCoreError in {func.__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            raise
    return wrapper

# Global client manager instance
aws_clients = AWSClientManager()