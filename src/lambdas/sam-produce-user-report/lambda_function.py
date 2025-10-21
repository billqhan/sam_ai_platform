"""
Lambda function entry point for sam-produce-user-report.
This file serves as the main entry point that AWS Lambda expects.
"""

import sys
import os

# Add shared modules to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))

# Import the actual handler
from handler import lambda_handler

# Re-export the lambda_handler for AWS Lambda
__all__ = ['lambda_handler']