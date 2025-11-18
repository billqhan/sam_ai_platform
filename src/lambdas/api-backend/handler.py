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
sqs = boto3.client('sqs')

# Environment variables
BUCKET_PREFIX = os.environ['BUCKET_PREFIX']
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

def get_dashboard_chart_data(event, chart_type):
    """Get dashboard chart data"""
    from datetime import timedelta
    params = event.get('queryStringParameters', {}) or {}
    period = params.get('period', '7d')
    
    # Parse period (7d, 30d, 90d)
    days = int(period.rstrip('d'))
    
    # Generate date range
    today = datetime.now().date()
    dates = [(today - timedelta(days=days-i-1)).isoformat() for i in range(days)]
    
    # TODO: Fetch actual data from DynamoDB/CloudWatch
    # For now, return mock data in Recharts format
    if chart_type == 'opportunities':
        mock_data = [10, 15, 12, 18, 20, 16, 22] if days == 7 else [10] * days
        return cors_response(200, [
            {'date': dates[i], 'opportunities': mock_data[i], 'matches': mock_data[i] // 2}
            for i in range(days)
        ])
    elif chart_type == 'matches':
        mock_data = [5, 8, 6, 10, 12, 9, 14] if days == 7 else [5] * days
        return cors_response(200, [
            {'date': dates[i], 'matches': mock_data[i]}
            for i in range(days)
        ])
    else:
        return cors_response(400, {'error': f'Unknown chart type: {chart_type}'})

def get_top_matches(event):
    """Get top matches for dashboard"""
    params = event.get('queryStringParameters', {}) or {}
    limit = int(params.get('limit', 5))
    
    # TODO: Query DynamoDB for top matches
    # Return empty array for now - UI will use mock data
    return cors_response(200, [])

def get_dashboard_activity(event):
    """Get recent activity for dashboard"""
    params = event.get('queryStringParameters', {}) or {}
    limit = int(params.get('limit', 10))
    
    # TODO: Query DynamoDB/CloudWatch for recent activity
    # Return empty array for now - UI will use mock data
    return cors_response(200, [])

def get_dashboard_metrics(event):
    """Get dashboard summary metrics"""
    try:
        # S3 buckets
        extracted_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
        responses_bucket = f'{BUCKET_PREFIX}-sam-opportunity-responses-{ENVIRONMENT}'
        
        # Count opportunities
        total_opportunities = 0
        try:
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=extracted_bucket, Prefix='', Delimiter='/')
            
            for page in page_iterator:
                if 'CommonPrefixes' in page:
                    total_opportunities += len(page['CommonPrefixes'])
        except Exception as e:
            print(f"Warning: Could not count opportunities: {str(e)}")
            total_opportunities = 0
        
        # Count matches/responses (files in responses bucket)
        total_matches = 0
        high_quality_matches = 0
        try:
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=responses_bucket)
            
            for page in page_iterator:
                if 'Contents' in page:
                    # Count files as matches
                    matches = [obj for obj in page['Contents'] if obj['Key'].endswith('.json') or obj['Key'].endswith('.txt')]
                    total_matches += len(matches)
                    # For now, assume 30% are high quality
                    high_quality_matches += len(matches) * 0.3
        except Exception as e:
            print(f"Warning: Could not count matches: {str(e)}")
            total_matches = 0
            high_quality_matches = 0
        
        # Calculate some basic stats
        pending = max(0, total_opportunities - total_matches)
        
        metrics = {
            'totalOpportunities': int(total_opportunities),
            'totalMatches': int(total_matches),
            'highQualityMatches': int(high_quality_matches),
            'pending': int(pending),
            'opportunitiesChange': 0.0,  # Would need historical data to calculate
            'matchesChange': 0.0,        # Would need historical data to calculate  
            'qualityChange': 0.0,        # Would need historical data to calculate
            'pendingChange': 0.0,        # Would need historical data to calculate
            'lastUpdated': datetime.now().isoformat()
        }
        return cors_response(200, metrics)
        
    except Exception as e:
        print(f"Error calculating dashboard metrics: {str(e)}")
        # Return safe defaults on error
        return cors_response(200, {
            'totalOpportunities': 0,
            'totalMatches': 0,
            'highQualityMatches': 0,
            'pending': 0,
            'opportunitiesChange': 0.0,
            'matchesChange': 0.0,
            'qualityChange': 0.0,
            'pendingChange': 0.0,
            'lastUpdated': datetime.now().isoformat(),
            'error': f'Failed to calculate metrics: {str(e)}'
        })

