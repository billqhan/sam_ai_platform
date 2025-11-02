"""
SQS message processing utilities for Lambda functions.
"""
import json
import logging
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime

from .sqs_utils import sqs_handler, S3EventMessage
from .error_handling import ProcessingError, RetryableError
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class SQSProcessingResult:
    """Result of SQS message processing."""
    message_id: str
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    processing_time_ms: int = 0

class SQSBatchProcessor:
    """Processor for SQS batch events in Lambda functions."""
    
    def __init__(self, message_handler: Callable[[S3EventMessage], Any]):
        """
        Initialize batch processor.
        
        Args:
            message_handler: Function to process individual S3EventMessage objects
        """
        self.message_handler = message_handler
        self.results: List[SQSProcessingResult] = []
    
    def process_lambda_event(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Process Lambda SQS event with batch handling.
        
        Args:
            event: Lambda SQS event
            context: Lambda context
            
        Returns:
            Processing results summary
        """
        logger.info(f"Processing SQS batch with {len(event.get('Records', []))} messages")
        
        self.results = []
        successful_messages = []
        failed_messages = []
        
        for record in event.get('Records', []):
            result = self._process_single_record(record)
            self.results.append(result)
            
            if result.success:
                successful_messages.append(result.message_id)
            else:
                failed_messages.append({
                    'messageId': result.message_id,
                    'error': result.error_message
                })
        
        # Log summary
        total_messages = len(self.results)
        successful_count = len(successful_messages)
        failed_count = len(failed_messages)
        
        logger.info(f"Batch processing complete: {successful_count}/{total_messages} successful")
        
        if failed_messages:
            logger.error(f"Failed messages: {failed_messages}")
        
        return {
            'statusCode': 200 if failed_count == 0 else 207,  # 207 = Multi-Status
            'totalMessages': total_messages,
            'successfulMessages': successful_count,
            'failedMessages': failed_count,
            'results': [result.__dict__ for result in self.results]
        }
    
    def _process_single_record(self, record: Dict[str, Any]) -> SQSProcessingResult:
        """Process a single SQS record."""
        message_id = record.get('messageId', 'unknown')
        start_time = datetime.now()
        
        try:
            # Parse the message body to get S3 event information
            message_body = record.get('body', '')
            s3_event_message = sqs_handler.parse_s3_event_message(message_body)
            
            logger.info(f"Processing message {message_id} for object {s3_event_message.object_key}")
            
            # Get retry count from message attributes
            retry_count = self._get_retry_count(record)
            
            # Process the message using the provided handler
            self.message_handler(s3_event_message)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            logger.info(f"Successfully processed message {message_id} in {processing_time}ms")
            
            return SQSProcessingResult(
                message_id=message_id,
                success=True,
                retry_count=retry_count,
                processing_time_ms=processing_time
            )
            
        except RetryableError as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            error_msg = f"Retryable error processing message {message_id}: {str(e)}"
            logger.warning(error_msg)
            
            return SQSProcessingResult(
                message_id=message_id,
                success=False,
                error_message=error_msg,
                retry_count=self._get_retry_count(record),
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to process message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return SQSProcessingResult(
                message_id=message_id,
                success=False,
                error_message=error_msg,
                retry_count=self._get_retry_count(record),
                processing_time_ms=processing_time
            )
    
    def _get_retry_count(self, record: Dict[str, Any]) -> int:
        """Extract retry count from SQS message attributes."""
        try:
            attributes = record.get('attributes', {})
            return int(attributes.get('ApproximateReceiveCount', '1')) - 1
        except (ValueError, TypeError):
            return 0

class SQSMessageValidator:
    """Validator for SQS message structure and content."""
    
    @staticmethod
    def validate_lambda_sqs_event(event: Dict[str, Any]) -> bool:
        """
        Validate Lambda SQS event structure.
        
        Args:
            event: Lambda event dictionary
            
        Returns:
            True if valid, raises ProcessingError if invalid
        """
        if not isinstance(event, dict):
            raise ProcessingError("Event must be a dictionary")
        
        if 'Records' not in event:
            raise ProcessingError("Event must contain 'Records' field")
        
        records = event['Records']
        if not isinstance(records, list):
            raise ProcessingError("Records must be a list")
        
        if len(records) == 0:
            raise ProcessingError("Records list cannot be empty")
        
        # Validate each record
        for i, record in enumerate(records):
            SQSMessageValidator.validate_sqs_record(record, i)
        
        return True
    
    @staticmethod
    def validate_sqs_record(record: Dict[str, Any], index: int = 0) -> bool:
        """
        Validate individual SQS record structure.
        
        Args:
            record: SQS record dictionary
            index: Record index for error reporting
            
        Returns:
            True if valid, raises ProcessingError if invalid
        """
        required_fields = ['messageId', 'body', 'receiptHandle']
        
        for field in required_fields:
            if field not in record:
                raise ProcessingError(f"Record {index} missing required field: {field}")
        
        # Validate message body is valid JSON
        try:
            json.loads(record['body'])
        except json.JSONDecodeError as e:
            raise ProcessingError(f"Record {index} has invalid JSON body: {str(e)}")
        
        return True
    
    @staticmethod
    def validate_s3_event_message(message: S3EventMessage) -> bool:
        """
        Validate S3 event message content.
        
        Args:
            message: S3EventMessage object
            
        Returns:
            True if valid, raises ProcessingError if invalid
        """
        if not message.bucket_name:
            raise ProcessingError("S3 event message missing bucket name")
        
        if not message.object_key:
            raise ProcessingError("S3 event message missing object key")
        
        if not message.event_name:
            raise ProcessingError("S3 event message missing event name")
        
        # Validate object key format for opportunity files
        if not message.object_key.endswith('.json'):
            raise ProcessingError(f"Object key must end with .json: {message.object_key}")
        
        # Validate event is a creation event
        if not message.event_name.startswith('s3:ObjectCreated'):
            raise ProcessingError(f"Unsupported event type: {message.event_name}")
        
        return True

def create_sqs_processor(message_handler: Callable[[S3EventMessage], Any]) -> SQSBatchProcessor:
    """
    Factory function to create SQS batch processor.
    
    Args:
        message_handler: Function to process S3EventMessage objects
        
    Returns:
        Configured SQSBatchProcessor instance
    """
    return SQSBatchProcessor(message_handler)

def handle_sqs_processing_errors(func: Callable) -> Callable:
    """
    Decorator to handle SQS processing errors consistently.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function with error handling
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RetryableError as e:
            logger.warning(f"Retryable error in {func.__name__}: {str(e)}")
            # Re-raise to trigger SQS retry mechanism
            raise
        except ProcessingError as e:
            logger.error(f"Processing error in {func.__name__}: {str(e)}")
            # Don't re-raise to avoid infinite retries
            return {
                'statusCode': 400,
                'error': str(e),
                'retryable': False
            }
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True)
            # Re-raise unexpected errors to trigger retry
            raise
    
    return wrapper