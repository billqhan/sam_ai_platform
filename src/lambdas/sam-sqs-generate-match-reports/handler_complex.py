"""
SAM SQS generate match reports Lambda function handler.
Processes opportunities through Bedrock AI for matching.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any

from shared import (
    get_logger, 
    handle_lambda_error, 
    config,
    aws_clients
)
from shared.sqs_processor import create_sqs_processor, SQSMessageValidator
from shared.sqs_utils import S3EventMessage
from shared.bedrock_utils import get_bedrock_client
from shared.error_handling import RetryableError, ProcessingError
from shared.tracing import trace_lambda_handler, TracingContext, add_trace_annotation
from shared.metrics import get_business_metrics
from shared.logging_config import PerformanceTimer

logger = get_logger(__name__)

class OpportunityMatchProcessor:
    """Processes individual opportunities for AI matching."""
    
    def __init__(self):
        self.bedrock_client = get_bedrock_client()
        self.s3_client = aws_clients.s3
        self.business_metrics = get_business_metrics()
        
        # Configuration from environment variables
        self.debug_mode = config.get_debug_mode()
        self.process_delay_seconds = config.processing.process_delay_seconds
        self.match_threshold = config.processing.match_threshold
        self.max_attachment_files = config.processing.max_attachment_files
        self.max_description_chars = config.processing.max_description_chars
        self.max_attachment_chars = config.processing.max_attachment_chars
        
        # S3 bucket configuration
        self.output_bucket_sqs = config.s3.sam_matching_out_sqs
        self.output_bucket_runs = config.s3.sam_matching_out_runs
        
        # Model configuration
        self.model_id_desc = config.bedrock.model_id_desc
        self.model_id_match = config.bedrock.model_id_match
        
        if self.debug_mode:
            logger.info("Debug mode enabled", 
                       process_delay_seconds=self.process_delay_seconds,
                       match_threshold=self.match_threshold,
                       max_attachment_files=self.max_attachment_files,
                       max_description_chars=self.max_description_chars,
                       max_attachment_chars=self.max_attachment_chars,
                       model_id_desc=self.model_id_desc,
                       model_id_match=self.model_id_match)
    
    def process_opportunity_message(self, s3_message: S3EventMessage) -> Dict[str, Any]:
        """
        Process a single opportunity message from SQS.
        
        Args:
            s3_message: S3 event message containing opportunity file information
            
        Returns:
            Processing result dictionary
        """
        with PerformanceTimer(logger, "opportunity_processing") as timer:
            try:
                with TracingContext("opportunity_processing", "AI-RFP-Agent"):
                    opportunity_id = s3_message.object_key.split('/')[-2] if '/' in s3_message.object_key else 'unknown'
                    
                    logger.info("OPPORTUNITY_PROCESSED", 
                               bucket=s3_message.bucket_name,
                               object_key=s3_message.object_key,
                               opportunity_id=opportunity_id)
                    
                    add_trace_annotation('opportunity_id', opportunity_id)
                    add_trace_annotation('processing_stage', 'start')
                    
                    # Apply processing delay for rate limiting
                    if self.process_delay_seconds > 0:
                        logger.debug("Applying processing delay", 
                                   delay_seconds=self.process_delay_seconds)
                        time.sleep(self.process_delay_seconds)
                    
                    # Download and parse opportunity JSON
                    with TracingContext("download_opportunity_data"):
                        opportunity_data = self._download_opportunity_data(s3_message)
                    
                    # Download and process attachments (if any)
                    with TracingContext("download_attachments"):
                        attachments = self._download_attachments(opportunity_data, s3_message)
                    
                    # Extract opportunity information using Bedrock
                    with TracingContext("extract_opportunity_info", "Bedrock"):
                        opportunity_info = self._extract_opportunity_info(opportunity_data, attachments)
                    
                    # Calculate company match using Bedrock and knowledge base
                    with TracingContext("calculate_company_match", "Bedrock"):
                        match_result = self._calculate_company_match(opportunity_info, opportunity_data)
                    
                    # Store results and generate run summary
                    with TracingContext("store_results", "S3"):
                        self._store_match_results(match_result, opportunity_data, s3_message)
                    
                    # Record business metrics
                    self.business_metrics.record_opportunity_processed(success=True)
                    self.business_metrics.record_match_result(
                        is_match=match_result.get('is_match', False),
                        score=match_result.get('match_score', 0.0)
                    )
                    
                    processing_time = timer.start_time and (datetime.utcnow() - timer.start_time).total_seconds()
                    
                    logger.info("Opportunity processing completed successfully",
                               opportunity_id=opportunity_data.get('solicitationNumber', opportunity_data.get('opportunity_id')),
                               match_score=match_result.get('match_score'),
                               is_match=match_result.get('is_match'),
                               processing_time_seconds=processing_time)
                    
                    # Log business events
                    if match_result.get('is_match', False):
                        logger.business_event("MATCH_FOUND", 
                                            opportunity_id=opportunity_id,
                                            match_score=match_result.get('match_score'))
                    else:
                        logger.business_event("NO_MATCH_FOUND", 
                                            opportunity_id=opportunity_id,
                                            match_score=match_result.get('match_score'))
                    
                    add_trace_annotation('processing_stage', 'complete')
                    add_trace_annotation('match_score', match_result.get('match_score', 0.0))
                    add_trace_annotation('is_match', match_result.get('is_match', False))
                    
                    return {
                        'success': True,
                        'opportunity_id': opportunity_data.get('solicitationNumber', opportunity_data.get('opportunity_id')),
                        'match_score': match_result.get('match_score'),
                        'processing_time_seconds': processing_time
                    }
                    
            except Exception as e:
                processing_time = timer.start_time and (datetime.utcnow() - timer.start_time).total_seconds()
                error_msg = f"Failed to process opportunity: {str(e)}"
                
                logger.error("OPPORTUNITY_PROCESSING_FAILED", 
                           error=str(e),
                           error_type=type(e).__name__,
                           bucket=s3_message.bucket_name,
                           object_key=s3_message.object_key,
                           processing_time_seconds=processing_time)
                
                # Record business metrics
                self.business_metrics.record_opportunity_processed(success=False)
                
                # Store error result
                try:
                    self._store_error_result(s3_message, error_msg)
                except Exception as store_error:
                    logger.error("Failed to store error result", 
                               store_error=str(store_error))
                
                add_trace_annotation('processing_stage', 'error')
                add_trace_annotation('error_type', type(e).__name__)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'processing_time_seconds': processing_time
                }
    
    def _download_opportunity_data(self, s3_message: S3EventMessage) -> Dict[str, Any]:
        """Download and parse opportunity JSON from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=s3_message.bucket_name,
                Key=s3_message.object_key
            )
            
            content = response['Body'].read().decode('utf-8')
            opportunity_data = json.loads(content)
            
            if self.debug_mode:
                logger.info(f"Downloaded opportunity data: {len(content)} characters")
            
            return opportunity_data
            
        except Exception as e:
            raise ProcessingError(f"Failed to download opportunity data: {str(e)}")
    
    def _download_attachments(self, opportunity_data: Dict[str, Any], s3_message: S3EventMessage) -> list:
        """Download and process attachment files."""
        attachments = []
        
        try:
            # Get resource links from opportunity data
            resource_links = opportunity_data.get('resource_links', [])
            
            if not resource_links:
                if self.debug_mode:
                    logger.info("No resource links found in opportunity data")
                return attachments
            
            # Extract opportunity number for file prefix matching
            opportunity_number = opportunity_data.get('opportunity_id', 'unknown')
            
            # Look for attachment files in the same S3 location
            # Files should be prefixed with opportunity_number
            bucket_name = s3_message.bucket_name
            object_prefix = s3_message.object_key.rsplit('/', 1)[0] + '/'  # Get directory path
            
            if self.debug_mode:
                logger.info(f"Looking for attachments with prefix: {object_prefix}{opportunity_number}")
            
            # List objects with the opportunity number prefix
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=f"{object_prefix}{opportunity_number}",
                    MaxKeys=self.max_attachment_files + 1  # +1 for the opportunity.json file
                )
                
                attachment_files = []
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    # Skip the opportunity.json file itself
                    if not key.endswith('opportunity.json'):
                        attachment_files.append(key)
                
                # Limit to max attachment files
                attachment_files = attachment_files[:self.max_attachment_files]
                
                if self.debug_mode:
                    logger.info(f"Found {len(attachment_files)} attachment files")
                
                # Download and process each attachment
                total_chars = 0
                for file_key in attachment_files:
                    if total_chars >= self.max_attachment_chars:
                        if self.debug_mode:
                            logger.info(f"Reached max attachment characters limit: {self.max_attachment_chars}")
                        break
                    
                    try:
                        # Download file content
                        file_response = self.s3_client.get_object(
                            Bucket=bucket_name,
                            Key=file_key
                        )
                        
                        content = file_response['Body'].read()
                        
                        # Try to decode as text (handle different file types)
                        try:
                            if file_key.lower().endswith(('.txt', '.md', '.json', '.xml', '.html', '.csv')):
                                text_content = content.decode('utf-8')
                            elif file_key.lower().endswith('.pdf'):
                                # For PDF files, we'd need a PDF parser, but for now just note the file
                                text_content = f"[PDF File: {file_key.split('/')[-1]} - Content extraction not implemented]"
                            else:
                                # For other file types, just note the file
                                text_content = f"[File: {file_key.split('/')[-1]} - Content type not supported for text extraction]"
                            
                            # Truncate if too long
                            remaining_chars = self.max_attachment_chars - total_chars
                            if len(text_content) > remaining_chars:
                                text_content = text_content[:remaining_chars] + "... [truncated]"
                            
                            attachments.append(text_content)
                            total_chars += len(text_content)
                            
                            if self.debug_mode:
                                logger.info(f"Processed attachment {file_key}: {len(text_content)} characters")
                        
                        except UnicodeDecodeError:
                            # Binary file that can't be decoded as text
                            file_name = file_key.split('/')[-1]
                            placeholder = f"[Binary File: {file_name} - Content not readable as text]"
                            attachments.append(placeholder)
                            total_chars += len(placeholder)
                            
                            if self.debug_mode:
                                logger.info(f"Skipped binary file {file_key}")
                    
                    except Exception as e:
                        logger.warning(f"Failed to download attachment {file_key}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.warning(f"Failed to list attachment files: {str(e)}")
            
            if self.debug_mode:
                logger.info(f"Downloaded {len(attachments)} attachments, total characters: {total_chars}")
            
            return attachments
            
        except Exception as e:
            logger.error(f"Error processing attachments: {str(e)}")
            return []
    
    def _extract_opportunity_info(self, opportunity_data: Dict[str, Any], attachments: list) -> str:
        """Extract opportunity information using Bedrock LLM."""
        try:
            logger.info("Extracting opportunity info using Bedrock",
                       model_id=self.model_id_desc,
                       attachments_count=len(attachments))
            
            with PerformanceTimer(logger, "bedrock_extract_opportunity_info"):
                # Use the bedrock_utils method for opportunity info extraction
                opportunity_info = self.bedrock_client.extract_opportunity_info(
                    opportunity_data=opportunity_data,
                    attachments=attachments
                )
            
            # Record successful Bedrock call
            self.business_metrics.record_bedrock_call(success=True, model_id=self.model_id_desc)
            logger.api_call("Bedrock", "extract_opportunity_info", success=True)
            
            logger.info("Successfully extracted opportunity info",
                       info_length=len(opportunity_info))
            
            return opportunity_info
            
        except Exception as e:
            error_msg = f"Failed to extract opportunity information: {str(e)}"
            
            # Record failed Bedrock call
            self.business_metrics.record_bedrock_call(success=False, model_id=self.model_id_desc)
            logger.api_call("Bedrock", "extract_opportunity_info", success=False, error=str(e))
            
            logger.error("BEDROCK_CALL_FAILED", 
                        operation="extract_opportunity_info",
                        model_id=self.model_id_desc,
                        error=str(e))
            
            # Return a fallback summary based on available data
            title = opportunity_data.get('title', 'Unknown Title')
            description = opportunity_data.get('description', 'No description available')
            
            # Truncate description if too long
            if len(description) > self.max_description_chars:
                description = description[:self.max_description_chars] + "... [truncated]"
            
            fallback_info = f"""
OPPORTUNITY TITLE: {title}

DESCRIPTION: {description}

ATTACHMENTS: {len(attachments)} attachment(s) processed

ERROR: {error_msg}

This is a fallback summary due to AI processing failure. Manual review recommended.
"""
            
            return fallback_info
    
    def _calculate_company_match(self, opportunity_info: str, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate company match using Bedrock and knowledge base."""
        try:
            logger.info("Calculating company match using Bedrock",
                       model_id=self.model_id_match,
                       match_threshold=self.match_threshold)
            
            with PerformanceTimer(logger, "bedrock_calculate_company_match"):
                # Use the bedrock_utils method for company matching
                match_result = self.bedrock_client.calculate_company_match(
                    opportunity_info=opportunity_info,
                    opportunity_data=opportunity_data
                )
            
            # Record successful Bedrock call
            self.business_metrics.record_bedrock_call(success=True, model_id=self.model_id_match)
            logger.api_call("Bedrock", "calculate_company_match", success=True)
            
            # Ensure match_result has all required fields with defaults
            required_fields = {
                'match_score': 0.0,
                'is_match': False,
                'rationale': 'No analysis available',
                'citations': [],
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': []
            }
            
            # Fill in any missing fields with defaults
            for field, default_value in required_fields.items():
                if field not in match_result:
                    match_result[field] = default_value
            
            # Apply match threshold to determine is_match
            match_score = float(match_result.get('match_score', 0.0))
            match_result['is_match'] = match_score >= self.match_threshold
            
            # Add opportunity summary information
            match_result['opportunity_summary'] = {
                'title': opportunity_data.get('title', 'Unknown Title'),
                'value': opportunity_data.get('award_amount', opportunity_data.get('estimated_value', 'Not specified')),
                'deadline': opportunity_data.get('responseDeadLine', opportunity_data.get('response_deadline', opportunity_data.get('due_date', 'Not specified'))),
                'naics_codes': opportunity_data.get('naicsCodes', opportunity_data.get('naics_codes', []))
            }
            
            # Add processing metadata
            match_result['processed_timestamp'] = datetime.now().isoformat()
            match_result['solicitation_id'] = opportunity_data.get('solicitationNumber', opportunity_data.get('solicitation_number', opportunity_data.get('opportunity_id', 'unknown')))
            match_result['match_threshold'] = self.match_threshold
            
            logger.info("Company match calculated successfully",
                       match_score=match_result['match_score'],
                       is_match=match_result['is_match'],
                       citations_count=len(match_result.get('citations', [])),
                       opportunity_skills_count=len(match_result.get('opportunity_required_skills', [])),
                       company_skills_count=len(match_result.get('company_skills', [])))
            
            # Log match score as a business event
            logger.business_event("MATCH_SCORE", 
                                score=match_result['match_score'],
                                is_match=match_result['is_match'])
            
            return match_result
            
        except Exception as e:
            error_msg = f"Failed to calculate company match: {str(e)}"
            
            # Record failed Bedrock call
            self.business_metrics.record_bedrock_call(success=False, model_id=self.model_id_match)
            logger.api_call("Bedrock", "calculate_company_match", success=False, error=str(e))
            
            logger.error("BEDROCK_CALL_FAILED",
                        operation="calculate_company_match", 
                        model_id=self.model_id_match,
                        error=str(e))
            
            # Return a fallback match result
            fallback_result = {
                'match_score': 0.0,
                'is_match': False,
                'rationale': f'Error during matching analysis: {error_msg}',
                'citations': [],
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': [],
                'opportunity_summary': {
                    'title': opportunity_data.get('title', 'Unknown Title'),
                    'value': opportunity_data.get('award_amount', opportunity_data.get('estimated_value', 'Not specified')),
                    'deadline': opportunity_data.get('responseDeadLine', opportunity_data.get('response_deadline', opportunity_data.get('due_date', 'Not specified'))),
                    'naics_codes': opportunity_data.get('naicsCodes', opportunity_data.get('naics_codes', []))
                },
                'processed_timestamp': datetime.now().isoformat(),
                'solicitation_id': opportunity_data.get('solicitationNumber', opportunity_data.get('solicitation_number', opportunity_data.get('opportunity_id', 'unknown'))),
                'match_threshold': self.match_threshold
            }
            
            return fallback_result
    
    def _store_match_results(self, match_result: Dict[str, Any], opportunity_data: Dict[str, Any], s3_message: S3EventMessage):
        """Store match results and generate run summary."""
        try:
            solicitation_id = match_result.get('solicitation_id', 'unknown')
            is_match = match_result.get('is_match', False)
            match_score = match_result.get('match_score', 0.0)
            
            # Determine category based on match result
            if is_match:
                category = 'matches'
            else:
                category = 'no_matches'
            
            # Create date-based folder structure (YYYY-MM-DD)
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Store match result in categorized folder
            result_key = f"{current_date}/{category}/{solicitation_id}.json"
            
            try:
                self.s3_client.put_object(
                    Bucket=self.output_bucket_sqs,
                    Key=result_key,
                    Body=json.dumps(match_result, indent=2),
                    ContentType='application/json'
                )
                
                if self.debug_mode:
                    logger.info(f"Stored match result: {result_key}")
            
            except Exception as e:
                logger.error(f"Failed to store match result: {str(e)}")
                raise
            
            # Generate and store run summary
            self._generate_run_summary(match_result, opportunity_data, category)
            
        except Exception as e:
            logger.error(f"Failed to store match results: {str(e)}")
            raise
    
    def _store_error_result(self, s3_message: S3EventMessage, error_msg: str):
        """Store error result for failed processing."""
        try:
            # Extract solicitation ID from S3 object key or use a fallback
            object_key = s3_message.object_key
            if '/' in object_key:
                # Extract opportunity number from path like "opportunity_123/opportunity.json"
                solicitation_id = object_key.split('/')[-2]
            else:
                # Fallback to using the object key itself
                solicitation_id = object_key.replace('.json', '').replace('opportunity', 'unknown')
            
            # Create date-based folder structure (YYYY-MM-DD)
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Create error result
            error_result = {
                'solicitation_id': solicitation_id,
                'processed_timestamp': datetime.now().isoformat(),
                'error': error_msg,
                'source_bucket': s3_message.bucket_name,
                'source_key': s3_message.object_key,
                'match_score': 0.0,
                'is_match': False,
                'rationale': f'Processing failed: {error_msg}',
                'citations': [],
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': [],
                'opportunity_summary': {
                    'title': 'Processing Failed',
                    'value': 'Unknown',
                    'deadline': 'Unknown',
                    'naics_codes': []
                },
                'match_threshold': self.match_threshold
            }
            
            # Store error result in errors folder
            error_key = f"{current_date}/errors/{solicitation_id}.json"
            
            try:
                self.s3_client.put_object(
                    Bucket=self.output_bucket_sqs,
                    Key=error_key,
                    Body=json.dumps(error_result, indent=2),
                    ContentType='application/json'
                )
                
                if self.debug_mode:
                    logger.info(f"Stored error result: {error_key}")
            
            except Exception as e:
                logger.error(f"Failed to store error result: {str(e)}")
                raise
            
            # Generate run summary for error
            self._generate_run_summary(error_result, {}, 'errors')
            
        except Exception as e:
            logger.error(f"Failed to store error result: {str(e)}")
            # Don't re-raise here to avoid infinite error loops
    
    def _generate_run_summary(self, match_result: Dict[str, Any], opportunity_data: Dict[str, Any], category: str):
        """Generate individual run summary for sam-matching-out-runs bucket."""
        try:
            # Create run summary
            run_summary = {
                'run_id': f"{datetime.now().strftime('%Y%m%dt%H%M%S')}_{match_result.get('solicitation_id', 'unknown')}",
                'timestamp': datetime.now().isoformat(),
                'date_prefix': datetime.now().strftime('%Y%m%d'),
                'solicitation_id': match_result.get('solicitation_id', 'unknown'),
                'category': category,
                'match_score': match_result.get('match_score', 0.0),
                'is_match': match_result.get('is_match', False),
                'opportunity_title': match_result.get('opportunity_summary', {}).get('title', opportunity_data.get('title', 'Unknown')),
                'processing_status': 'success' if category != 'errors' else 'error',
                'error_message': match_result.get('error') if category == 'errors' else None
            }
            
            # Store run summary in runs folder
            timestamp = datetime.now().strftime('%Y%m%dt%H%MZ')
            run_key = f"runs/{timestamp}_{match_result.get('solicitation_id', 'unknown')}.json"
            
            try:
                self.s3_client.put_object(
                    Bucket=self.output_bucket_runs,
                    Key=run_key,
                    Body=json.dumps(run_summary, indent=2),
                    ContentType='application/json'
                )
                
                if self.debug_mode:
                    logger.info(f"Stored run summary: {run_key}")
            
            except Exception as e:
                logger.error(f"Failed to store run summary: {str(e)}")
                # Don't raise here to avoid breaking the main processing flow
            
        except Exception as e:
            logger.error(f"Failed to generate run summary: {str(e)}")
            # Don't raise here to avoid breaking the main processing flow

# Global processor instance
processor = OpportunityMatchProcessor()

def process_single_message(s3_message: S3EventMessage) -> Any:
    """
    Process a single S3 event message for opportunity matching.
    
    Args:
        s3_message: S3 event message from SQS
        
    Returns:
        Processing result
    """
    return processor.process_opportunity_message(s3_message)

# Create SQS batch processor
sqs_processor = create_sqs_processor(process_single_message)

@trace_lambda_handler("sam_sqs_generate_match_reports")
@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for AI-powered opportunity matching.
    
    Args:
        event: SQS event with opportunity messages
        context: Lambda context object
        
    Returns:
        dict: Response with processing results
    """
    # Initialize logger with Lambda context for better tracing
    logger = get_logger(__name__, context=context)
    business_metrics = get_business_metrics()
    
    logger.info("Starting AI opportunity matching Lambda",
               function_name=context.function_name,
               request_id=context.aws_request_id,
               remaining_time_ms=context.get_remaining_time_in_millis(),
               debug_mode=config.get_debug_mode())
    
    # Add X-Ray annotations for filtering
    add_trace_annotation('function_name', 'sam-sqs-generate-match-reports')
    add_trace_annotation('environment', config.get_environment())
    add_trace_annotation('debug_mode', config.get_debug_mode())
    
    try:
        with TracingContext("sqs_event_validation"):
            # Validate SQS event structure
            SQSMessageValidator.validate_lambda_sqs_event(event)
            
            # Log SQS batch information
            records_count = len(event.get('Records', []))
            logger.info("Processing SQS batch", 
                       records_count=records_count)
            
            add_trace_annotation('sqs_records_count', records_count)
        
        with TracingContext("sqs_batch_processing"):
            # Process the SQS batch
            result = sqs_processor.process_lambda_event(event, context)
        
        # Record processing rate metric
        total_messages = result.get('totalMessages', 0)
        processing_time = context.get_remaining_time_in_millis() / 1000.0  # Convert to seconds
        if processing_time > 0:
            rate = total_messages / (processing_time / 60.0)  # opportunities per minute
            business_metrics.record_processing_rate(rate)
        
        logger.info("AI opportunity matching completed",
                   total_messages=result.get('totalMessages'),
                   successful_messages=result.get('successfulMessages'),
                   failed_messages=result.get('failedMessages'),
                   correlation_id=logger.correlation_id,
                   trace_id=logger.trace_id)
        
        # Log business event
        logger.business_event("BATCH_PROCESSING_COMPLETED",
                            total_messages=result.get('totalMessages'),
                            successful_messages=result.get('successfulMessages'),
                            failed_messages=result.get('failedMessages'))
        
        add_trace_annotation('batch_success', True)
        add_trace_annotation('total_messages', result.get('totalMessages', 0))
        add_trace_annotation('successful_messages', result.get('successfulMessages', 0))
        
        return result
        
    except Exception as e:
        logger.error("Lambda handler error", 
                    error=str(e),
                    error_type=type(e).__name__)
        
        # Log business event for failure
        logger.business_event("BATCH_PROCESSING_FAILED",
                            error=str(e),
                            error_type=type(e).__name__)
        
        add_trace_annotation('batch_success', False)
        add_trace_annotation('error_type', type(e).__name__)
        
        raise