def get_opportunities(event):
    """List opportunities with optional filters"""
    # Parse query parameters
    params = event.get('queryStringParameters', {}) or {}
    page = int(params.get('page', 1))
    page_size = int(params.get('pageSize', 20))
    search = params.get('search', '').lower()
    
    try:
        # S3 bucket containing the extracted JSON opportunity data
        extracted_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
        
        # List all opportunity files from S3
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=extracted_bucket,
            Prefix='',
            Delimiter='/'
        )
        
        opportunities = []
        
        # Iterate through date folders first, then opportunity folders within each date
        for page_obj in page_iterator:
            # Get date folders (common prefixes)
            if 'CommonPrefixes' in page_obj:
                for date_prefix in page_obj['CommonPrefixes']:
                    date_folder = date_prefix['Prefix'].rstrip('/')
                    
                    # Now list opportunity folders within this date folder
                    try:
                        opp_paginator = s3.get_paginator('list_objects_v2')
                        opp_page_iterator = opp_paginator.paginate(
                            Bucket=extracted_bucket,
                            Prefix=f"{date_folder}/",
                            Delimiter='/'
                        )
                        
                        for opp_page_obj in opp_page_iterator:
                            if 'CommonPrefixes' in opp_page_obj:
                                for opp_prefix in opp_page_obj['CommonPrefixes']:
                                    opp_folder = opp_prefix['Prefix'].rstrip('/')
                                    opportunity_id = opp_folder.split('/')[-1]  # Get just the opportunity ID
                                    
                                    # Look for the opportunity JSON file
                                    try:
                                        json_key = f"{opp_folder}/{opportunity_id}_opportunity.json"
                                        response = s3.get_object(Bucket=extracted_bucket, Key=json_key)
                                        opportunity_data = json.loads(response['Body'].read().decode('utf-8'))

                                        # Prefer stable ID from processed data, then noticeId, then folder name
                                        computed_id = opportunity_data.get('id') or opportunity_id or opportunity_data.get('noticeId')
                                        # Skip invalid or placeholder IDs
                                        if not computed_id or str(computed_id).strip().lower() == 'unknown':
                                            continue

                                        # Extract key fields for the list view
                                        opp = {
                                            'id': computed_id,
                                            'title': opportunity_data.get('title', 'No title'),
                                            'description': opportunity_data.get('description', '')[:300] + '...' if len(opportunity_data.get('description', '')) > 300 else opportunity_data.get('description', ''),
                                            'agency': opportunity_data.get('department', opportunity_data.get('subagency', 'Unknown')),
                                            'solicitationNumber': opportunity_data.get('solicitationNumber', ''),
                                            'postedDate': opportunity_data.get('postedDate', ''),
                                            'responseDeadline': opportunity_data.get('responseDeadLine', ''),
                                            'type': opportunity_data.get('type', ''),
                                            'setAside': opportunity_data.get('setAside', ''),
                                            'active': opportunity_data.get('active', 'Yes'),
                                            'additionalInfoLink': opportunity_data.get('additionalInfoLink', ''),
                                            'uiLink': opportunity_data.get('uiLink', '')
                                        }
                                        
                                        # Apply search filter if provided
                                        if not search or search in opp['title'].lower() or search in opp['description'].lower() or search in opp['agency'].lower():
                                            opportunities.append(opp)
                                            
                                    except Exception as e:
                                        # Skip files that can't be read or parsed
                                        print(f"Warning: Could not process {json_key}: {str(e)}")
                                        continue
                                        
                    except Exception as e:
                        print(f"Warning: Could not process date folder {date_folder}: {str(e)}")
                        continue
        
        # Sort by posted date (most recent first)
        opportunities.sort(key=lambda x: x.get('postedDate', ''), reverse=True)
        
        # Apply pagination
        total = len(opportunities)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = opportunities[start_idx:end_idx]
        
        result = {
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': (total + page_size - 1) // page_size,
            'items': paginated_items
        }
        
        return cors_response(200, result)
        
    except Exception as e:
        print(f"Error fetching opportunities from S3: {str(e)}")
        # Return empty result on error
        return cors_response(200, {
            'total': 0,
            'page': page,
            'pageSize': page_size,
            'totalPages': 0,
            'items': [],
            'error': f'Failed to load opportunities: {str(e)}'
        })

def get_opportunity_by_id(event, opportunity_id):
    """Get single opportunity details"""
    try:
        # S3 bucket containing the extracted JSON opportunity data
        extracted_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
        
        # Search through date folders to find the opportunity
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=extracted_bucket,
            Prefix='',
            Delimiter='/'
        )
        
        for page_obj in page_iterator:
            if 'CommonPrefixes' in page_obj:
                for date_prefix in page_obj['CommonPrefixes']:
                    date_folder = date_prefix['Prefix'].rstrip('/')
                    
                    # Try to find the opportunity in this date folder
                    json_key = f"{date_folder}/{opportunity_id}/{opportunity_id}_opportunity.json"
                    
                    try:
                        response = s3.get_object(Bucket=extracted_bucket, Key=json_key)
                        opportunity_data = json.loads(response['Body'].read().decode('utf-8'))
                        
                        # Return the full opportunity data
                        return cors_response(200, opportunity_data)
                        
                    except s3.exceptions.NoSuchKey:
                        # Continue searching in other date folders
                        continue
                    except json.JSONDecodeError as e:
                        return cors_response(500, {'error': f'Failed to parse opportunity data: {str(e)}'})
        
        # If we get here, the opportunity was not found in any date folder
        return cors_response(404, {'error': f'Opportunity {opportunity_id} not found'})
            
    except Exception as e:
        print(f"Error fetching opportunity {opportunity_id}: {str(e)}")
        return cors_response(500, {'error': f'Failed to load opportunity: {str(e)}'})

