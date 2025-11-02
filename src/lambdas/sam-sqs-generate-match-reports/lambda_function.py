"""
Enhanced Lambda function for generating match reports using LLM analysis.
Replaces hardcoded debug output with real Bedrock LLM-based opportunity matching.
"""
import json
import sys
import os
import time
from datetime import datetime
import logging
from typing import Dict, Any, List

# Add shared modules to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))

try:
    from shared.llm_data_extraction import get_llm_data_extractor, get_bedrock_llm_client
    from shared.config import config
    from shared.aws_clients import aws_clients
    from shared.error_handling import ErrorHandler
except ImportError as e:
    # Fallback imports for Lambda environment
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))
    
    from llm_data_extraction import get_llm_data_extractor, get_bedrock_llm_client
    from config import config
    from aws_clients import aws_clients
    from error_handling import ErrorHandler

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Enhanced Lambda handler that uses LLM analysis for opportunity matching.
    
    Args:
        event: SQS event containing S3 object references
        context: Lambda context object
        
    Returns:
        Response with processing results
    """
    logger.info("🚀 LLM MATCH REPORTS LAMBDA STARTED")
    logger.info(f"📋 Event: {json.dumps(event, default=str)}")
    
    # Initialize services
    data_extractor = get_llm_data_extractor()
    llm_client = get_bedrock_llm_client()
    error_handler = ErrorHandler(debug_mode=config.get_debug_mode())
    
    # Initialize Bedrock client
    if not llm_client.initialize_bedrock_client():
        logger.error("Failed to initialize Bedrock client")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to initialize Bedrock client',
                'message': 'LLM services unavailable'
            })
        }
    
    # Target buckets
    sqs_bucket = config.s3.sam_matching_out_sqs
    runs_bucket = config.s3.sam_matching_out_runs
    
    logger.info(f"📋 Target buckets:")
    logger.info(f"  - SQS bucket: {sqs_bucket}")
    logger.info(f"  - Runs bucket: {runs_bucket}")
    
    try:
        # Process each SQS record
        records = event.get('Records', [])
        logger.info(f"📊 Processing {len(records)} SQS records")
        
        results = []
        
        for i, record in enumerate(records):
            logger.info(f"🔍 Processing record {i+1}/{len(records)}")
            
            try:
                result = process_sqs_record(
                    record, 
                    data_extractor, 
                    llm_client, 
                    sqs_bucket, 
                    runs_bucket,
                    error_handler
                )
                results.append(result)
                
            except Exception as record_error:
                error_category = error_handler.categorize_error(record_error)
                logger.error(f"❌ Failed to process record {i+1}: {record_error}")
                
                # Create comprehensive error result
                error_result = {
                    'message_id': record.get('messageId', f'unknown_{i}'),
                    'success': False,
                    'error': str(record_error),
                    'error_type': error_category,
                    'processing_stage': 'record_processing',
                    'timestamp': datetime.now().isoformat()
                }
                
                # Add debug info if enabled
                if error_handler.debug_mode:
                    error_result['debug_info'] = {
                        'error_class': type(record_error).__name__,
                        'record_data': record
                    }
                
                results.append(error_result)
        
        # Summary
        successful = len([r for r in results if r.get('success', False)])
        failed = len([r for r in results if not r.get('success', False)])
        
        logger.info(f"📊 PROCESSING SUMMARY:")
        logger.info(f"  Total messages: {len(results)}")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Failed: {failed}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'LLM match report processing completed',
                'total_messages': len(results),
                'successful_messages': successful,
                'failed_messages': failed,
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"💥 LAMBDA ERROR: {e}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Lambda processing failed'
            })
        }


def process_sqs_record(record: Dict[str, Any], 
                      data_extractor, 
                      llm_client, 
                      sqs_bucket: str, 
                      runs_bucket: str,
                      error_handler: ErrorHandler) -> Dict[str, Any]:
    """
    Process a single SQS record using LLM analysis with comprehensive error handling.
    
    Args:
        record: SQS record containing S3 event information
        data_extractor: LLM data extraction utility
        llm_client: Bedrock LLM client
        sqs_bucket: Target bucket for match results
        runs_bucket: Target bucket for run summaries
        error_handler: Error handling utility
        
    Returns:
        Processing result dictionary
    """
    message_id = record.get('messageId', 'unknown')
    message_body = record.get('body', '{}')
    opportunity_id = None
    
    logger.info(f"📄 Processing message ID: {message_id}")
    
    try:
        # Parse the message body to get S3 info
        error_handler.update_stage("message_parsing")
        body_data = json.loads(message_body)
        s3_records = body_data.get('Records', [])
        
        if not s3_records:
            raise ValueError("No S3 records found in message body")
        
        s3_record = s3_records[0]
        if 's3' not in s3_record:
            raise ValueError("No S3 info found in record")
        
        s3_info = s3_record['s3']
        source_bucket = s3_info.get('bucket', {}).get('name', '')
        source_key = s3_info.get('object', {}).get('key', '')
        
        if not source_bucket or not source_key:
            raise ValueError("Missing S3 bucket or key information")
        
        logger.info(f"📋 S3 Event Details:")
        logger.info(f"  Source bucket: {source_bucket}")
        logger.info(f"  Source key: {source_key}")
        
        # Extract opportunity ID from key
        opportunity_id = data_extractor.extract_opportunity_id(source_key)
        logger.info(f"📊 Opportunity ID: {opportunity_id}")
        
        # Start comprehensive error tracking
        error_handler.start_processing(opportunity_id, "data_extraction")
        
        # Step 1: Read opportunity data from S3
        error_handler.update_stage("reading_opportunity_data", opportunity_id)
        logger.info("🔍 Step 1: Reading opportunity data")
        
        try:
            # Log S3 read operation
            error_handler.log_s3_operation("read", source_bucket, source_key)
            
            opportunity_data = data_extractor.read_opportunity_data(source_bucket, source_key)
            
            # Log successful read with file size if available
            if opportunity_data:
                data_size = len(json.dumps(opportunity_data))
                error_handler.log_s3_operation("read", source_bucket, source_key, 
                                             success=True, file_size=data_size)
            
            # Validate opportunity data
            if not data_extractor.validate_opportunity_data(opportunity_data):
                raise ValueError("Opportunity data validation failed")
                
        except Exception as e:
            # Log S3 operation failure
            error_handler.log_s3_operation("read", source_bucket, source_key, 
                                         success=False, error=e)
            error_handler.log_error(opportunity_id, e, {
                'stage': 'data_extraction',
                'source_bucket': source_bucket,
                'source_key': source_key
            })
            raise
        
        # Step 2: Read attachment files
        error_handler.update_stage("reading_attachments", opportunity_id)
        logger.info("🔍 Step 2: Reading attachment files")
        
        try:
            attachments = data_extractor.read_attachment_files(source_bucket, opportunity_id)
            logger.info(f"Found {len(attachments)} attachment files")
            
            # Log progress update for attachment processing
            error_handler.log_progress_update(opportunity_id, "attachment_reading", {
                'attachments_found': len(attachments),
                'source_bucket': source_bucket
            })
            
        except Exception as e:
            # Non-critical error - continue with empty attachments
            error_handler.log_error(opportunity_id, e, {
                'stage': 'attachment_reading',
                'source_bucket': source_bucket,
                'opportunity_id': opportunity_id
            })
            attachments = []
            logger.warning("Continuing without attachments due to read error")
        
        # Step 3: Prepare content for LLM processing
        error_handler.update_stage("content_preparation", opportunity_id)
        logger.info("🔍 Step 3: Preparing content for LLM")
        
        try:
            description, attachment_content = data_extractor.prepare_opportunity_content(
                opportunity_data, attachments
            )
        except Exception as e:
            error_handler.log_error(opportunity_id, e, {
                'stage': 'content_preparation',
                'attachments_count': len(attachments)
            })
            # Use basic fallback
            description = f"Title: {opportunity_data.get('title', 'Unknown')}\nDescription: {opportunity_data.get('description', 'No description available')}"
            attachment_content = "No attachment content available due to processing error"
        
        # Step 4: Extract opportunity information using LLM
        error_handler.update_stage("llm_opportunity_extraction", opportunity_id)
        logger.info("🔍 Step 4: Extracting opportunity information using LLM")
        
        llm_processing_status = "failed"
        enhanced_description = None
        opportunity_required_skills = []
        
        try:
            # Log progress update before LLM call
            error_handler.log_progress_update(opportunity_id, "llm_opportunity_extraction", {
                'model_id': llm_client.model_id_desc,
                'prompt_length': len(description) + len(attachment_content),
                'attachment_count': len(attachments)
            })
            
            # Log LLM request details
            error_handler.log_llm_request(
                llm_client.model_id_desc,
                len(description) + len(attachment_content),
                {
                    'max_tokens': llm_client.max_tokens, 
                    'temperature': llm_client.temperature,
                    'estimated_tokens': (len(description) + len(attachment_content)) // 4  # Rough estimate
                }
            )
            
            start_time = time.time()
            enhanced_description, opportunity_required_skills = llm_client.extract_opportunity_info(
                description, attachment_content
            )
            processing_time = time.time() - start_time
            llm_success = True  # If we get here without exception, it was successful
            
            # Log LLM response details
            error_handler.log_llm_response(
                llm_client.model_id_desc,
                len(enhanced_description or ''),
                processing_time,
                {
                    'skills_extracted': len(opportunity_required_skills or []),
                    'structured_format': "BUSINESS SUMMARY:" in (enhanced_description or '')
                }
            )
            
            if llm_success:
                llm_processing_status = "success"
                logger.info(f"✅ LLM opportunity extraction successful")
            else:
                llm_processing_status = "failed"
                logger.warning(f"⚠️ LLM opportunity extraction failed, using fallback")
            
        except Exception as e:
            # Enhanced error logging for LLM failures (Requirement 1.5)
            error_handler.log_error(opportunity_id, e, {
                'stage': 'llm_opportunity_extraction',
                'model_id': llm_client.model_id_desc,
                'prompt_length': len(description) + len(attachment_content),
                'attachment_count': len(attachments),
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0
            })
            
            # Apply graceful degradation
            fallback_data = {
                'original_description': description,
                'opportunity_data': opportunity_data
            }
            degraded_result = error_handler.handle_graceful_degradation(e, fallback_data)
            enhanced_description = degraded_result.get('enhanced_description')
            opportunity_required_skills = degraded_result.get('opportunity_required_skills', [])
        
        # Step 5: Calculate company match using Knowledge Base and LLM
        error_handler.update_stage("company_match_calculation", opportunity_id)
        logger.info("🔍 Step 5: Calculating company match using Knowledge Base and LLM")
        
        match_processing_status = "failed"
        company_match_result = {}
        
        try:
            # Log progress update before company match calculation
            error_handler.log_progress_update(opportunity_id, "company_match_calculation", {
                'model_id': llm_client.model_id_match,
                'enhanced_description_length': len(enhanced_description or ''),
                'skills_count': len(opportunity_required_skills)
            })
            
            # Log LLM request details
            error_handler.log_llm_request(
                llm_client.model_id_match,
                len(enhanced_description or '') + len(str(opportunity_required_skills)),
                {
                    'max_tokens': llm_client.max_tokens, 
                    'temperature': llm_client.temperature,
                    'estimated_tokens': (len(enhanced_description or '') + len(str(opportunity_required_skills))) // 4
                }
            )
            
            start_time = time.time()
            company_match_result, match_success = llm_client.calculate_company_match(
                enhanced_description, opportunity_required_skills,
                error_handler=error_handler, opportunity_id=opportunity_id
            )
            processing_time = time.time() - start_time
            
            # Log LLM response details
            error_handler.log_llm_response(
                llm_client.model_id_match,
                len(str(company_match_result)),
                processing_time,
                {
                    'match_score': company_match_result.get('score'),
                    'kb_results_count': len(company_match_result.get('kb_retrieval_results', [])),
                    'citations_count': len(company_match_result.get('citations', []))
                }
            )
            
            if match_success:
                match_processing_status = "success"
                logger.info(f"✅ Company match calculation successful: score={company_match_result['score']}")
            else:
                match_processing_status = "failed"
                logger.warning(f"⚠️ Company match calculation failed: score={company_match_result['score']}")
            
        except Exception as e:
            # Enhanced error logging for match calculation failures
            error_handler.log_error(opportunity_id, e, {
                'stage': 'company_match_calculation',
                'model_id': llm_client.model_id_match,
                'enhanced_description_length': len(enhanced_description or ''),
                'skills_count': len(opportunity_required_skills),
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0
            })
            
            # Apply graceful degradation
            fallback_data = {
                'opportunity_required_skills': opportunity_required_skills,
                'enhanced_description': enhanced_description
            }
            degraded_result = error_handler.handle_graceful_degradation(e, fallback_data)
            company_match_result = {
                'score': degraded_result.get('score', 0.0),
                'rationale': degraded_result.get('rationale', 'Match calculation failed'),
                'opportunity_required_skills': opportunity_required_skills or [],
                'company_skills': degraded_result.get('company_skills', []),
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': []
            }
        
        # Step 6: Create enhanced match result
        error_handler.update_stage("result_creation", opportunity_id)
        
        try:
            match_result = create_enhanced_match_result(
                opportunity_data,
                opportunity_id,
                enhanced_description,
                opportunity_required_skills,
                company_match_result,
                attachment_content,
                source_bucket,
                source_key,
                message_id,
                llm_processing_status,
                match_processing_status
            )
        except Exception as e:
            error_handler.log_error(opportunity_id, e, {
                'stage': 'result_creation'
            })
            raise
        
        # Step 7: Write results to S3
        error_handler.update_stage("s3_output", opportunity_id)
        
        try:
            # Log progress update before S3 write
            error_handler.log_progress_update(opportunity_id, "s3_output", {
                'sqs_bucket': sqs_bucket,
                'runs_bucket': runs_bucket,
                'match_score': match_result.get('score', 0.0)
            })
            
            sqs_key, runs_key, category = write_results_to_s3(
                match_result,
                opportunity_id,
                sqs_bucket,
                runs_bucket,
                error_handler
            )
        except Exception as e:
            error_handler.log_error(opportunity_id, e, {
                'stage': 's3_output',
                'sqs_bucket': sqs_bucket,
                'runs_bucket': runs_bucket
            })
            raise
        
        # Log successful processing summary
        processing_details = {
            'attachments_processed': len(attachments),
            'llm_processing_status': llm_processing_status,
            'match_processing_status': match_processing_status,
            'enhanced_description_length': len(enhanced_description or ''),
            'skills_extracted': len(opportunity_required_skills),
            'kb_results_count': len(company_match_result.get('kb_retrieval_results', [])),
            'citations_count': len(company_match_result.get('citations', []))
        }
        
        error_handler.log_processing_summary(
            opportunity_id, 
            True, 
            company_match_result.get('score'), 
            processing_details
        )
        
        return {
            'message_id': message_id,
            'success': True,
            'opportunity_id': opportunity_id,
            'sqs_key': sqs_key,
            'runs_key': runs_key,
            'category': category,
            'match_score': match_result.get('score', 0.0),
            'match_threshold': config.processing.match_threshold,
            'attachments_processed': len(attachments),
            'processing_status': {
                'llm_processing': llm_processing_status,
                'match_processing': match_processing_status,
                'overall': 'success'
            }
        }
        
    except json.JSONDecodeError as e:
        error_category = error_handler.categorize_error(e)
        error_handler.log_error(opportunity_id or 'unknown', e, {
            'stage': 'message_parsing',
            'message_body_length': len(message_body)
        })
        
        # Create error record if we have opportunity_id
        if opportunity_id:
            error_record = error_handler.create_error_record(opportunity_id, e, 'message_parsing')
            write_error_record_to_s3(error_record, opportunity_id, sqs_bucket, error_handler)
        
        return {
            'message_id': message_id,
            'success': False,
            'error': f'JSON parse error: {str(e)}',
            'error_type': error_category,
            'processing_stage': 'message_parsing'
        }
        
    except Exception as e:
        error_category = error_handler.categorize_error(e)
        error_handler.log_error(opportunity_id or 'unknown', e, {
            'stage': error_handler.current_stage or 'unknown',
            'message_id': message_id
        })
        
        # Log processing summary for failed case
        if opportunity_id:
            error_handler.log_processing_summary(opportunity_id, False)
            
            # Create and write error record
            error_record = error_handler.create_error_record(
                opportunity_id, e, error_handler.current_stage
            )
            write_error_record_to_s3(error_record, opportunity_id, sqs_bucket, error_handler)
        
        return {
            'message_id': message_id,
            'success': False,
            'error': str(e),
            'error_type': error_category,
            'processing_stage': error_handler.current_stage or 'unknown',
            'opportunity_id': opportunity_id
        }


def create_enhanced_match_result(opportunity_data: Dict[str, Any],
                               opportunity_id: str,
                               enhanced_description: str,
                               opportunity_required_skills: List[str],
                               company_match_result: Dict[str, Any],
                               attachment_content: str,
                               source_bucket: str,
                               source_key: str,
                               message_id: str,
                               llm_processing_status: str,
                               match_processing_status: str) -> Dict[str, Any]:
    """
    Create enhanced match result structure with comprehensive requirements compliance.
    """
    current_time = datetime.now()
    
    # Extract SAM.gov metadata fields
    solicitation_number = opportunity_data.get('solicitationNumber', opportunity_id)
    notice_id = opportunity_data.get('noticeId', opportunity_id)
    title = opportunity_data.get('title', 'Unknown Title')
    full_parent_path_name = opportunity_data.get('fullParentPathName', '')
    posted_date = opportunity_data.get('postedDate', '')
    opportunity_type = opportunity_data.get('type', '')
    response_deadline = opportunity_data.get('responseDeadLine', '')
    
    # Extract point of contact information
    point_of_contact = opportunity_data.get('pointOfContact', [])
    if isinstance(point_of_contact, list) and len(point_of_contact) > 0:
        poc_data = point_of_contact[0]
        poc_full_name = poc_data.get('fullName', '')
        poc_email = poc_data.get('email', '')
        poc_phone = poc_data.get('phone', '')
    elif isinstance(point_of_contact, dict):
        poc_full_name = point_of_contact.get('fullName', '')
        poc_email = point_of_contact.get('email', '')
        poc_phone = point_of_contact.get('phone', '')
    else:
        poc_full_name = ''
        poc_email = ''
        poc_phone = ''
    
    # Extract place of performance information with null safety
    place_of_performance = opportunity_data.get('placeOfPerformance')
    if place_of_performance and isinstance(place_of_performance, dict):
        city_name = place_of_performance.get('city', {}).get('name', '') if place_of_performance.get('city') else ''
        state_name = place_of_performance.get('state', {}).get('name', '') if place_of_performance.get('state') else ''
        country_name = place_of_performance.get('country', {}).get('name', '') if place_of_performance.get('country') else ''
    else:
        city_name = ''
        state_name = ''
        country_name = ''
    
    # Generate UI link
    ui_link = f"https://sam.gov/opp/{notice_id}/view" if notice_id else ''
    
    # Ensure enhanced_description has structured format
    if not enhanced_description or "BUSINESS SUMMARY:" not in enhanced_description:
        logger.warning("Enhanced description missing structured format, using fallback")
        enhanced_description = format_structured_description(enhanced_description, opportunity_data)
    
    # Use citations directly from company_match_result (already enhanced by LLM processing)
    citations = company_match_result.get('citations', [])
    
    # Validate and format kb_retrieval_results
    kb_retrieval_results = validate_and_format_kb_results(company_match_result.get('kb_retrieval_results', []))
    
    # Create the comprehensive match result structure
    match_result = {
        # Core SAM.gov metadata fields
        'solicitationNumber': solicitation_number,
        'noticeId': notice_id,
        'title': title,
        'fullParentPathName': full_parent_path_name,
        'postedDate': posted_date,
        'type': opportunity_type,
        'responseDeadLine': response_deadline,
        
        # Point of contact fields
        'pointOfContact.fullName': poc_full_name,
        'pointOfContact.email': poc_email,
        'pointOfContact.phone': poc_phone,
        
        # Place of performance fields
        'placeOfPerformance.city.name': city_name,
        'placeOfPerformance.state.name': state_name,
        'placeOfPerformance.country.name': country_name,
        
        # UI link
        'uiLink': ui_link,
        
        # Enhanced description with structured format
        'enhanced_description': enhanced_description,
        
        # Company matching results
        'score': float(company_match_result.get('score', 0.0)),
        'rationale': company_match_result.get('rationale', 'No rationale provided'),
        'opportunity_required_skills': company_match_result.get('opportunity_required_skills', opportunity_required_skills or []),
        'company_skills': company_match_result.get('company_skills', []),
        'past_performance': company_match_result.get('past_performance', []),
        
        # Citations with proper structure
        'citations': citations,
        
        # Knowledge base retrieval results with comprehensive fields
        'kb_retrieval_results': kb_retrieval_results,
        
        # Processing metadata
        'input_key': source_key,
        'timestamp': current_time.isoformat(),
        
        # Additional processing metadata for monitoring and debugging
        'processing_metadata': {
            'message_id': message_id,
            'source_bucket': source_bucket,
            'processed_timestamp': current_time.isoformat(),
            'enhanced_description_length': len(enhanced_description),
            'attachment_content_length': len(attachment_content),
            'opportunity_required_skills_count': len(opportunity_required_skills or []),
            'llm_processing_status': llm_processing_status,
            'match_processing_status': match_processing_status,
            'kb_retrieval_results_count': len(kb_retrieval_results),
            'citations_count': len(citations),
            'company_skills_count': len(company_match_result.get('company_skills', [])),
            'format_version': '1.0',  # Track format version for backward compatibility
            'requirements_compliance': {
                'sam_metadata_complete': bool(solicitation_number and notice_id and title),
                'structured_description': "BUSINESS SUMMARY:" in enhanced_description,
                'kb_results_formatted': len(kb_retrieval_results) > 0,
                'citations_formatted': len(citations) > 0 or match_processing_status == "failed"
            }
        }
    }
    
    logger.info(f"Created comprehensive match result for {solicitation_number}: "
               f"score={match_result['score']}, "
               f"kb_results={len(kb_retrieval_results)}, "
               f"citations={len(citations)}")
    
    return match_result


def format_structured_description(description: str, opportunity_data: Dict[str, Any]) -> str:
    """
    Format description with structured Business Summary and Non-Technical Summary sections.
    Used as fallback when LLM processing fails to provide structured format.
    """
    title = opportunity_data.get('title', 'Unknown Title')
    original_description = opportunity_data.get('description', 'No description available')
    
    # Truncate if too long
    if len(original_description) > 2000:
        original_description = original_description[:2000] + "... [truncated]"
    
    structured_description = f"""
