"""
SAM JSON processor Lambda function handler.
Processes SAM opportunities JSON and splits into individual files.
"""

import json
import os
import asyncio
from datetime import datetime
# import aiohttp  # Not used, replaced with requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any, Optional
import tempfile
import re

from shared.logging_config import get_logger
from shared.error_handling import handle_lambda_error, RetryableError, NonRetryableError, ErrorType
from shared.aws_clients import aws_clients
from shared.config import config

logger = get_logger(__name__)

class OpportunityProcessor:
    """Handles processing of SAM opportunities JSON."""
    
    def __init__(self):
        self.s3_client = aws_clients.s3
        self.output_bucket = config.s3.sam_extracted_json_resources
        self.max_concurrent_downloads = config.processing.max_concurrent_downloads
    
    def process_s3_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process S3 PUT event and extract opportunities."""
        logger.info("Processing S3 event", event=event)
        
        processed_files = []
        errors = []
        
        for record in event.get('Records', []):
            try:
                # Extract S3 event details
                s3_info = record.get('s3', {})
                bucket_name = s3_info.get('bucket', {}).get('name')
                object_key = s3_info.get('object', {}).get('key')
                
                if not bucket_name or not object_key:
                    logger.warning("Invalid S3 event record", record=record)
                    continue
                
                logger.info("Processing S3 object", bucket=bucket_name, key=object_key)
                
                # Download and process the SAM opportunities JSON
                result = self._process_sam_json_file(bucket_name, object_key)
                processed_files.append(result)
                
            except Exception as e:
                error_msg = f"Error processing S3 record: {str(e)}"
                logger.error(error_msg, record=record, error=str(e))
                errors.append(error_msg)
        
        return {
            'processed_files': len(processed_files),
            'total_opportunities': sum(r['opportunities_processed'] for r in processed_files),
            'errors': errors
        }
    
    def _process_sam_json_file(self, bucket_name: str, object_key: str) -> Dict[str, Any]:
        """Download and process a single SAM JSON file."""
        logger.info("Downloading SAM JSON file", bucket=bucket_name, key=object_key)
        
        try:
            # Download the JSON file from S3
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            json_content = response['Body'].read().decode('utf-8')
            
            # Parse the JSON content
            sam_data = json.loads(json_content)
            logger.info("Parsed SAM JSON", file_size=len(json_content))
            
            # Extract opportunities from the JSON structure
            opportunities = self._extract_opportunities(sam_data)
            logger.info("Extracted opportunities", count=len(opportunities))
            
            # Process each opportunity
            processed_count = 0
            for opportunity in opportunities:
                try:
                    self._process_single_opportunity(opportunity)
                    processed_count += 1
                except Exception as e:
                    logger.error("Failed to process opportunity", 
                               opportunity_id=opportunity.get('opportunity_id', 'unknown'),
                               error=str(e))
                    # Continue processing other opportunities
                    continue
            
            return {
                'source_file': object_key,
                'opportunities_found': len(opportunities),
                'opportunities_processed': processed_count
            }
            
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"Invalid JSON in file {object_key}: {str(e)}", ErrorType.DATA_ERROR)
        except Exception as e:
            raise RetryableError(f"Error processing file {object_key}: {str(e)}", ErrorType.SYSTEM_ERROR)
    
    def _extract_opportunities(self, sam_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual opportunities from SAM JSON structure."""
        opportunities = []
        
        # Handle different possible JSON structures from SAM.gov API
        if 'opportunitiesData' in sam_data:
            opportunities = sam_data['opportunitiesData']
        elif 'opportunities' in sam_data:
            opportunities = sam_data['opportunities']
        elif isinstance(sam_data, list):
            opportunities = sam_data
        else:
            logger.warning("Unexpected SAM JSON structure", keys=list(sam_data.keys()))
            # Try to find opportunities in nested structures
            for key, value in sam_data.items():
                if isinstance(value, list) and len(value) > 0:
                    # Check if this looks like opportunities data
                    first_item = value[0]
                    if isinstance(first_item, dict) and any(field in first_item for field in 
                                                          ['solicitation_number', 'opportunity_id', 'title']):
                        opportunities = value
                        break
        
        logger.info("Extracted opportunities from JSON", count=len(opportunities))
        return opportunities
    
    def _process_single_opportunity(self, opportunity: Dict[str, Any]) -> None:
        """Process a single opportunity and store it with resources."""
        # Get opportunity identifier
        opportunity_number = self._get_opportunity_number(opportunity)
        if not opportunity_number:
            raise NonRetryableError("Opportunity missing required identifier", ErrorType.DATA_ERROR)

        logger.info("Processing opportunity", opportunity_number=opportunity_number)

        # Add a consistent 'id' field to the opportunity
        opportunity['id'] = opportunity_number

        # Create date-based folder structure (YYYY-MM-DD)
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Create the opportunity folder structure with date prefix
        opportunity_folder = f"{current_date}/{opportunity_number}/"
        opportunity_file_key = f"{opportunity_folder}{opportunity_number}_opportunity.json"

        # Store the opportunity JSON
        self._store_opportunity_json(opportunity, opportunity_file_key)

        # Download and store resource files
        resource_links = opportunity.get('resourceLinks', [])
        if resource_links:
            self._download_resource_files(resource_links, opportunity_number, opportunity_folder)

        logger.info("Completed processing opportunity", 
                   opportunity_number=opportunity_number,
                   resource_files=len(resource_links))
    
    def _get_opportunity_number(self, opportunity: Dict[str, Any]) -> Optional[str]:
        """Extract opportunity number from opportunity data."""
        # Try different possible field names for opportunity identifier
        for field in ['opportunity_number', 'solicitation_number', 'opportunity_id', 'solicitationNumber']:
            if field in opportunity and opportunity[field]:
                raw_number = str(opportunity[field]).strip()
                # URL decode to remove %28, %29 and other encoded characters
                decoded_number = unquote(raw_number)
                # Replace any remaining problematic characters with underscores
                clean_number = re.sub(r'[^\w\-.]', '_', decoded_number)
                return clean_number
        
        return None
    
    def _store_opportunity_json(self, opportunity: Dict[str, Any], s3_key: str) -> None:
        """Store opportunity JSON in S3."""
        try:
            json_content = json.dumps(opportunity, indent=2, default=str)
            
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=s3_key,
                Body=json_content,
                ContentType='application/json'
            )
            
            logger.info("Stored opportunity JSON", s3_key=s3_key, size=len(json_content))
            
        except Exception as e:
            raise RetryableError(f"Failed to store opportunity JSON: {str(e)}", ErrorType.SYSTEM_ERROR)
    
    def _download_resource_files(self, resource_links: List[str], opportunity_number: str, opportunity_folder: str) -> None:
        """Download resource files for an opportunity using concurrent processing."""
        if not resource_links:
            return
        
        logger.info("Downloading resource files", 
                   opportunity_number=opportunity_number,
                   resource_count=len(resource_links))
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=self.max_concurrent_downloads) as executor:
            # Submit download tasks with index for unique naming
            future_to_url = {
                executor.submit(self._download_single_resource, url, opportunity_number, opportunity_folder, idx): url
                for idx, url in enumerate(resource_links, 1)
            }
            
            # Process completed downloads
            successful_downloads = 0
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        successful_downloads += 1
                except Exception as e:
                    logger.error("Resource download failed", 
                               url=url, 
                               opportunity_number=opportunity_number,
                               error=str(e))
                    # Continue with other downloads
                    continue
        
        logger.info("Completed resource downloads", 
                   opportunity_number=opportunity_number,
                   successful=successful_downloads,
                   total=len(resource_links))
    
    def _download_single_resource(self, url: str, opportunity_number: str, opportunity_folder: str, file_index: int) -> bool:
        """Download a single resource file."""
        try:
            import requests
            
            # Try to extract meaningful filename from URL or Content-Disposition header
            filename = self._extract_filename_from_url(url, file_index)
            
            # Add opportunity number prefix to filename
            prefixed_filename = f"{opportunity_number}_{filename}"
            s3_key = f"{opportunity_folder}{prefixed_filename}"
            
            # Download the file with timeout
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Try to get a better filename from the actual response headers
            content_disposition = response.headers.get('content-disposition', '')
            if 'filename=' in content_disposition and 'attachment_' in prefixed_filename:
                try:
                    actual_filename = content_disposition.split('filename=')[1].strip('"').strip("'")
                    if actual_filename and actual_filename != 'download':
                        # Update the filename with the actual one from headers
                        prefixed_filename = f"{opportunity_number}_{actual_filename}"
                        s3_key = f"{opportunity_folder}{prefixed_filename}"
                except:
                    pass  # Keep the original filename if parsing fails
            
            # Upload to S3 in chunks to handle large files
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=s3_key,
                Body=response.content,
                ContentType=response.headers.get('content-type', 'application/octet-stream')
            )
            
            logger.info("Downloaded resource file", 
                       url=url,
                       s3_key=s3_key,
                       size=len(response.content))
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error("HTTP error downloading resource", url=url, error=str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error downloading resource", url=url, error=str(e))
            return False
    
    def _extract_filename_from_url(self, url: str, file_index: int) -> str:
        """Extract a meaningful filename from URL or generate a default one."""
        try:
            import requests
            
            # First, try to get filename from Content-Disposition header
            try:
                head_response = requests.head(url, timeout=10)
                content_disposition = head_response.headers.get('content-disposition', '')
                if 'filename=' in content_disposition:
                    # Extract filename from Content-Disposition header
                    filename_part = content_disposition.split('filename=')[1]
                    filename = filename_part.strip('"').strip("'")
                    if filename and filename != 'download':
                        return filename
            except:
                pass  # Continue to other methods if HEAD request fails
            
            # Try to extract from URL path
            parsed_url = urlparse(url)
            path_filename = os.path.basename(parsed_url.path)
            
            # Check if we got a meaningful filename from the path
            if path_filename and path_filename not in ['download', 'file', '']:
                # If it looks like a file ID, make it more descriptive
                if len(path_filename) > 20 and not '.' in path_filename:
                    # Looks like a UUID or long ID, add extension
                    return f"attachment_{file_index:02d}_{path_filename[:8]}.pdf"
                else:
                    return path_filename
            
            # Check if URL contains file ID that we can use
            if '/files/' in url:
                file_id = url.split('/files/')[-1].split('/')[0]
                if file_id and len(file_id) > 8:
                    return f"attachment_{file_index:02d}_{file_id[:8]}.pdf"
            
            # Default fallback with index
            return f"attachment_{file_index:02d}.pdf"
            
        except Exception as e:
            logger.warning(f"Error extracting filename from URL: {str(e)}")
            return f"attachment_{file_index:02d}.pdf"

@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for SAM JSON processing.
    
    Args:
        event: S3 PUT event
        context: Lambda context object
        
    Returns:
        dict: Response with status and message
    """
    logger.info("Starting SAM JSON processing", event=event)
    
    try:
        processor = OpportunityProcessor()
        result = processor.process_s3_event(event)
        
        logger.info("SAM JSON processing completed successfully", result=result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'SAM JSON processing completed successfully',
                'result': result,
                'correlation_id': logger.correlation_id
            })
        }
        
    except Exception as e:
        logger.error("SAM JSON processing failed", error=str(e))
        raise