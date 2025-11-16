"""
Lambda function entry point for SAM produce web reports.
Imports and delegates to the main handler.
"""

from handler import lambda_handler

# Export the handler
__all__ = ['lambda_handler']
