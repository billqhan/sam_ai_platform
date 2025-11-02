"""
Centralized error handling utilities for Lambda functions.
"""
import json
import traceback
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