BUSINESS SUMMARY:
{title}

{original_description}

NON-TECHNICAL SUMMARY:
This opportunity requires analysis of the technical requirements and alignment with company capabilities. Manual review recommended due to processing limitations.

TECHNICAL REQUIREMENTS:
- Requirements extraction failed during processing
- Manual review of opportunity documents recommended
- Contact information available in opportunity metadata

EVALUATION CRITERIA:
- Standard government contracting evaluation criteria apply
- Specific criteria require manual extraction from opportunity documents
"""
    
    return structured_description.strip()


def validate_and_format_citations(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Legacy function - now citations are handled directly by LLM processing.
    Kept for backward compatibility but should not be used.
    """
    # Return citations as-is since they're now properly formatted by LLM processing
    return citations if isinstance(citations, list) else []


def validate_and_format_kb_results(kb_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and format knowledge base retrieval results.
    """
    formatted_results = []
    
    for result in kb_results:
        if isinstance(result, dict):
            formatted_result = {
                'content': result.get('content', ''),
                'score': float(result.get('score', 0.0)),
                'metadata': result.get('metadata', {}),
                'source': result.get('source', 'Knowledge Base')
            }
            formatted_results.append(formatted_result)
    
    return formatted_results


def write_results_to_s3(match_result: Dict[str, Any],
                       opportunity_id: str,
                       sqs_bucket: str,
                       runs_bucket: str,
                       error_handler: ErrorHandler) -> tuple:
    """
    Write match results to S3 buckets based on MATCH_THRESHOLD.
    
    Args:
        match_result: The match result data
        opportunity_id: Unique opportunity identifier
        sqs_bucket: Target bucket for categorized results
        runs_bucket: Target bucket for run logs
        error_handler: Error handling utility
        
    Returns:
        tuple: (sqs_key, runs_key, category)
    """
    current_time = datetime.now()
    
    # Get match threshold from config
    match_threshold = config.processing.match_threshold
    match_score = float(match_result.get('score', 0.0))
    
    # Determine category based on match threshold
    category = "matches" if match_score >= match_threshold else "no_matches"
    
    # Create S3 keys with category-based folder structure
    sqs_key = f"{current_time.strftime('%Y-%m-%d')}/{category}/{opportunity_id}.json"
    runs_key = f"runs/raw/{current_time.strftime('%Y%m%dt%H%MZ')}_{opportunity_id}.json"
    
    logger.info(f"Writing results: score={match_score:.3f}, threshold={match_threshold:.3f}, category={category}")
    
    try:
        # Write to SQS bucket
        error_handler.log_s3_operation("write", sqs_bucket, sqs_key)
        aws_clients.s3.put_object(
            Bucket=sqs_bucket,
            Key=sqs_key,
            Body=json.dumps(match_result, indent=2),
            ContentType='application/json'
        )
        error_handler.log_s3_operation("write", sqs_bucket, sqs_key, success=True)
        
        # Create enhanced run result with full match data (similar to provided schema)
        run_result = create_enhanced_run_result(match_result, current_time)
        
        # Write to runs bucket in raw folder
        error_handler.log_s3_operation("write", runs_bucket, runs_key)
        aws_clients.s3.put_object(
            Bucket=runs_bucket,
            Key=runs_key,
            Body=json.dumps(run_result, indent=2),
            ContentType='application/json'
        )
        error_handler.log_s3_operation("write", runs_bucket, runs_key, success=True)
        
        return sqs_key, runs_key, category
        
    except Exception as e:
        error_handler.log_s3_operation("write", sqs_bucket, sqs_key, success=False, error=e)
        error_handler.log_s3_operation("write", runs_bucket, runs_key, success=False, error=e)
        raise


def create_enhanced_run_result(match_result: Dict[str, Any], current_time: datetime) -> Dict[str, Any]:
    """
    Create enhanced run result with schema similar to the provided example.
    
    Args:
        match_result: The complete match result
        current_time: Current timestamp
        
    Returns:
        Enhanced run result dictionary
    """
    # Extract core fields from match_result
    run_result = {
        'solicitationNumber': match_result.get('solicitationNumber', ''),
        'noticeId': match_result.get('noticeId', ''),
        'title': match_result.get('title', ''),
        'fullParentPathName': match_result.get('fullParentPathName', ''),
        'enhanced_description': match_result.get('enhanced_description', ''),
        'score': match_result.get('score', 0.0),
        'rationale': match_result.get('rationale', ''),
        'opportunity_required_skills': match_result.get('opportunity_required_skills', []),
        'company_skills': match_result.get('company_skills', []),
        'past_performance': match_result.get('past_performance', []),
        'citations': match_result.get('citations', []),
        'kb_retrieval_results': match_result.get('kb_retrieval_results', []),
        'input_key': match_result.get('input_key', ''),
        'timestamp': match_result.get('timestamp', current_time.isoformat()),
        'postedDate': match_result.get('postedDate', ''),
        'type': match_result.get('type', ''),
        'responseDeadLine': match_result.get('responseDeadLine', ''),
        'pointOfContact.fullName': match_result.get('pointOfContact.fullName', ''),
        'pointOfContact.email': match_result.get('pointOfContact.email', ''),
        'pointOfContact.phone': match_result.get('pointOfContact.phone', ''),
        'placeOfPerformance.city.name': match_result.get('placeOfPerformance.city.name', ''),
        'placeOfPerformance.state.name': match_result.get('placeOfPerformance.state.name', ''),
        'placeOfPerformance.country.name': match_result.get('placeOfPerformance.country.name', ''),
        'uiLink': match_result.get('uiLink', '')
    }
    
    return run_result


def write_error_record_to_s3(error_record: Dict[str, Any],
                           opportunity_id: str,
                           sqs_bucket: str,
                           error_handler: ErrorHandler):
    """
    Write error record to S3 bucket.
    """
    current_time = datetime.now()
    error_key = f"{current_time.strftime('%Y-%m-%d')}/errors/{opportunity_id}.json"
    
    try:
        error_handler.log_s3_operation("write", sqs_bucket, error_key)
        aws_clients.s3.put_object(
            Bucket=sqs_bucket,
            Key=error_key,
            Body=json.dumps(error_record, indent=2),
            ContentType='application/json'
        )
        error_handler.log_s3_operation("write", sqs_bucket, error_key, success=True)
        
    except Exception as e:
        error_handler.log_s3_operation("write", sqs_bucket, error_key, success=False, error=e)
        logger.error(f"Failed to write error record to S3: {e}")