"""
Centralized error handling utilities for Lambda functions.
"""
import json
import traceback
import logging
from typing import Dict, Any, Optional
from enum import Enum
import time
import random

class ErrorType(Enum):
    """Classification of error types for handling strategies."""
    TRANSIENT = "transient"
    DATA_ERROR = "data_error"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM_ERROR = "system_error"
    EXTERNAL_API = "external_api"

class RetryableError(Exception):
    """Exception that indicates the operation should be retried."""
    def __init__(self, message: str, error_type: ErrorType, retry_after: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type
        self.retry_after = retry_after

class NonRetryableError(Exception):
    """Exception that indicates the operation should not be retried."""
    def __init__(self, message: str, error_type: ErrorType):
        super().__init__(message)
        self.error_type = error_type

def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, jitter: bool = True) -> float:
    """Calculate exponential backoff delay with optional jitter."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    
    if jitter:
        # Add random jitter (±25% of delay)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = exponential_backoff(attempt, base_delay)
                        time.sleep(delay)
                        continue
                    else:
                        raise
                except NonRetryableError:
                    raise
                except Exception as e:
                    # Treat unknown exceptions as non-retryable by default
                    raise NonRetryableError(f"Unexpected error: {str(e)}", ErrorType.SYSTEM_ERROR)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

def create_error_response(error: Exception, correlation_id: str = None) -> Dict[str, Any]:
    """Create standardized error response for Lambda functions."""
    error_response = {
        'error': True,
        'error_type': getattr(error, 'error_type', ErrorType.SYSTEM_ERROR).value,
        'message': str(error),
        'timestamp': time.time()
    }
    
    if correlation_id:
        error_response['correlation_id'] = correlation_id
    
    # Add stack trace for system errors (but not for business logic errors)
    if isinstance(error, (RetryableError, NonRetryableError)):
        if error.error_type in [ErrorType.SYSTEM_ERROR, ErrorType.EXTERNAL_API]:
            error_response['stack_trace'] = traceback.format_exc()
    else:
        error_response['stack_trace'] = traceback.format_exc()
    
    return error_response

def handle_lambda_error(func):
    """Decorator to handle Lambda function errors consistently."""
    def wrapper(event, context):
        try:
            return func(event, context)
        except (RetryableError, NonRetryableError) as e:
            correlation_id = getattr(context, 'aws_request_id', None)
            error_response = create_error_response(e, correlation_id)
            
            # For SQS triggers, we want to raise the exception to trigger retry/DLQ
            if 'Records' in event and event['Records'][0].get('eventSource') == 'aws:sqs':
                raise
            
            return {
                'statusCode': 500 if e.error_type == ErrorType.SYSTEM_ERROR else 400,
                'body': json.dumps(error_response)
            }
        except Exception as e:
            correlation_id = getattr(context, 'aws_request_id', None)
            system_error = NonRetryableError(f"Unexpected error: {str(e)}", ErrorType.SYSTEM_ERROR)
            error_response = create_error_response(system_error, correlation_id)
            
            return {
                'statusCode': 500,
                'body': json.dumps(error_response)
            }
    
    return wrapper

class CircuitBreaker:
    """Circuit breaker pattern implementation for external service calls."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise RetryableError("Circuit breaker is OPEN", ErrorType.EXTERNAL_API)
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'


