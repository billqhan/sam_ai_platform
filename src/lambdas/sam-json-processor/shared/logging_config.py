"""
Standardized logging configuration for all Lambda functions.
Includes structured JSON logging, correlation IDs, and X-Ray tracing support.
"""
import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

# Try to import X-Ray SDK for tracing support
try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all
    XRAY_AVAILABLE = True
    # Patch AWS SDK calls for automatic tracing
    patch_all()
except ImportError:
    XRAY_AVAILABLE = False
    xray_recorder = None

class StructuredLogger:
    """Structured JSON logger for Lambda functions with X-Ray tracing support."""
    
    def __init__(self, name: str, level: str = 'INFO', context=None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create console handler with JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        
        # Generate correlation ID for this execution
        self.correlation_id = str(uuid.uuid4())
        
        # Lambda context information
        self.function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        self.function_version = os.environ.get('AWS_LAMBDA_FUNCTION_VERSION', 'unknown')
        self.request_id = getattr(context, 'aws_request_id', 'unknown') if context else 'unknown'
        
        # X-Ray tracing information
        self.trace_id = None
        self.segment_id = None
        if XRAY_AVAILABLE and xray_recorder:
            try:
                current_segment = xray_recorder.current_segment()
                if current_segment:
                    self.trace_id = current_segment.trace_id
                    self.segment_id = current_segment.id
            except Exception:
                # X-Ray not available or no active segment
                pass
    
    def _create_log_entry(self, level: str, message: str, **kwargs) -> Dict[str, Any]:
        """Create structured log entry with tracing information."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message,
            'correlation_id': self.correlation_id,
            'function_name': self.function_name,
            'function_version': self.function_version,
            'request_id': self.request_id
        }
        
        # Add X-Ray tracing information if available
        if self.trace_id:
            log_entry['trace_id'] = self.trace_id
        if self.segment_id:
            log_entry['segment_id'] = self.segment_id
            
        # Add current X-Ray segment info if different from initialization
        if XRAY_AVAILABLE and xray_recorder:
            try:
                current_segment = xray_recorder.current_segment()
                if current_segment and current_segment.id != self.segment_id:
                    log_entry['current_segment_id'] = current_segment.id
            except Exception:
                pass
        
        # Add any additional context
        if kwargs:
            log_entry['context'] = kwargs
            
        return log_entry
    
    def info(self, message: str, **kwargs):
        """Log info message with structured format."""
        log_entry = self._create_log_entry('INFO', message, **kwargs)
        self.logger.info(json.dumps(log_entry))
    
    def error(self, message: str, **kwargs):
        """Log error message with structured format."""
        log_entry = self._create_log_entry('ERROR', message, **kwargs)
        self.logger.error(json.dumps(log_entry))
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured format."""
        log_entry = self._create_log_entry('WARNING', message, **kwargs)
        self.logger.warning(json.dumps(log_entry))
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured format."""
        log_entry = self._create_log_entry('DEBUG', message, **kwargs)
        self.logger.debug(json.dumps(log_entry))
    
    def metric(self, metric_name: str, value: float, unit: str = 'Count', **kwargs):
        """Log custom metric for CloudWatch monitoring."""
        log_entry = self._create_log_entry('INFO', f'METRIC_{metric_name}', 
                                         metric_name=metric_name, 
                                         metric_value=value, 
                                         metric_unit=unit, 
                                         **kwargs)
        self.logger.info(json.dumps(log_entry))
    
    def performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics."""
        log_entry = self._create_log_entry('INFO', f'PERFORMANCE_{operation}', 
                                         operation=operation, 
                                         duration_ms=duration_ms, 
                                         **kwargs)
        self.logger.info(json.dumps(log_entry))
    
    def api_call(self, service: str, operation: str, success: bool, duration_ms: float = None, **kwargs):
        """Log API call metrics."""
        message = f'API_CALL_{"SUCCESS" if success else "FAILED"}'
        context = {
            'service': service,
            'operation': operation,
            'success': success
        }
        if duration_ms is not None:
            context['duration_ms'] = duration_ms
        context.update(kwargs)
        
        log_entry = self._create_log_entry('INFO' if success else 'ERROR', message, **context)
        if success:
            self.logger.info(json.dumps(log_entry))
        else:
            self.logger.error(json.dumps(log_entry))
    
    def business_event(self, event_type: str, **kwargs):
        """Log business events for monitoring."""
        log_entry = self._create_log_entry('INFO', event_type, **kwargs)
        self.logger.info(json.dumps(log_entry))

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for CloudWatch logs."""
    
    def format(self, record):
        # If the message is already a JSON string, return it as-is
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            try:
                json.loads(message)
                return message
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Otherwise, create a basic JSON structure
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name
        }
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def get_logger(name: str, level: str = None, context=None) -> StructuredLogger:
    """Get a structured logger instance with optional Lambda context."""
    log_level = level or os.environ.get('LOG_LEVEL', 'INFO')
    return StructuredLogger(name, log_level, context)

class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, logger: StructuredLogger, operation: str, **kwargs):
        self.logger = logger
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000
            self.logger.performance(self.operation, duration, **self.kwargs)
            
            # Add X-Ray annotation if available
            if XRAY_AVAILABLE and xray_recorder:
                try:
                    xray_recorder.put_annotation(f'{self.operation}_duration_ms', duration)
                except Exception:
                    pass