def trigger_workflow(event, step):
    """Trigger a workflow step - modified to work with existing data when Lambda functions are not available"""
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
        body_str = event.get('body') or '{}'
        body = json.loads(body_str)
        
        # Check if Lambda function exists before trying to invoke it
        try:
            lambda_client.get_function(FunctionName=function_name)
            function_exists = True
        except lambda_client.exceptions.ResourceNotFoundException:
            function_exists = False
            print(f"Lambda function {function_name} does not exist, using mock response")
        
        if function_exists:
            # Create appropriate event payload for each step
            if step == 'download':
                # Direct invocation for download
                payload = body
            elif step == 'process':
                # Simulate S3 event for JSON processor - trigger processing of all files
                payload = {
                    'trigger': 'manual',
                    'action': 'process_all_files'
                }
            elif step == 'match':
                # Create SQS-like event structure for matching function
                payload = {
                    'Records': [
                        {
                            'eventSource': 'aws:sqs',
                            'body': json.dumps({
                                'Records': [
                                    {
                                        'eventSource': 'aws:s3',
                                        'eventName': 'ObjectCreated:Put',
                                        's3': {
                                            'bucket': {'name': f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'},
                                            'object': {'key': 'manual_trigger_match'}
                                        }
                                    }
                                ]
                            })
                        }
                    ]
                }
            elif step == 'reports':
                # Simulate S3 event for report generator - trigger report generation
                payload = {
                    'trigger': 'manual',
                    'action': 'generate_reports'
                }
            elif step == 'notify':
                # Direct invocation for notifications
                payload = body
            else:
                payload = body
            
            # Invoke Lambda function
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(payload)
            )
            
            return cors_response(200, {
                'success': True,
                'step': step,
                'function': function_name,
                'statusCode': response['StatusCode'],
                'payload': payload
            })
        else:
            # Lambda function doesn't exist, provide mock response based on existing data
            return handle_workflow_with_existing_data(step, body)
            
    except Exception as e:
        print(f"Error triggering workflow {step}: {str(e)}")
        return cors_response(500, {'error': str(e)})

def handle_workflow_with_existing_data(step, body):
    """Handle workflow steps using existing S3 data when Lambda functions are not available"""
    try:
        if step == 'download':
            # Check for recent SAM data files
            s3_bucket = f'{BUCKET_PREFIX}-sam-data-in-{ENVIRONMENT}'
            try:
                response = s3.list_objects_v2(
                    Bucket=s3_bucket,
                    MaxKeys=10
                )
                
                files = response.get('Contents', [])
                if files:
                    # Sort by last modified, get the most recent
                    files.sort(key=lambda x: x['LastModified'], reverse=True)
                    latest_file = files[0]
                    
                    # Get file content to count opportunities
                    obj = s3.get_object(Bucket=s3_bucket, Key=latest_file['Key'])
                    content = json.loads(obj['Body'].read())
                    opportunities_count = len(content.get('opportunitiesData', []))
                    
                    return cors_response(200, {
                        'success': True,
                        'step': step,
                        'message': 'Using existing SAM.gov data',
                        'data': {
                            'opportunitiesCount': opportunities_count,
                            's3ObjectKey': latest_file['Key'],
                            'lastModified': latest_file['LastModified'].isoformat(),
                            'size': latest_file['Size']
                        }
                    })
                else:
                    return cors_response(200, {
                        'success': False,
                        'step': step,
                        'message': 'No existing SAM.gov data found',
                        'data': {'opportunitiesCount': 0}
                    })
            except Exception as s3_error:
                return cors_response(200, {
                    'success': False,
                    'step': step,
                    'message': f'Error accessing existing data: {str(s3_error)}',
                    'data': {'opportunitiesCount': 0}
                })
        
        elif step == 'process':
            # Check for processed JSON files
            s3_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
            try:
                response = s3.list_objects_v2(Bucket=s3_bucket, MaxKeys=100)
                processed_count = len(response.get('Contents', []))
                
                return cors_response(200, {
                    'success': True,
                    'step': step,
                    'message': 'Using existing processed data',
                    'data': {
                        'processedFiles': processed_count,
                        'status': 'completed'
                    }
                })
            except:
                return cors_response(200, {
                    'success': True,
                    'step': step,
                    'message': 'Process step completed (mock)',
                    'data': {'processedFiles': 0, 'status': 'completed'}
                })
        
        elif step == 'match':
            return cors_response(200, {
                'success': True,
                'step': step,
                'message': 'Matching step completed (using existing match results)',
                'data': {'status': 'completed'}
            })
        
        elif step == 'reports':
            return cors_response(200, {
                'success': True,
                'step': step,
                'message': 'Reports generated (using existing reports)',
                'data': {'status': 'completed'}
            })
        
        elif step == 'notify':
            return cors_response(200, {
                'success': True,
                'step': step,
                'message': 'Notifications sent (mock)',
                'data': {'status': 'completed'}
            })
        
        else:
            return cors_response(200, {
                'success': True,
                'step': step,
                'message': f'Workflow step {step} completed (mock)',
                'data': {'status': 'completed'}
            })
    
    except Exception as e:
        return cors_response(500, {
            'success': False,
            'step': step,
            'error': f'Error handling workflow with existing data: {str(e)}'
        })

