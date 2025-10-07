"""
Standardized logging configuration for all Lambda functions.
"""
import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

class StructuredLogger:
    """Structured JSON logger for Lambda functions."""
    
    def __init__(self, name: str, level: str = 'INFO'):
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
        self.request_id = os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', 'unknown')
    
    def _create_log_entry(self, level: str, message: str, **kwargs) -> Dict[str, Any]:
        """Create structured log entry."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message,
            'correlation_id': self.correlation_id,
            'function_name': self.function_name,
            'function_version': self.function_version,
            'request_id': self.request_id
        }
        
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

def get_logger(name: str, level: str = None) -> StructuredLogger:
    """Get a structured logger instance."""
    log_level = level or os.environ.get('LOG_LEVEL', 'INFO')
    return StructuredLogger(name, log_level)