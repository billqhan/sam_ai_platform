"""
SAM produce user report Lambda function handler.
Generates readable reports and email templates for matched opportunities.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import unquote_plus

from shared import (
    get_logger, 
    handle_lambda_error, 
    config, 
    aws_clients,
    handle_aws_error,
    RetryableError,
    NonRetryableError
)
from report_generator import ReportGenerator
from template_manager import TemplateManager

logger = get_logger(__name__)

class UserReportHandler:
    """Handler for user report generation from match results."""
    
    def __init__(self):
        self.s3_client = aws_clients.s3
        self.output_bucket = config.s3.sam_opportunity_responses
        self.company_info = config.get_company_info()
        self.template_manager = TemplateManager()
        self.report_generator = ReportGenerator(self.template_manager, self.company_info)
    
    @handle_aws_error
    def process_s3_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process S3 PUT event for match result files.
        
        Args:
            event: S3 event containing object information
            
        Returns:
            dict: Processing results summary
        """
        results = {
            'processed_files': 0,
            'successful_reports': 0,
            'failed_reports': 0,
            'errors': []
        }
        
        # Extract S3 records from event
        records = event.get('Records', [])
        if not records:
            logger.warning("No S3 records found in event")
            return results
        
        for record in records:
            try:
                # Parse S3 event record
                s3_info = record.get('s3', {})
                bucket_name = s3_info.get('bucket', {}).get('name')
                object_key = unquote_plus(s3_info.get('object', {}).get('key', ''))
                
                if not bucket_name or not object_key:
                    logger.warning("Invalid S3 record format", record=record)
                    continue
                
                logger.info("Processing match result file", 
                           bucket=bucket_name, 
                           key=object_key)
                
                # Only process JSON files in the correct structure
                if not self._is_valid_match_result_file(object_key):
                    logger.info("Skipping non-match result file", key=object_key)
                    continue
                
                results['processed_files'] += 1
                
                # Generate reports for this match result
                self._generate_reports_for_file(bucket_name, object_key)
                results['successful_reports'] += 1
                
                logger.info("Successfully generated reports", 
                           bucket=bucket_name, 
                           key=object_key)
                
            except Exception as e:
                error_msg = f"Failed to process record: {str(e)}"
                logger.error(error_msg, record=record, error=str(e))
                results['failed_reports'] += 1
                results['errors'].append(error_msg)
        
        return results
    
    def _is_valid_match_result_file(self, object_key: str) -> bool:
        """
        Check if the S3 object is a valid match result file.
        
        Args:
            object_key: S3 object key
            
        Returns:
            bool: True if valid match result file
        """
        # Expected pattern: YYYY-MM-DD/{category}/{solicitation_id}.json
        parts = object_key.split('/')
        if len(parts) != 3:
            return False
        
        date_part, category, filename = parts
        
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(date_part, '%Y-%m-%d')
        except ValueError:
            return False
        
        # Validate category
        valid_categories = ['matches', 'no_matches', 'errors']
        if category not in valid_categories:
            return False
        
        # Validate filename ends with .json
        if not filename.endswith('.json'):
            return False
        
        return True
    
    @handle_aws_error
    def _generate_reports_for_file(self, bucket_name: str, object_key: str) -> None:
        """
        Generate reports for a specific match result file.
        
        Args:
            bucket_name: S3 bucket name
            object_key: S3 object key
        """
        # Download and parse match result JSON
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            match_data = json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            raise RetryableError(f"Failed to download match result file: {str(e)}")
        
        # Extract solicitation ID from the match data
        solicitation_id = match_data.get('solicitation_id')
        if not solicitation_id:
            raise NonRetryableError("Match result missing solicitation_id")
        
        logger.info("Generating reports for opportunity", 
                   solicitation_id=solicitation_id)
        
        # Generate text report
        text_report = self.report_generator.generate_text_report(match_data)
        
        # Generate Word document
        word_doc_bytes = self.report_generator.generate_word_document(match_data)
        
        # Generate email template
        email_template = self.report_generator.generate_email_template(match_data)
        
        # Store all generated reports
        self._store_reports(solicitation_id, text_report, word_doc_bytes, email_template)
    
    @handle_aws_error
    def _store_reports(self, solicitation_id: str, text_report: str, 
                      word_doc_bytes: bytes, email_template: str) -> None:
        """
        Store generated reports in S3.
        
        Args:
            solicitation_id: Unique solicitation identifier
            text_report: Generated text report content
            word_doc_bytes: Generated Word document as bytes
            email_template: Generated email template content
        """
        base_key = f"{solicitation_id}"
        
        # Store text report
        text_key = f"{base_key}/report.txt"
        self.s3_client.put_object(
            Bucket=self.output_bucket,
            Key=text_key,
            Body=text_report.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Store Word document
        word_key = f"{base_key}/report.docx"
        self.s3_client.put_object(
            Bucket=self.output_bucket,
            Key=word_key,
            Body=word_doc_bytes,
            ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Store email template
        email_key = f"{base_key}/email_template.txt"
        self.s3_client.put_object(
            Bucket=self.output_bucket,
            Key=email_key,
            Body=email_template.encode('utf-8'),
            ContentType='text/plain'
        )
        
        logger.info("Stored all reports", 
                   solicitation_id=solicitation_id,
                   text_key=text_key,
                   word_key=word_key,
                   email_key=email_key)

# Global handler instance
handler = UserReportHandler()

@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for user report generation.
    
    Args:
        event: S3 PUT event for match results
        context: Lambda context object
        
    Returns:
        dict: Response with status and processing results
    """
    logger.info("Starting user report generation", event=event)
    
    try:
        # Process the S3 event
        results = handler.process_s3_event(event)
        
        logger.info("User report generation completed", results=results)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'User report generation completed successfully',
                'results': results,
                'correlation_id': logger.correlation_id
            })
        }
        
    except Exception as e:
        logger.error("User report generation failed", error=str(e))
        raise