def generate_auto_workflow_report(event):
    """Generate automatic workflow report and upload to S3"""
    try:
        body = json.loads(event.get('body', '{}'))
        step = body.get('step', 'unknown')
        step_name = body.get('stepName', 'Unknown Step')
        timestamp = body.get('timestamp', datetime.now().isoformat())
        success = body.get('success', True)
        error_msg = body.get('error', '')
        
        # Generate timestamped filename
        dt = datetime.now()
        filename = f"UI_Workflow_{dt.strftime('%Y%m%d_%H%M%S')}.html"
        
        # Create HTML report content
        status_color = '#22c55e' if success else '#ef4444'
        status_text = 'SUCCESS' if success else 'FAILED'
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI Workflow Execution Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow: hidden; }}
        .header {{ background: {status_color}; color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 2.5em; font-weight: 300; }}
        .header .status {{ font-size: 1.2em; opacity: 0.9; }}
        .content {{ padding: 40px; }}
        .section {{ margin-bottom: 30px; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #e5e5e5; padding-bottom: 10px; margin-bottom: 20px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
        .info-item {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid {status_color}; }}
        .info-label {{ font-weight: 600; color: #666; font-size: 0.9em; text-transform: uppercase; margin-bottom: 5px; }}
        .info-value {{ font-size: 1.1em; color: #333; }}
        .error-section {{ background: #fee; border: 1px solid #fcc; padding: 20px; border-radius: 8px; margin-top: 20px; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 UI Workflow Execution</h1>
            <div class="status">Status: {status_text}</div>
        </div>
        <div class="content">
            <div class="section">
                <h2>📋 Execution Details</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Workflow Step</div>
                        <div class="info-value">{step_name}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Step ID</div>
                        <div class="info-value">{step}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Execution Time</div>
                        <div class="info-value">{timestamp}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Trigger Source</div>
                        <div class="info-value">Manual UI Button</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>⚡ System Information</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Platform</div>
                        <div class="info-value">AWS Lambda + API Gateway</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Environment</div>
                        <div class="info-value">Development</div>
                    </div>
                </div>
            </div>
            
            {"" if success else f'''
            <div class="error-section">
                <h3 style="color: #dc3545; margin-top: 0;">❌ Error Details</h3>
                <p><strong>Error Message:</strong> {error_msg}</p>
            </div>
            '''}
        </div>
        <div class="footer">
            Generated automatically by AI-RFP Platform • {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
    </div>
</body>
</html>"""

        # Upload to S3
        s3_bucket = f'{BUCKET_PREFIX}-sam-website-{ENVIRONMENT}'
        s3_key = f'dashboards/{filename}'
        
        s3.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html',
            CacheControl='public, max-age=3600'
        )
        
        return cors_response(200, {
            'success': True,
            'message': 'Auto-report generated successfully',
            'filename': filename,
            's3Key': s3_key,
            'reportUrl': f"https://{s3_bucket}.s3.amazonaws.com/{s3_key}"
        })
        
    except Exception as e:
        print(f"Error generating auto-report: {str(e)}")
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

def get_workflow_history(event):
    """Get workflow execution history"""
    # TODO: Query CloudWatch logs or DynamoDB for real history
    history = [
        {
            'type': 'Full Workflow',
            'status': 'success',
            'timestamp': '2025-11-01 14:00:00',
            'duration': 342,
            'itemsProcessed': 2,
            'message': 'All steps completed successfully'
        },
        {
            'type': 'Generate Reports',
            'status': 'success',
            'timestamp': '2025-11-01 13:30:15',
            'duration': 45,
            'message': 'Web dashboard and user reports generated'
        },
        {
            'type': 'Generate Matches',
            'status': 'success',
            'timestamp': '2025-11-01 13:25:30',
            'duration': 178,
            'itemsProcessed': 159,
            'message': '3 matches found above threshold'
        }
    ]
    return cors_response(200, history)

def get_matches_by_opportunity(event, opportunity_id):
    """Get all matches for a specific opportunity"""
    try:
        matches_bucket = f'{BUCKET_PREFIX}-sam-matching-out-runs-{ENVIRONMENT}'
        
        # Look for match reports for this opportunity
        matches = []
        seen_ids = set()

        # Fallback: deep search for the opportunity_id anywhere in the JSON
        def deep_contains(value, target):
            try:
                if isinstance(value, dict):
                    for v in value.values():
                        if deep_contains(v, target):
                            return True
                elif isinstance(value, list):
                    for v in value:
                        if deep_contains(v, target):
                            return True
                else:
                    if isinstance(value, (str, int)):
                        return str(value) == str(target)
                return False
            except Exception:
                return False
        try:
            print(f"[matches_by_opportunity] bucket={matches_bucket} id={opportunity_id}")
            # Pattern 1: Historical path runs/{opportunityId}/...
            resp1 = s3.list_objects_v2(
                Bucket=matches_bucket,
                Prefix=f'runs/{opportunity_id}'
            )
            count1 = len(resp1.get('Contents', []))
            print(f"[matches_by_opportunity] runs/{opportunity_id} count={count1}")
            if 'Contents' in resp1:
                for obj in resp1['Contents']:
                    if obj['Key'].endswith('.json'):
                        try:
                            match_obj = s3.get_object(Bucket=matches_bucket, Key=obj['Key'])
                            match_data = json.loads(match_obj['Body'].read().decode('utf-8'))
                            if isinstance(match_data, dict):
                                item_id = obj['Key'].split('/')[-1].replace('.json', '')
                                if item_id in seen_ids:
                                    continue
                                seen_ids.add(item_id)
                                opp_id_in_json = match_data.get('opportunityId') or match_data.get('opportunity_id') or opportunity_id
                                matches.append({
                                    'id': item_id,
                                    'opportunityId': opp_id_in_json,
                                    'title': match_data.get('opportunity_title', match_data.get('title', 'No title')),
                                    'matchScore': match_data.get('match_score', match_data.get('score', 0.0)),
                                    'status': match_data.get('status', 'completed'),
                                    'agency': match_data.get('agency', match_data.get('department', 'Unknown')),
                                    'type': match_data.get('type', 'Solicitation'),
                                    'createdDate': obj['LastModified'].isoformat(),
                                    'responseDeadline': match_data.get('response_deadline', match_data.get('responseDeadLine', '')),
                                    'reason': match_data.get('match_reason', match_data.get('reasoning', 'Automated match')),
                                    'confidence': match_data.get('confidence', match_data.get('match_score', 0.0)),
                                    'requirements': match_data.get('requirements', []),
                                    'capabilities': match_data.get('capabilities', [])
                                })
                        except Exception as e:
                            print(f"Error processing match file {obj['Key']}: {str(e)}")
                            continue

            # Pattern 2: Current path runs/raw/YYYYMMDDtHHMMZ_{opportunityId}.json
            # Pattern 2: Current path runs/raw/ with pagination
            paginator = s3.get_paginator('list_objects_v2')
            page_it = paginator.paginate(Bucket=matches_bucket, Prefix='runs/raw/')
            total_raw = 0
            for page in page_it:
                contents = page.get('Contents', [])
                total_raw += len(contents)
                for obj in contents:
                    key = obj['Key']
                    if key.endswith('.json'):
                        try:
                            match_obj = s3.get_object(Bucket=matches_bucket, Key=key)
                            match_data = json.loads(match_obj['Body'].read().decode('utf-8'))
                            if isinstance(match_data, dict):
                                sol_num = match_data.get('solicitationNumber')
                                notice_id = match_data.get('noticeId')
                                opp_id_in_json = match_data.get('opportunityId') or match_data.get('opportunity_id')
                                file_id = key.split('/')[-1].replace('.json', '')
                                if (
                                    sol_num == opportunity_id
                                    or notice_id == opportunity_id
                                    or opp_id_in_json == opportunity_id
                                    or key.endswith(f'_{opportunity_id}.json')
                                    or deep_contains(match_data, opportunity_id)
                                ):
                                    if file_id in seen_ids:
                                        continue
                                    seen_ids.add(file_id)
                                    matches.append({
                                        'id': file_id,
                                        'opportunityId': opp_id_in_json or opportunity_id,
                                        'title': match_data.get('opportunity_title', match_data.get('title', 'No title')),
                                        'matchScore': match_data.get('match_score', match_data.get('score', 0.0)),
                                        'status': match_data.get('status', 'completed'),
                                        'agency': match_data.get('agency', match_data.get('department', 'Unknown')),
                                        'type': match_data.get('type', 'Solicitation'),
                                        'createdDate': obj['LastModified'].isoformat(),
                                        'responseDeadline': match_data.get('response_deadline', match_data.get('responseDeadLine', '')),
                                        'reason': match_data.get('match_reason', match_data.get('reasoning', 'Automated match')),
                                        'confidence': match_data.get('confidence', match_data.get('match_score', 0.0)),
                                        'requirements': match_data.get('requirements', []),
                                        'capabilities': match_data.get('capabilities', [])
                                    })
                        except Exception as e:
                            print(f"Error processing match file {key}: {str(e)}")
                            continue
            print(f"[matches_by_opportunity] runs/raw total scanned={total_raw}, matches_found={len(matches)}")
        except Exception as e:
            print(f"Error accessing matches bucket: {str(e)}")
            return cors_response(404, {'error': 'No matches found for this opportunity'})

        # Pattern 3: Daily SQS-style outputs: {date}/matches/{opportunityId}.json
        # Check last 30 days of date folders
        try:
            from datetime import datetime, timedelta
            sqs_bucket = f'{BUCKET_PREFIX}-sam-matching-out-sqs-{ENVIRONMENT}'
            print(f"[matches_by_opportunity] scanning SQS bucket={sqs_bucket}")
            
            # Generate list of date prefixes to check (last 30 days)
            today = datetime.now()
            date_prefixes = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]
            
            sqs_scanned = 0
            for date_prefix in date_prefixes:
                key = f'{date_prefix}/matches/{opportunity_id}.json'
                try:
                    match_obj = s3.get_object(Bucket=sqs_bucket, Key=key)
                    match_data = json.loads(match_obj['Body'].read().decode('utf-8'))
                    sqs_scanned += 1
                    
                    file_id = opportunity_id
                    if file_id in seen_ids:
                        continue
                    seen_ids.add(file_id)
                    
                    opp_id_in_json = match_data.get('opportunityId') or match_data.get('opportunity_id') or opportunity_id
                    matches.append({
                        'id': f"{date_prefix}_matches",
                        'opportunityId': opp_id_in_json,
                        'title': match_data.get('opportunity_title', match_data.get('title', 'No title')),
                        'matchScore': match_data.get('match_score', match_data.get('score', 0.0)),
                        'status': match_data.get('status', 'completed'),
                        'agency': match_data.get('agency', match_data.get('department', 'Unknown')),
                        'type': match_data.get('type', 'Solicitation'),
                        'createdDate': date_prefix,
                        'responseDeadline': match_data.get('response_deadline', match_data.get('responseDeadLine', '')),
                        'reason': match_data.get('match_reason', match_data.get('reasoning', 'Automated match')),
                        'confidence': match_data.get('confidence', match_data.get('match_score', 0.0)),
                        'requirements': match_data.get('requirements', []),
                        'capabilities': match_data.get('capabilities', [])
                    })
                    print(f"[matches_by_opportunity] Found SQS match for {opportunity_id} on {date_prefix}")
                except s3.exceptions.NoSuchKey:
                    # No match file for this date, continue
                    pass
                except Exception as e:
                    print(f"Error processing SQS match file {key}: {str(e)}")
                    continue
            
            print(f"[matches_by_opportunity] SQS checked {len(date_prefixes)} dates, found={sqs_scanned}, total_matches={len(matches)}")
        except Exception as e:
            print(f"Warning: error scanning SQS bucket: {str(e)}")
        
        if not matches:
            return cors_response(404, {'error': 'No matches found for this opportunity'})
        
        return cors_response(200, {
            'matches': matches,
            'total': len(matches),
            'opportunityId': opportunity_id
        })
        
    except Exception as e:
        print(f"Error getting matches by opportunity: {str(e)}")
        return cors_response(500, {'error': 'Internal server error', 'message': str(e)})

def get_matches(event):
    """List matches with optional filters"""
    params = event.get('queryStringParameters', {}) or {}
    page = int(params.get('page', 1))
    page_size = int(params.get('pageSize', 20))
    search = params.get('search', '').lower()
    
    try:
        # S3 buckets for match data
        responses_bucket = f'{BUCKET_PREFIX}-sam-opportunity-responses-{ENVIRONMENT}'
        matches_bucket = f'{BUCKET_PREFIX}-sam-matching-out-runs-{ENVIRONMENT}'
        
        matches = []
        
        # Check for match reports in the matching output bucket
        try:
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=matches_bucket,
                Prefix='runs/'
            )
            
            for page_obj in page_iterator:
                if 'Contents' in page_obj:
                    for obj in page_obj['Contents']:
                        if obj['Key'].endswith('.json'):
                            try:
                                # Get the match report
                                response = s3.get_object(Bucket=matches_bucket, Key=obj['Key'])
                                match_data = json.loads(response['Body'].read().decode('utf-8'))
                                
                                # Extract match information
                                if isinstance(match_data, dict):
                                    match = {
                                        'id': obj['Key'].split('/')[-1].replace('.json', ''),
                                        'opportunityId': match_data.get('opportunityId', match_data.get('opportunity_id', 'Unknown')),
                                        'title': match_data.get('opportunity_title', match_data.get('title', 'No title')),
                                        'matchScore': match_data.get('match_score', match_data.get('score', 0.0)),
                                        'status': match_data.get('status', 'pending'),
                                        'agency': match_data.get('agency', match_data.get('department', 'Unknown')),
                                        'type': match_data.get('type', 'Solicitation'),
                                        'createdDate': obj['LastModified'].isoformat() if 'LastModified' in obj else datetime.now().isoformat(),
                                        'responseDeadline': match_data.get('response_deadline', match_data.get('responseDeadLine', '')),
                                        'reason': match_data.get('match_reason', match_data.get('reasoning', 'Automated match')),
                                        'confidence': match_data.get('confidence', match_data.get('match_score', 0.0))
                                    }
                                    
                                    # Apply search filter if provided
                                    if not search or search in match['title'].lower() or search in match['agency'].lower():
                                        matches.append(match)
                                        
                            except Exception as e:
                                print(f"Warning: Could not process match file {obj['Key']}: {str(e)}")
                                continue
                                
        except Exception as e:
            print(f"Warning: Could not access matches bucket {matches_bucket}: {str(e)}")
        
        # If no matches found, check opportunity responses bucket
        if not matches:
            try:
                page_iterator = paginator.paginate(
                    Bucket=responses_bucket,
                    Prefix=''
                )
                
                for page_obj in page_iterator:
                    if 'Contents' in page_obj:
                        for obj in page_obj['Contents']:
                            if obj['Key'].endswith('.json'):
                                try:
                                    response = s3.get_object(Bucket=responses_bucket, Key=obj['Key'])
                                    response_data = json.loads(response['Body'].read().decode('utf-8'))
                                    
                                    match = {
                                        'id': obj['Key'].split('/')[-1].replace('.json', ''),
                                        'opportunityId': response_data.get('opportunityId', response_data.get('opportunity_id', 'Unknown')),
                                        'title': response_data.get('title', 'No title'),
                                        'matchScore': response_data.get('score', 0.8),
                                        'status': 'generated',
                                        'agency': response_data.get('agency', 'Unknown'),
                                        'type': 'Response Generated',
                                        'createdDate': obj['LastModified'].isoformat() if 'LastModified' in obj else datetime.now().isoformat(),
                                        'responseDeadline': response_data.get('deadline', ''),
                                        'reason': 'Response generated for opportunity',
                                        'confidence': 0.8
                                    }
                                    
                                    if not search or search in match['title'].lower() or search in match['agency'].lower():
                                        matches.append(match)
                                        
                                except Exception as e:
                                    print(f"Warning: Could not process response file {obj['Key']}: {str(e)}")
                                    continue
                                    
            except Exception as e:
                print(f"Warning: Could not access responses bucket {responses_bucket}: {str(e)}")
        
        # Sort by match score (highest first)
        matches.sort(key=lambda x: x.get('matchScore', 0), reverse=True)
        
        # Apply pagination
        total = len(matches)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_matches = matches[start_idx:end_idx]
        
        result = {
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': (total + page_size - 1) // page_size,
            'items': paginated_matches
        }
        
        return cors_response(200, result)
        
    except Exception as e:
        print(f"Error fetching matches: {str(e)}")
        return cors_response(200, {
            'total': 0,
            'page': page,
            'pageSize': page_size,
            'totalPages': 0,
            'items': [],
            'error': f'Failed to load matches: {str(e)}'
        })

def get_report_content(event, report_id):
    """Get report content by ID and serve it directly"""
    try:
        # Map report ID to S3 key
        # We need to look up the actual S3 key from the reports metadata
        # Since we know the ID, let's build the S3 key based on patterns
        
        if report_id == 'dashboards_index':
            s3_key = 'dashboards/index.html'
        elif report_id == 'index':
            s3_key = 'index.html'
        elif report_id.startswith('dashboards_'):
            # Extract the file part and add .html extension
            file_part = report_id.replace('dashboards_', '')
            s3_key = f'dashboards/{file_part}.html'
        else:
            # Default: replace first underscore with slash and add .html if needed
            s3_key = report_id.replace('_', '/', 1)
            if not s3_key.endswith('.html'):
                s3_key += '.html'
        
        # Determine which bucket based on the key pattern
        if s3_key.startswith('dashboards/') or s3_key == 'index.html':
            bucket = f'{BUCKET_PREFIX}-sam-website-{ENVIRONMENT}'
        else:
            bucket = f'{BUCKET_PREFIX}-sam-matching-out-runs-{ENVIRONMENT}'
            
        try:
            # Get object from S3
            response = s3.get_object(Bucket=bucket, Key=s3_key)
            content = response['Body'].read()
            
            # Determine content type based on file extension
            content_type = 'text/html'
            if s3_key.endswith('.json'):
                content_type = 'application/json'
            elif s3_key.endswith('.txt'):
                content_type = 'text/plain'
            elif s3_key.endswith('.csv'):
                content_type = 'text/csv'
                
            # Return content directly
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': content_type,
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Cache-Control': 'public, max-age=3600'  # Cache for 1 hour
                },
                'body': content.decode('utf-8') if content_type.startswith('text') else content,
                'isBase64Encoded': False
            }
            
        except Exception as e:
            print(f"Error retrieving report content from S3: {str(e)}")
            return cors_response(404, {'error': f'Report not found: {report_id}'})
            
    except Exception as e:
        print(f"Error serving report content: {str(e)}")
        return cors_response(500, {'error': f'Failed to retrieve report: {str(e)}'})

def get_reports(event):
    """List generated reports"""
    params = event.get('queryStringParameters', {}) or {}
    report_type = params.get('type', 'all')
    page = int(params.get('page', 1))
    page_size = int(params.get('pageSize', 20))
    
    try:
        # S3 bucket for website reports
        website_bucket = f'{BUCKET_PREFIX}-sam-website-{ENVIRONMENT}'
        
        reports = []
        
        try:
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=website_bucket, Prefix='')
            
            for page_obj in page_iterator:
                if 'Contents' in page_obj:
                    for obj in page_obj['Contents']:
                        if obj['Key'].endswith('.html'):
                            try:
                                # Extract report info from filename and metadata
                                filename = obj['Key'].split('/')[-1]
                                
                                # Determine report type based on filename patterns
                                if 'summary' in filename.lower() or 'opportunity' in filename.lower():
                                    report_type_val = 'web'
                                    title = 'Daily Opportunity Summary Report'
                                    icon_type = 'web'
                                elif 'business_report' in filename.lower() or 'manual_workflow' in filename.lower():
                                    report_type_val = 'workflow'
                                    # Extract timestamp from filename for title
                                    import re
                                    # Look for patterns like Business_Report_2025-11-02_03-21-47.html
                                    timestamp_match = re.search(r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})', filename)
                                    if timestamp_match:
                                        year, month, day, hour, minute = timestamp_match.groups()
                                        compact_timestamp = f"{year}{month}{day}{hour}{minute}"
                                        title = f'Business Report {compact_timestamp}'
                                    else:
                                        title = 'Business Report'
                                    icon_type = 'workflow'
                                else:
                                    report_type_val = 'user'
                                    title = 'User Report'
                                    icon_type = 'user'
                                
                                # Generate presigned URLs for secure access (valid for 1 hour)
                                try:
                                    view_url = s3.generate_presigned_url(
                                        'get_object',
                                        Params={'Bucket': website_bucket, 'Key': obj['Key']},
                                        ExpiresIn=3600
                                    )
                                    download_url = s3.generate_presigned_url(
                                        'get_object',
                                        Params={'Bucket': website_bucket, 'Key': obj['Key']},
                                        ExpiresIn=3600
                                    )
                                except Exception as e:
                                    print(f"Error generating presigned URLs: {str(e)}")
                                    view_url = None
                                    download_url = None
                                
                                # Create report entry
                                report = {
                                    'id': obj['Key'].replace('.html', '').replace('/', '_'),
                                    'title': title,
                                    'type': report_type_val,
                                    'generatedDate': obj['LastModified'].isoformat(),
                                    'size': obj.get('Size', 0),
                                    'filename': filename,
                                    's3Key': obj['Key'],
                                    'downloadUrl': download_url or f"https://{website_bucket}.s3.amazonaws.com/{obj['Key']}",
                                    'viewUrl': view_url or f"https://{website_bucket}.s3.amazonaws.com/{obj['Key']}",
                                    'emailSent': True,  # Assume reports are emailed
                                    'summary': f'Generated report containing opportunity analysis and matches for {obj["LastModified"].strftime("%Y-%m-%d")}'
                                }
                                
                                reports.append(report)
                                
                            except Exception as e:
                                print(f"Warning: Could not process report file {obj['Key']}: {str(e)}")
                                continue
                                
        except Exception as e:
            print(f"Warning: Could not access reports bucket {website_bucket}: {str(e)}")
        
        # Also check for other report files in matching results buckets
        try:
            runs_bucket = f'{BUCKET_PREFIX}-sam-matching-out-runs-{ENVIRONMENT}'
            page_iterator = paginator.paginate(Bucket=runs_bucket, Prefix='runs/')
            
            for page_obj in page_iterator:
                if 'Contents' in page_obj:
                    for obj in page_obj['Contents']:
                        if obj['Key'].endswith('.json') and 'summary' in obj['Key']:
                            try:
                                filename = obj['Key'].split('/')[-1]
                                
                                report = {
                                    'id': obj['Key'].replace('.json', '').replace('/', '_'),
                                    'title': 'Matching Run Summary',
                                    'type': 'analysis',
                                    'generatedDate': obj['LastModified'].isoformat(),
                                    'size': obj.get('Size', 0),
                                    'filename': filename,
                                    's3Key': obj['Key'],
                                    'downloadUrl': f"https://{runs_bucket}.s3.amazonaws.com/{obj['Key']}",
                                    'viewUrl': None,  # JSON files are not viewable in browser
                                    'emailSent': False,
                                    'summary': f'Matching analysis summary for batch run on {obj["LastModified"].strftime("%Y-%m-%d")}'
                                }
                                
                                reports.append(report)
                                
                            except Exception as e:
                                print(f"Warning: Could not process analysis file {obj['Key']}: {str(e)}")
                                continue
                                
        except Exception as e:
            print(f"Warning: Could not access runs bucket {runs_bucket}: {str(e)}")
        
        # Sort reports by date (newest first)
        reports.sort(key=lambda x: x['generatedDate'], reverse=True)
        
        # Filter by type if specified
        if report_type != 'all':
            reports = [r for r in reports if r['type'] == report_type]
        
        # Apply pagination
        total = len(reports)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_reports = reports[start_idx:end_idx]
        
        result = {
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': (total + page_size - 1) // page_size,
            'items': paginated_reports
        }
        
        return cors_response(200, result)
        
    except Exception as e:
        print(f"Error fetching reports: {str(e)}")
        return cors_response(200, {
            'total': 0,
            'page': page,
            'pageSize': page_size,
            'totalPages': 0,
            'items': [],
            'error': f'Failed to load reports: {str(e)}'
        })

def trigger_matching(event):
    """Trigger the matching process for all opportunities"""
    try:
        # Get SQS queue for matching (uses the existing JSON messages queue)
        sqs = boto3.client('sqs')
        queue_name = f'{BUCKET_PREFIX}-sqs-sam-json-messages-{ENVIRONMENT}'
        
        try:
            # Get queue URL
            queue_response = sqs.get_queue_url(QueueName=queue_name)
            queue_url = queue_response['QueueUrl']
        except Exception as e:
            return cors_response(400, {'error': f'Could not find SQS queue {queue_name}: {str(e)}'})
        
        # Get all opportunities to trigger matching
        extracted_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
        
        opportunities_processed = 0
        messages_sent = 0
        
        try:
            paginator = s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=extracted_bucket, Prefix='')
            
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].endswith('_opportunity.json'):
                            try:
                                # Get opportunity data
                                response = s3.get_object(Bucket=extracted_bucket, Key=obj['Key'])
                                opportunity = json.loads(response['Body'].read().decode('utf-8'))
                                
                                # Create S3 event message for matching (same format as used by the system)
                                s3_event = {
                                    'Records': [{
                                        's3': {
                                            'bucket': {'name': extracted_bucket},
                                            'object': {'key': obj['Key']}
                                        }
                                    }]
                                }
                                
                                # Send to SQS queue (matches the format expected by matching Lambda)
                                sqs.send_message(
                                    QueueUrl=queue_url,
                                    MessageBody=json.dumps(s3_event, default=decimal_default)
                                )
                                
                                messages_sent += 1
                                opportunities_processed += 1
                                
                            except Exception as e:
                                print(f"Warning: Could not process opportunity {obj['Key']}: {str(e)}")
                                opportunities_processed += 1
                                continue
                                
        except Exception as e:
            return cors_response(500, {'error': f'Failed to process opportunities: {str(e)}'})
            
        return cors_response(200, {
            'success': True,
            'message': f'Matching triggered for {opportunities_processed} opportunities',
            'opportunities_processed': opportunities_processed,
            'messages_sent': messages_sent,
            'queue_name': queue_name
        })
        
    except Exception as e:
        print(f"Error triggering matching: {str(e)}")
        return cors_response(500, {'error': f'Failed to trigger matching: {str(e)}'})

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
        elif path.startswith('/dashboard/charts/'):
            chart_type = path.split('/')[-1]
            return get_dashboard_chart_data(event, chart_type)
        elif path.startswith('/dashboard/top-matches'):
            return get_top_matches(event)
        elif path == '/dashboard/activity':
            return get_dashboard_activity(event)
        
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
                if action == 'auto-report':
                    return generate_auto_workflow_report(event)
                else:
                    return trigger_workflow(event, action)
            elif action == 'status':
                return get_workflow_status(event)
            elif action == 'history':
                return get_workflow_history(event)
        
        # Matches endpoints
        elif path == '/matches':
            return get_matches(event)
        elif path == '/matches/trigger' and http_method == 'POST':
            return trigger_matching(event)
        elif path.startswith('/matches/opportunity/'):
            opp_id = path.split('/')[-1]
            return get_matches_by_opportunity(event, opp_id)
        
        # Reports endpoints
        elif path == '/reports':
            return get_reports(event)
        elif path.startswith('/reports/') and path.endswith('/view'):
            # Extract report ID from path like /reports/{id}/view
            report_id = path.split('/')[-2]
            return get_report_content(event, report_id)
        elif path.startswith('/reports/'):
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