class ErrorHandler:
    """
    Comprehensive error handling and logging for LLM match report generation.
    Implements error categorization, detailed logging, and graceful degradation.
    """
    
    def __init__(self, debug_mode: bool = False):
        """
        Initialize error handler with configuration.
        
        Args:
            debug_mode: Enable detailed debug logging
        """
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(__name__)
        self.processing_start_time = None
        self.current_stage = None
        
        # Error categorization mapping
        self.error_categories = {
            # Data access errors
            'NoSuchKey': 'data_access',
            'AccessDenied': 'data_access', 
            'NoSuchBucket': 'data_access',
            'JSONDecodeError': 'data_access',
            'UnicodeDecodeError': 'data_access',
            'FileNotFoundError': 'data_access',
            
            # LLM processing errors
            'ThrottlingException': 'llm_processing',
            'ServiceQuotaExceededException': 'llm_processing',
            'ValidationException': 'llm_processing',
            'ModelTimeoutException': 'llm_processing',
            'ModelNotReadyException': 'llm_processing',
            'InternalServerException': 'llm_processing',
            
            # Knowledge base errors
            'ResourceNotFoundException': 'knowledge_base',
            'ConflictException': 'knowledge_base',
            'ServiceUnavailableException': 'knowledge_base',
        }
    
    def start_processing(self, opportunity_id: str, stage: str = "initialization"):
        """
        Start processing tracking for an opportunity.
        
        Args:
            opportunity_id: The opportunity being processed
            stage: Current processing stage
        """
        self.processing_start_time = time.time()
        self.current_stage = stage
        
        self.logger.info(f"🚀 PROCESSING STARTED: {opportunity_id}")
        self.logger.info(f"📍 Stage: {stage}")
        self.logger.info(f"⏰ Start time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    
    def update_stage(self, stage: str, opportunity_id: str = None):
        """
        Update current processing stage with progress logging.
        
        Args:
            stage: New processing stage
            opportunity_id: Optional opportunity ID for context
        """
        elapsed_time = time.time() - self.processing_start_time if self.processing_start_time else 0
        
        self.logger.info(f"📍 STAGE UPDATE: {self.current_stage} → {stage}")
        if opportunity_id:
            self.logger.info(f"🔍 Opportunity: {opportunity_id}")
        self.logger.info(f"⏱️  Elapsed time: {elapsed_time:.2f}s")
        
        self.current_stage = stage
    
    def log_llm_request(self, model_id: str, prompt_length: int, request_params: dict = None):
        """
        Log LLM request details when DEBUG_MODE is enabled.
        Implements Requirement 5.1: Log request parameters and response metadata.
        
        Args:
            model_id: The model being called
            prompt_length: Length of the prompt in characters
            request_params: Additional request parameters
        """
        # Always log basic request info for monitoring
        self.logger.info(f"🤖 LLM REQUEST: {model_id} (prompt: {prompt_length} chars)")
        
        if self.debug_mode:
            self.logger.debug(f"🤖 LLM REQUEST DETAILS:")
            self.logger.debug(f"  Model: {model_id}")
            self.logger.debug(f"  Prompt length: {prompt_length} characters")
            self.logger.debug(f"  Request timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            if request_params:
                # Log safe parameters (avoid logging sensitive data)
                safe_params = {
                    'max_tokens': request_params.get('max_tokens'),
                    'temperature': request_params.get('temperature'),
                    'anthropic_version': request_params.get('anthropic_version'),
                    'top_p': request_params.get('top_p'),
                    'top_k': request_params.get('top_k')
                }
                self.logger.debug(f"  Parameters: {safe_params}")
                
                # Log token usage estimates if available
                if 'estimated_tokens' in request_params:
                    self.logger.debug(f"  Estimated tokens: {request_params['estimated_tokens']}")
    
    def log_llm_response(self, model_id: str, response_length: int, processing_time: float, 
                        response_metadata: dict = None):
        """
        Log LLM response details when DEBUG_MODE is enabled.
        Implements Requirement 5.1: Log request parameters and response metadata.
        
        Args:
            model_id: The model that responded
            response_length: Length of response in characters
            processing_time: Time taken for the request
            response_metadata: Additional response metadata
        """
        # Always log basic response info for monitoring
        self.logger.info(f"✅ LLM RESPONSE: {model_id} ({response_length} chars, {processing_time:.2f}s)")
        
        if self.debug_mode:
            self.logger.debug(f"🤖 LLM RESPONSE DETAILS:")
            self.logger.debug(f"  Model: {model_id}")
            self.logger.debug(f"  Response length: {response_length} characters")
            self.logger.debug(f"  Processing time: {processing_time:.2f}s")
            self.logger.debug(f"  Response timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            if response_metadata:
                # Log safe metadata
                safe_metadata = {
                    'usage': response_metadata.get('usage'),
                    'stop_reason': response_metadata.get('stop_reason'),
                    'model': response_metadata.get('model'),
                    'input_tokens': response_metadata.get('input_tokens'),
                    'output_tokens': response_metadata.get('output_tokens')
                }
                self.logger.debug(f"  Metadata: {safe_metadata}")
                
                # Log performance metrics
                if processing_time > 0:
                    chars_per_second = response_length / processing_time
                    self.logger.debug(f"  Performance: {chars_per_second:.1f} chars/second")
    
    def categorize_error(self, error: Exception) -> str:
        """
        Categorize error into data_access, llm_processing, or knowledge_base.
        
        Args:
            error: The exception to categorize
            
        Returns:
            Error category string
        """
        error_name = type(error).__name__
        error_message = str(error).lower()
        
        # Check direct error type mapping
        if error_name in self.error_categories:
            return self.error_categories[error_name]
        
        # Check for AWS error codes in ClientError
        if hasattr(error, 'response') and 'Error' in error.response:
            error_code = error.response['Error']['Code']
            if error_code in self.error_categories:
                return self.error_categories[error_code]
        
        # Pattern matching for error messages
        if any(pattern in error_message for pattern in ['s3', 'bucket', 'key', 'file not found']):
            return 'data_access'
        elif any(pattern in error_message for pattern in ['bedrock', 'model', 'llm', 'throttl']):
            return 'llm_processing'
        elif any(pattern in error_message for pattern in ['knowledge', 'retriev', 'vector']):
            return 'knowledge_base'
        
        # Default to system error
        return 'system_error'
    
    def create_error_record(self, opportunity_id: str, error: Exception, 
                          processing_stage: str = None) -> dict:
        """
        Create standardized error record for failed processing.
        
        Args:
            opportunity_id: The opportunity ID that failed
            error: The exception that occurred
            processing_stage: Stage where error occurred
            
        Returns:
            Error record dictionary
        """
        error_category = self.categorize_error(error)
        current_time = time.time()
        
        error_record = {
            'solicitationNumber': opportunity_id,
            'error': str(error),
            'error_type': error_category,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(current_time)),
            'processing_stage': processing_stage or self.current_stage or 'unknown',
            'processing_time': current_time - self.processing_start_time if self.processing_start_time else 0
        }
        
        # Add detailed error information for debugging
        if self.debug_mode:
            error_record['debug_info'] = {
                'error_class': type(error).__name__,
                'stack_trace': traceback.format_exc(),
                'error_args': getattr(error, 'args', [])
            }
            
            # Add AWS error details if available
            if hasattr(error, 'response'):
                error_record['debug_info']['aws_error'] = {
                    'error_code': error.response.get('Error', {}).get('Code'),
                    'error_message': error.response.get('Error', {}).get('Message'),
                    'request_id': error.response.get('ResponseMetadata', {}).get('RequestId')
                }
        
        return error_record
    
    def log_error(self, opportunity_id: str, error: Exception, context: dict = None):
        """
        Log error with comprehensive details.
        
        Args:
            opportunity_id: The opportunity ID being processed
            error: The exception that occurred
            context: Additional context information
        """
        error_category = self.categorize_error(error)
        
        self.logger.error(f"❌ ERROR in {self.current_stage or 'unknown stage'}")
        self.logger.error(f"🔍 Opportunity ID: {opportunity_id}")
        self.logger.error(f"📂 Error Category: {error_category}")
        self.logger.error(f"💥 Error: {str(error)}")
        
        if context:
            self.logger.error(f"📋 Context: {context}")
        
        # Log stack trace for system errors or in debug mode
        if error_category == 'system_error' or self.debug_mode:
            self.logger.error(f"📚 Stack trace:\n{traceback.format_exc()}")
        
        # Log AWS-specific error details
        if hasattr(error, 'response') and 'Error' in error.response:
            aws_error = error.response['Error']
            self.logger.error(f"☁️  AWS Error Code: {aws_error.get('Code')}")
            self.logger.error(f"☁️  AWS Error Message: {aws_error.get('Message')}")
    
    def handle_graceful_degradation(self, error: Exception, fallback_data: dict = None) -> dict:
        """
        Implement graceful degradation when partial data is available.
        
        Args:
            error: The exception that occurred
            fallback_data: Partial data that was successfully processed
            
        Returns:
            Degraded result with available data
        """
        error_category = self.categorize_error(error)
        
        self.logger.warning(f"🔄 GRACEFUL DEGRADATION: {error_category}")
        self.logger.warning(f"💡 Using partial data with error indicators")
        
        # Create degraded result based on available data
        degraded_result = fallback_data or {}
        
        # Add error indicators
        degraded_result.update({
            'processing_status': 'partial_failure',
            'error_category': error_category,
            'error_message': str(error),
            'degradation_applied': True,
            'degradation_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        })
        
        # Apply category-specific degradation
        if error_category == 'llm_processing':
            degraded_result.update({
                'score': 0.0,
                'rationale': f'LLM processing failed: {str(error)}. Manual review required.',
                'enhanced_description': degraded_result.get('original_description', 'LLM processing failed'),
                'opportunity_required_skills': ['Manual review required - LLM processing failed']
            })
        elif error_category == 'knowledge_base':
            degraded_result.update({
                'kb_retrieval_results': [],
                'citations': [],
                'company_skills': ['Knowledge base unavailable - manual review required']
            })
        elif error_category == 'data_access':
            degraded_result.update({
                'enhanced_description': 'Data access failed - original data unavailable',
                'attachments_processed': 0
            })
        
        return degraded_result
    
    def log_processing_summary(self, opportunity_id: str, success: bool, 
                             match_score: float = None, processing_details: dict = None):
        """
        Log comprehensive processing summary.
        
        Args:
            opportunity_id: The opportunity that was processed
            success: Whether processing was successful
            match_score: Final match score if available
            processing_details: Additional processing metrics
        """
        total_time = time.time() - self.processing_start_time if self.processing_start_time else 0
        
        status_emoji = "✅" if success else "❌"
        self.logger.info(f"{status_emoji} PROCESSING COMPLETE: {opportunity_id}")
        self.logger.info(f"⏱️  Total processing time: {total_time:.2f}s")
        self.logger.info(f"🎯 Final stage: {self.current_stage}")
        
        if match_score is not None:
            self.logger.info(f"📊 Match score: {match_score}")
        
        if processing_details:
            self.logger.info(f"📋 Processing details:")
            for key, value in processing_details.items():
                self.logger.info(f"   {key}: {value}")
        
        # Reset processing state
        self.processing_start_time = None
        self.current_stage = None
    
    def log_progress_update(self, opportunity_id: str, stage: str, progress_info: dict = None):
        """
        Log progress updates for monitoring long-running processes.
        Implements Requirement 3.3: Log progress updates for monitoring.
        
        Args:
            opportunity_id: The opportunity being processed
            stage: Current processing stage
            progress_info: Additional progress information
        """
        elapsed_time = time.time() - self.processing_start_time if self.processing_start_time else 0
        
        self.logger.info(f"⏳ PROGRESS: {opportunity_id} - {stage}")
        self.logger.info(f"⏱️  Elapsed: {elapsed_time:.1f}s")
        
        if progress_info:
            for key, value in progress_info.items():
                self.logger.info(f"   {key}: {value}")
    
    def log_s3_operation(self, operation: str, bucket: str, key: str, 
                        success: bool = True, error: Exception = None, 
                        file_size: int = None):
        """
        Log S3 operations with comprehensive details.
        Implements Requirement 5.3: Log S3 file reading failures with bucket/key details.
        
        Args:
            operation: The S3 operation (read, write, delete, etc.)
            bucket: S3 bucket name
            key: S3 object key
            success: Whether the operation was successful
            error: Exception if operation failed
            file_size: Size of file in bytes (if available)
        """
        status_emoji = "✅" if success else "❌"
        
        if success:
            size_info = f" ({file_size} bytes)" if file_size else ""
            self.logger.info(f"{status_emoji} S3 {operation.upper()}: s3://{bucket}/{key}{size_info}")
        else:
            self.logger.error(f"{status_emoji} S3 {operation.upper()} FAILED: s3://{bucket}/{key}")
            
            if error:
                error_category = self.categorize_error(error)
                self.logger.error(f"📂 Error Category: {error_category}")
                self.logger.error(f"💥 Error: {str(error)}")
                
                # Log AWS S3-specific error details
                if hasattr(error, 'response') and 'Error' in error.response:
                    aws_error = error.response['Error']
                    self.logger.error(f"☁️  AWS S3 Error Code: {aws_error.get('Code')}")
                    self.logger.error(f"☁️  AWS S3 Error Message: {aws_error.get('Message')}")
                    
                    # Log specific S3 error guidance
                    if aws_error.get('Code') == 'NoSuchKey':
                        self.logger.error(f"🔍 File does not exist: s3://{bucket}/{key}")
                    elif aws_error.get('Code') == 'NoSuchBucket':
                        self.logger.error(f"🔍 Bucket does not exist: {bucket}")
                    elif aws_error.get('Code') == 'AccessDenied':
                        self.logger.error(f"🔍 Access denied to: s3://{bucket}/{key}")
        
        if self.debug_mode and success:
            self.logger.debug(f"🔍 S3 {operation.upper()} DETAILS:")
            self.logger.debug(f"  Bucket: {bucket}")
            self.logger.debug(f"  Key: {key}")
            if file_size:
                self.logger.debug(f"  Size: {file_size} bytes ({file_size/1024:.1f} KB)")
            self.logger.debug(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    
    def log_knowledge_base_request(self, query_text: str, knowledge_base_id: str, 
                                  request_params: dict = None):
        """
        Log Knowledge Base request details.
        
        Args:
            query_text: The query text being sent
            knowledge_base_id: The knowledge base ID
            request_params: Additional request parameters
        """
        self.logger.info(f"🔍 KB REQUEST: {knowledge_base_id} (query: {len(query_text)} chars)")
        
        if self.debug_mode:
            self.logger.debug(f"🔍 KB REQUEST DETAILS:")
            self.logger.debug(f"  Knowledge Base ID: {knowledge_base_id}")
            self.logger.debug(f"  Query length: {len(query_text)} characters")
            self.logger.debug(f"  Query preview: {query_text[:100]}...")
            self.logger.debug(f"  Request timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            if request_params:
                safe_params = {
                    'numberOfResults': request_params.get('numberOfResults'),
                    'retrievalConfiguration': request_params.get('retrievalConfiguration')
                }
                self.logger.debug(f"  Parameters: {safe_params}")
    
    def log_knowledge_base_response(self, knowledge_base_id: str, results_count: int, 
                                   processing_time: float, response_metadata: dict = None):
        """
        Log Knowledge Base response details.
        
        Args:
            knowledge_base_id: The knowledge base ID
            results_count: Number of results returned
            processing_time: Time taken for the request
            response_metadata: Additional response metadata
        """
        self.logger.info(f"✅ KB RESPONSE: {knowledge_base_id} ({results_count} results, {processing_time:.2f}s)")
        
        if self.debug_mode:
            self.logger.debug(f"🔍 KB RESPONSE DETAILS:")
            self.logger.debug(f"  Knowledge Base ID: {knowledge_base_id}")
            self.logger.debug(f"  Results count: {results_count}")
            self.logger.debug(f"  Processing time: {processing_time:.2f}s")
            self.logger.debug(f"  Response timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            if response_metadata:
                safe_metadata = {
                    'retrievalResults': response_metadata.get('retrievalResults'),
                    'nextToken': response_metadata.get('nextToken')
                }
                self.logger.debug(f"  Metadata: {safe_metadata}")
    
    def log_knowledge_base_error(self, opportunity_id: str, error: Exception, 
                                query_text: str, knowledge_base_id: str):
        """
        Log Knowledge Base query errors with comprehensive details.
        
        Args:
            opportunity_id: The opportunity ID being processed
            error: The exception that occurred
            query_text: The query that failed
            knowledge_base_id: The knowledge base ID
        """
        error_category = self.categorize_error(error)
        
        self.logger.error(f"❌ KB QUERY ERROR: {knowledge_base_id}")
        self.logger.error(f"🔍 Opportunity ID: {opportunity_id}")
        self.logger.error(f"📂 Error Category: {error_category}")
        self.logger.error(f"💥 Error: {str(error)}")
        self.logger.error(f"🔍 Query preview: {query_text[:200]}...")
        
        # Log AWS-specific error details
        if hasattr(error, 'response') and 'Error' in error.response:
            aws_error = error.response['Error']
            self.logger.error(f"☁️  AWS KB Error Code: {aws_error.get('Code')}")
            self.logger.error(f"☁️  AWS KB Error Message: {aws_error.get('Message')}")
            
            # Log specific KB error guidance
            if aws_error.get('Code') == 'ResourceNotFoundException':
                self.logger.error(f"🔍 Knowledge Base not found: {knowledge_base_id}")
            elif aws_error.get('Code') == 'ValidationException':
                self.logger.error(f"🔍 Invalid query or parameters")
            elif aws_error.get('Code') == 'ThrottlingException':
                self.logger.error(f"🔍 Knowledge Base query throttled")
        
        if self.debug_mode:
            self.logger.error(f"📚 Stack trace:\n{traceback.format_exc()}")