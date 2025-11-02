import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import time
import random
import requests
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class EnvironmentConfig:
    """Environment variable configuration and validation"""
    
    def __init__(self):
        self.sam_api_url = self._get_required_env('SAM_API_URL')
        self.sam_api_key = self._get_required_env('SAM_API_KEY')
        self.output_bucket = self._get_required_env('OUTPUT_BUCKET')
        self.log_bucket = self._get_required_env('LOG_BUCKET')
        self.api_limit = int(self._get_env('API_LIMIT', '1000'))
        self.override_date_format = self._get_env('OVERRIDE_DATE_FORMAT', 'MM/DD/YYYY')
        self.override_posted_from = self._get_env('OVERRIDE_POSTED_FROM')
        self.override_posted_to = self._get_env('OVERRIDE_POSTED_TO')
        
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get optional environment variable with default"""
        return os.environ.get(key, default)


class SamGovApiClient:
    """SAM.gov API client with authentication and request handling"""
    
    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': config.sam_api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'AI-RFP-Response-Agent/1.0'
        })
        
    def get_opportunities(self) -> Dict[str, Any]:
        """
        Retrieve opportunities from SAM.gov API
        
        Returns:
            Dict containing API response data
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If response validation fails
        """
        # Determine date range
        posted_from, posted_to = self._get_date_range()
        
        # Build API parameters
        params = {
            'limit': self.config.api_limit,
            'postedFrom': posted_from,
            'postedTo': posted_to,
            'ptype': 'o'  # Opportunities only
        }
        
        logger.info(f"Making SAM.gov API request with params: {params}")
        
        try:
            response = self.session.get(
                self.config.sam_api_url,
                params=params,
                timeout=300  # 5 minute timeout
            )
            response.raise_for_status()
            
            # Parse and validate response
            data = response.json()
            self._validate_response(data)
            
            logger.info(f"Successfully retrieved {len(data.get('opportunitiesData', []))} opportunities")
            return data
            
        except requests.exceptions.Timeout:
            logger.error("SAM.gov API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"SAM.gov API request failed: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SAM.gov API response as JSON: {str(e)}")
            raise ValueError("Invalid JSON response from SAM.gov API")
    
    def _get_date_range(self) -> tuple[str, str]:
        """
        Get date range for API request based on configuration
        
        Returns:
            Tuple of (posted_from, posted_to) in MM/DD/YYYY format
        """
        if self.config.override_posted_from and self.config.override_posted_to:
            logger.info("Using custom date override")
            return self.config.override_posted_from, self.config.override_posted_to
        
        # Default: previous day
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%m/%d/%Y')
        
        logger.info(f"Using default date range: {date_str}")
        return date_str, date_str
    
    def _validate_response(self, data: Dict[str, Any]) -> None:
        """
        Validate SAM.gov API response structure
        
        Args:
            data: Response data to validate
            
        Raises:
            ValueError: If response structure is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("API response is not a valid JSON object")
        
        if 'opportunitiesData' not in data:
            raise ValueError("API response missing 'opportunitiesData' field")
        
        opportunities = data['opportunitiesData']
        if not isinstance(opportunities, list):
            raise ValueError("'opportunitiesData' field is not a list")
        
        logger.info(f"Response validation passed: {len(opportunities)} opportunities found")


