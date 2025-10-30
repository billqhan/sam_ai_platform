"""
API Gateway Lambda Handler for RFP Response Agent UI Backend

This Lambda function serves as the API backend for the web UI, providing
endpoints for dashboard data, opportunity search, workflow control, etc.
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal

# AWS clients
s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
BUCKET_PREFIX = os.environ.get('BUCKET_PREFIX', 'l3harris-qhan')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

# Helper functions
def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def cors_response(status_code, body):
    """Return API Gateway response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=decimal_default)
    }

def get_dashboard_metrics(event):
    """Get dashboard summary metrics"""
    # TODO: Query DynamoDB or S3 for real metrics
    # For now, return mock data
    metrics = {
        'totalOpportunities': 1247,
        'totalMatches': 89,
        'highQualityMatches': 34,
        'pending': 12,
        'opportunitiesChange': 12.5,
        'matchesChange': -3.2,
        'qualityChange': 8.7,
        'pendingChange': 15.0,
    }
    return cors_response(200, metrics)

def get_opportunities(event):
    """List opportunities with optional filters"""
    # Parse query parameters
    params = event.get('queryStringParameters', {}) or {}
    
    # TODO: Query S3 or DynamoDB for opportunities
    # Apply filters from params (search, category, agency, etc.)
    
    # Mock response
    opportunities = {
        'total': 1247,
        'page': int(params.get('page', 1)),
        'pageSize': int(params.get('pageSize', 20)),
        'items': []  # Would contain opportunity objects
    }
    return cors_response(200, opportunities)

def get_opportunity_by_id(event, opportunity_id):
    """Get single opportunity details"""
    # TODO: Fetch from S3/DynamoDB
    # Mock response
    opportunity = {
        'id': opportunity_id,
        'title': 'Opportunity Title',
        'description': 'Opportunity description...',
        # ... other fields
    }
    return cors_response(200, opportunity)

def trigger_workflow(event, step):
    """Trigger a workflow step"""
    lambda_function_map = {
        'download': f'{BUCKET_PREFIX}-sam-gov-daily-download-{ENVIRONMENT}',
        'process': f'{BUCKET_PREFIX}-sam-json-processor-{ENVIRONMENT}',
        'match': f'{BUCKET_PREFIX}-sam-sqs-generate-match-reports-{ENVIRONMENT}',
        'reports': f'{BUCKET_PREFIX}-sam-produce-web-reports-{ENVIRONMENT}',
        'notify': f'{BUCKET_PREFIX}-sam-daily-email-notification-{ENVIRONMENT}',
    }
    
    function_name = lambda_function_map.get(step)
    if not function_name:
        return cors_response(400, {'error': f'Unknown workflow step: {step}'})
    
    try:
        # Parse request body for parameters
        body = json.loads(event.get('body', '{}'))
        
        # Invoke Lambda function
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(body)
        )
        
        return cors_response(200, {
            'success': True,
            'step': step,
            'function': function_name,
            'statusCode': response['StatusCode']
        })
    except Exception as e:
        return cors_response(500, {'error': str(e)})

def get_workflow_status(event):
    """Get current workflow status"""
    # TODO: Query CloudWatch or DynamoDB for status
    status = {
        'currentStep': None,
        'lastRun': datetime.now().isoformat(),
        'status': 'idle',
        'message': 'No workflow currently running'
    }
    return cors_response(200, status)

def get_matches(event):
    """List matches with optional filters"""
    params = event.get('queryStringParameters', {}) or {}
    
    # TODO: Query DynamoDB/S3 for matches
    matches = {
        'total': 89,
        'items': []  # Would contain match objects
    }
    return cors_response(200, matches)

def get_reports(event):
    """List generated reports"""
    params = event.get('queryStringParameters', {}) or {}
    report_type = params.get('type', 'all')
    
    # TODO: Query S3 for reports
    reports = {
        'total': 0,
        'items': []
    }
    return cors_response(200, reports)

def get_settings(event):
    """Get application settings"""
    # TODO: Fetch from DynamoDB or Systems Manager Parameter Store
    settings = {
        'matchThreshold': 0.7,
        'maxResults': 100,
        'enableKnowledgeBase': False,
        'companyName': 'L3Harris Technologies',
        # ... other settings
    }
    return cors_response(200, settings)

def update_settings(event):
    """Update application settings"""
    try:
        body = json.loads(event.get('body', '{}'))
        # TODO: Save to DynamoDB or Parameter Store
        return cors_response(200, {'success': True, 'message': 'Settings updated'})
    except Exception as e:
        return cors_response(500, {'error': str(e)})

def lambda_handler(event, context):
    """Main Lambda handler for API Gateway"""
    
    # Handle OPTIONS requests for CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return cors_response(200, {})
    
    # Parse the request
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    path_params = event.get('pathParameters', {}) or {}
    
    print(f"Request: {http_method} {path}")
    
    # Route the request
    try:
        # Health check endpoint
        if path == '/health':
            return cors_response(200, {
                'status': 'healthy',
                'service': 'RFP Response Agent API',
                'version': '1.0.0',
                'timestamp': datetime.now().isoformat()
            })
        
        # Dashboard endpoints
        if path == '/dashboard/metrics':
            return get_dashboard_metrics(event)
        
        # Opportunities endpoints
        elif path == '/opportunities':
            if http_method == 'GET':
                return get_opportunities(event)
        elif path.startswith('/opportunities/'):
            opp_id = path_params.get('id')
            if opp_id:
                return get_opportunity_by_id(event, opp_id)
        
        # Workflow endpoints
        elif path.startswith('/workflow/'):
            action = path.split('/')[-1]
            if http_method == 'POST':
                return trigger_workflow(event, action)
            elif action == 'status':
                return get_workflow_status(event)
        
        # Matches endpoints
        elif path == '/matches':
            return get_matches(event)
        
        # Reports endpoints
        elif path == '/reports' or path.startswith('/reports/'):
            return get_reports(event)
        
        # Settings endpoints
        elif path == '/settings':
            if http_method == 'GET':
                return get_settings(event)
            elif http_method == 'PUT':
                return update_settings(event)
        
        # Not found
        return cors_response(404, {'error': 'Endpoint not found'})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return cors_response(500, {'error': 'Internal server error', 'message': str(e)})
