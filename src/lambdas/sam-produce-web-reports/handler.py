"""
SAM produce web reports Lambda function handler.
Generates daily web dashboard with match statistics.
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from shared import get_logger, handle_lambda_error, config, get_s3_client
from .dashboard_generator import DashboardGenerator
from .data_aggregator import DataAggregator

logger = get_logger(__name__)

@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for web dashboard generation.
    Triggered by S3 PUT events for run result files matching pattern "2*.json".
    
    Args:
        event: S3 PUT event for run results
        context: Lambda context object
        
    Returns:
        dict: Response with status and message
    """
    logger.info("Starting web dashboard generation", event=event)
    
    try:
        # Extract S3 event information
        s3_events = _extract_s3_events(event)
        if not s3_events:
            logger.warning("No valid S3 events found in trigger")
            return _create_response(200, "No S3 events to process")
        
        # Process each S3 event
        processed_dashboards = []
        for s3_event in s3_events:
            bucket_name = s3_event['bucket']
            object_key = s3_event['key']
            
            logger.info(f"Processing S3 event", bucket=bucket_name, key=object_key)
            
            # Validate file pattern matches "2*.json" in runs/ folder
            if not _is_valid_run_file(object_key):
                logger.info(f"Skipping file - doesn't match pattern", key=object_key)
                continue
            
            # Extract date prefix from filename
            date_prefix = _extract_date_prefix(object_key)
            if not date_prefix:
                logger.warning(f"Could not extract date prefix from file", key=object_key)
                continue
            
            # Generate dashboard for this date
            dashboard_path = _generate_dashboard(date_prefix)
            if dashboard_path:
                processed_dashboards.append(dashboard_path)
                logger.info(f"Successfully generated dashboard", 
                          date=date_prefix, path=dashboard_path)
        
        if processed_dashboards:
            message = f"Generated {len(processed_dashboards)} dashboard(s)"
        else:
            message = "No dashboards generated - no matching files found"
        
        logger.info("Web dashboard generation completed", 
                   dashboards_generated=len(processed_dashboards))
        
        return _create_response(200, message, {
            'dashboards_generated': len(processed_dashboards),
            'dashboard_paths': processed_dashboards
        })
        
    except Exception as e:
        logger.error(f"Error in web dashboard generation: {str(e)}", 
                    error=str(e), event=event)
        raise


def _extract_s3_events(event: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract S3 event information from Lambda event.
    
    Args:
        event: Lambda event containing S3 notifications
        
    Returns:
        List of S3 event dictionaries with bucket and key
    """
    s3_events = []
    
    try:
        if 'Records' in event:
            for record in event['Records']:
                if record.get('eventSource') == 'aws:s3':
                    s3_info = record.get('s3', {})
                    bucket_info = s3_info.get('bucket', {})
                    object_info = s3_info.get('object', {})
                    
                    bucket_name = bucket_info.get('name')
                    object_key = object_info.get('key')
                    
                    if bucket_name and object_key:
                        s3_events.append({
                            'bucket': bucket_name,
                            'key': object_key
                        })
    except Exception as e:
        logger.error(f"Error extracting S3 events: {str(e)}")
    
    return s3_events


def _is_valid_run_file(object_key: str) -> bool:
    """
    Check if the S3 object key matches the expected pattern for run files.
    Pattern: runs/2*.json (files starting with '2' in the runs/ folder)
    
    Args:
        object_key: S3 object key to validate
        
    Returns:
        bool: True if file matches pattern
    """
    # Pattern: runs/2*.json
    pattern = r'^runs/2.*\.json$'
    return bool(re.match(pattern, object_key))


def _extract_date_prefix(object_key: str) -> Optional[str]:
    """
    Extract date prefix (YYYYMMDD) from run file name.
    Expected format: runs/YYYYMMDDtHHMMZ.json
    
    Args:
        object_key: S3 object key
        
    Returns:
        Date prefix string (YYYYMMDD) or None if not found
    """
    try:
        # Extract filename from path
        filename = object_key.split('/')[-1]
        
        # Remove .json extension
        if filename.endswith('.json'):
            filename = filename[:-5]
        
        # Extract date prefix (first 8 characters should be YYYYMMDD)
        if len(filename) >= 8 and filename[:8].isdigit():
            return filename[:8]
    except Exception as e:
        logger.error(f"Error extracting date prefix: {str(e)}", key=object_key)
    
    return None


def _generate_dashboard(date_prefix: str) -> Optional[str]:
    """
    Generate HTML dashboard for the specified date.
    
    Args:
        date_prefix: Date prefix (YYYYMMDD) to generate dashboard for
        
    Returns:
        S3 path of generated dashboard or None if failed
    """
    try:
        # Initialize components
        data_aggregator = DataAggregator()
        dashboard_generator = DashboardGenerator()
        
        # Aggregate data for the date
        logger.info(f"Aggregating data for date", date=date_prefix)
        daily_data = data_aggregator.aggregate_daily_data(date_prefix)
        
        if not daily_data:
            logger.warning(f"No data found for date", date=date_prefix)
            return None
        
        # Generate HTML dashboard
        logger.info(f"Generating HTML dashboard", date=date_prefix)
        html_content = dashboard_generator.generate_html(daily_data)
        
        # Store dashboard in S3
        dashboard_path = f"dashboards/Summary_{date_prefix}.html"
        s3_client = get_s3_client()
        
        s3_client.put_object(
            Bucket=config.s3.sam_website,
            Key=dashboard_path,
            Body=html_content,
            ContentType='text/html',
            CacheControl='max-age=3600'  # Cache for 1 hour
        )
        
        logger.info(f"Dashboard stored successfully", 
                   bucket=config.s3.sam_website, path=dashboard_path)
        
        return dashboard_path
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {str(e)}", date=date_prefix)
        return None


def _create_response(status_code: int, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Create standardized Lambda response.
    
    Args:
        status_code: HTTP status code
        message: Response message
        data: Optional additional data
        
    Returns:
        Lambda response dictionary
    """
    response_body = {
        'message': message,
        'correlation_id': logger.correlation_id
    }
    
    if data:
        response_body.update(data)
    
    return {
        'statusCode': status_code,
        'body': json.dumps(response_body)
    }