class S3StorageClient:
    """S3 client for storing SAM opportunities and error logging"""
    
    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.s3_client = boto3.client('s3')
        
    def store_opportunities(self, data: Dict[str, Any]) -> str:
        """
        Store SAM opportunities data to S3 with retry logic
        
        Args:
            data: Opportunities data to store
            
        Returns:
            S3 object key of stored file
            
        Raises:
            ClientError: If S3 operation fails after retries
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        object_key = f"SAM_Opportunities_{timestamp}.json"
        
        # Convert data to JSON string
        json_data = json.dumps(data, indent=2, default=str)
        
        # Store with retry logic
        return self._store_with_retry(
            bucket=self.config.output_bucket,
            key=object_key,
            data=json_data,
            content_type='application/json'
        )
    
    def log_error(self, error_message: str, error_details: Dict[str, Any] = None) -> None:
        """
        Log error to S3 error logging bucket
        
        Args:
            error_message: Error message to log
            error_details: Additional error details
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            object_key = f"error_{timestamp}.json"
            
            error_log = {
                'timestamp': datetime.now().isoformat(),
                'error_message': error_message,
                'error_details': error_details or {},
                'function_name': 'sam-gov-daily-download'
            }
            
            json_data = json.dumps(error_log, indent=2, default=str)
            
            self._store_with_retry(
                bucket=self.config.log_bucket,
                key=object_key,
                data=json_data,
                content_type='application/json'
            )
            
            logger.info(f"Error logged to S3: {object_key}")
            
        except Exception as e:
            logger.error(f"Failed to log error to S3: {str(e)}")
    
    def _store_with_retry(self, bucket: str, key: str, data: str, content_type: str) -> str:
        """
        Store data to S3 with exponential backoff retry (1 retry maximum)
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            data: Data to store
            content_type: Content type
            
        Returns:
            S3 object key
            
        Raises:
            ClientError: If all retry attempts fail
        """
        max_retries = 1
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Storing to S3: s3://{bucket}/{key} (attempt {attempt + 1})")
                
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=data.encode('utf-8'),
                    ContentType=content_type,
                    ServerSideEncryption='AES256'
                )
                
                logger.info(f"Successfully stored to S3: s3://{bucket}/{key}")
                return key
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.warning(f"S3 operation failed (attempt {attempt + 1}): {error_code} - {str(e)}")
                
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All retry attempts failed for S3 operation")
                    raise

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for SAM.gov daily download
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        Dict containing status and message
    """
    try:
        logger.info("Starting SAM.gov daily download Lambda function")
        logger.info(f"Event: {json.dumps(event)}")
        
        # Initialize configuration
        config = EnvironmentConfig()
        logger.info("Environment configuration validated successfully")
        
        # Initialize clients
        api_client = SamGovApiClient(config)
        s3_client = S3StorageClient(config)
        
        # Retrieve opportunities from SAM.gov with no retry logic
        opportunities_data = None
        max_retries = 0
        
        for attempt in range(max_retries + 1):
            try:
                opportunities_data = api_client.get_opportunities()
                break
            except Exception as e:
                logger.warning(f"API request failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries:
                    delay = 2.0 * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Retrying API request in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    error_details = {
                        'error_type': type(e).__name__,
                        'attempts': attempt + 1,
                        'api_url': config.sam_api_url
                    }
                    s3_client.log_error(f"Failed to retrieve data from SAM.gov API: {str(e)}", error_details)
                    raise
        
        # Store opportunities data to S3
        object_key = s3_client.store_opportunities(opportunities_data)
        
        opportunities_count = len(opportunities_data.get('opportunitiesData', []))
        logger.info(f"Successfully processed {opportunities_count} opportunities")
        
        logger.info("SAM.gov daily download completed successfully")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'SAM.gov daily download completed successfully',
                'requestId': context.aws_request_id if context else 'local-test',
                'opportunitiesCount': opportunities_count,
                's3ObjectKey': object_key
            })
        }
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Configuration error',
                'message': str(e)
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        
        # Log error to S3 if possible
        try:
            if 'config' in locals():
                s3_client = S3StorageClient(config)
                error_details = {
                    'error_type': type(e).__name__,
                    'function_name': 'sam-gov-daily-download',
                    'request_id': context.aws_request_id if context else 'local-test'
                }
                s3_client.log_error(f"Lambda function error: {str(e)}", error_details)
        except Exception as log_error:
            logger.error(f"Failed to log error to S3: {str(log_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }