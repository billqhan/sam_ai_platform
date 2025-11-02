"""
X-Ray tracing utilities for the AI RFP Response Agent.
"""
from typing import Optional, Dict, Any, Callable
from functools import wraps
from .logging_config import get_logger

logger = get_logger(__name__)

# Try to import X-Ray SDK
try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    XRAY_AVAILABLE = True
    
    # Patch AWS SDK calls for automatic tracing
    patch_all()
except ImportError:
    XRAY_AVAILABLE = False
    xray_recorder = None
    logger.warning("X-Ray SDK not available. Tracing will be disabled.")

def trace_lambda_handler(name: Optional[str] = None):
    """Decorator to trace Lambda handler functions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event, context):
            if not XRAY_AVAILABLE:
                return func(event, context)
            
            segment_name = name or f"{context.function_name}_handler"
            
            try:
                with xray_recorder.in_subsegment(segment_name) as subsegment:
                    # Add metadata about the Lambda execution
                    subsegment.put_metadata('lambda_context', {
                        'function_name': context.function_name,
                        'function_version': context.function_version,
                        'request_id': context.aws_request_id,
                        'memory_limit': context.memory_limit_in_mb,
                        'remaining_time': context.get_remaining_time_in_millis()
                    })
                    
                    # Add event information (sanitized)
                    event_info = _sanitize_event_for_tracing(event)
                    subsegment.put_metadata('event', event_info)
                    
                    result = func(event, context)
                    
                    # Mark as successful
                    subsegment.put_annotation('success', True)
                    return result
                    
            except Exception as e:
                if XRAY_AVAILABLE:
                    xray_recorder.current_subsegment().add_exception(e)
                    xray_recorder.current_subsegment().put_annotation('success', False)
                raise
        
        return wrapper
    return decorator

def trace_operation(operation_name: str, service_name: Optional[str] = None):
    """Decorator to trace specific operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not XRAY_AVAILABLE:
                return func(*args, **kwargs)
            
            subsegment_name = f"{service_name}::{operation_name}" if service_name else operation_name
            
            try:
                with xray_recorder.in_subsegment(subsegment_name) as subsegment:
                    # Add operation metadata
                    subsegment.put_annotation('operation', operation_name)
                    if service_name:
                        subsegment.put_annotation('service', service_name)
                    
                    result = func(*args, **kwargs)
                    
                    # Mark as successful
                    subsegment.put_annotation('success', True)
                    return result
                    
            except Exception as e:
                if XRAY_AVAILABLE:
                    xray_recorder.current_subsegment().add_exception(e)
                    xray_recorder.current_subsegment().put_annotation('success', False)
                raise
        
        return wrapper
    return decorator

class TracingContext:
    """Context manager for custom tracing segments."""
    
    def __init__(self, name: str, service_name: Optional[str] = None):
        self.name = name
        self.service_name = service_name
        self.subsegment = None
    
    def __enter__(self):
        if not XRAY_AVAILABLE:
            return self
        
        try:
            self.subsegment = xray_recorder.begin_subsegment(self.name)
            if self.service_name:
                self.subsegment.put_annotation('service', self.service_name)
            return self
        except Exception as e:
            logger.warning(f"Failed to create X-Ray subsegment: {e}")
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not XRAY_AVAILABLE or not self.subsegment:
            return
        
        try:
            if exc_type:
                self.subsegment.add_exception(exc_val)
                self.subsegment.put_annotation('success', False)
            else:
                self.subsegment.put_annotation('success', True)
            
            xray_recorder.end_subsegment()
        except Exception as e:
            logger.warning(f"Failed to end X-Ray subsegment: {e}")
    
    def add_annotation(self, key: str, value: Any):
        """Add annotation to the current subsegment."""
        if XRAY_AVAILABLE and self.subsegment:
            try:
                self.subsegment.put_annotation(key, value)
            except Exception as e:
                logger.warning(f"Failed to add X-Ray annotation: {e}")
    
    def add_metadata(self, key: str, value: Dict[str, Any]):
        """Add metadata to the current subsegment."""
        if XRAY_AVAILABLE and self.subsegment:
            try:
                self.subsegment.put_metadata(key, value)
            except Exception as e:
                logger.warning(f"Failed to add X-Ray metadata: {e}")

def add_trace_annotation(key: str, value: Any):
    """Add annotation to the current X-Ray segment."""
    if not XRAY_AVAILABLE:
        return
    
    try:
        xray_recorder.put_annotation(key, value)
    except Exception as e:
        logger.warning(f"Failed to add X-Ray annotation: {e}")

def add_trace_metadata(key: str, value: Dict[str, Any]):
    """Add metadata to the current X-Ray segment."""
    if not XRAY_AVAILABLE:
        return
    
    try:
        xray_recorder.put_metadata(key, value)
    except Exception as e:
        logger.warning(f"Failed to add X-Ray metadata: {e}")

def _sanitize_event_for_tracing(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize event data for X-Ray tracing (remove sensitive information)."""
    if not isinstance(event, dict):
        return {'event_type': str(type(event))}
    
    sanitized = {}
    
    # Common Lambda event sources
    if 'Records' in event:
        sanitized['source'] = 'SQS/S3/SNS'
        sanitized['record_count'] = len(event['Records'])
        
        # Add first record info (sanitized)
        if event['Records']:
            first_record = event['Records'][0]
            if 'eventSource' in first_record:
                sanitized['event_source'] = first_record['eventSource']
            if 'eventName' in first_record:
                sanitized['event_name'] = first_record['eventName']
    
    elif 'source' in event:
        sanitized['source'] = event.get('source', 'unknown')
        sanitized['detail_type'] = event.get('detail-type', 'unknown')
    
    else:
        sanitized['event_keys'] = list(event.keys())[:10]  # Limit to first 10 keys
    
    return sanitized