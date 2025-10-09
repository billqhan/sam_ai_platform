
import json
import boto3
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Simple Lambda handler that writes to S3 buckets"""
    
    logger.info("🚀 SIMPLE S3 OUTPUT LAMBDA STARTED")
    logger.info(f"📋 Event: {json.dumps(event, default=str)}")
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name='us-east-1')
    
    # Target buckets
    sqs_bucket = 'ktest-sam-matching-out-sqs-dev'
    runs_bucket = 'ktest-sam-matching-out-runs-dev'
    
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
                # Extract message info
                message_id = record.get('messageId', f'unknown_{i}')
                message_body = record.get('body', '{}')
                
                logger.info(f"📄 Message ID: {message_id}")
                logger.info(f"📄 Message body preview: {message_body[:200]}...")
                
                # Parse the message body to get S3 info
                try:
                    body_data = json.loads(message_body)
                    
                    # Look for S3 event in the message
                    s3_records = body_data.get('Records', [])
                    
                    if s3_records and len(s3_records) > 0:
                        s3_record = s3_records[0]
                        
                        if 's3' in s3_record:
                            s3_info = s3_record['s3']
                            source_bucket = s3_info.get('bucket', {}).get('name', 'unknown')
                            source_key = s3_info.get('object', {}).get('key', 'unknown')
                            
                            logger.info(f"📋 S3 Event Details:")
                            logger.info(f"  Source bucket: {source_bucket}")
                            logger.info(f"  Source key: {source_key}")
                            
                            # Extract opportunity ID from key
                            opportunity_id = 'unknown'
                            if '/' in source_key:
                                opportunity_id = source_key.split('/')[0]
                            
                            logger.info(f"📊 Opportunity ID: {opportunity_id}")
                            
                            # Create test match result
                            match_result = {
                                'solicitation_id': opportunity_id,
                                'match_score': 0.85,
                                'is_match': True,
                                'rationale': 'Test match result from simple S3 output Lambda',
                                'citations': [],
                                'opportunity_required_skills': ['AI', 'Cloud Computing'],
                                'company_skills': ['AWS', 'Python', 'Machine Learning'],
                                'past_performance': [],
                                'opportunity_summary': {
                                    'title': f'Opportunity {opportunity_id}',
                                    'value': 'Test Value',
                                    'deadline': 'Test Deadline',
                                    'naics_codes': []
                                },
                                'processed_timestamp': datetime.now().isoformat(),
                                'match_threshold': 0.7,
                                'source_bucket': source_bucket,
                                'source_key': source_key,
                                'message_id': message_id
                            }
                            
                            logger.info("🎯 S3 OUTPUT: Writing match result to SQS bucket")
                            
                            # Write to SQS bucket
                            current_date = datetime.now().strftime('%Y-%m-%d')
                            category = 'matches' if match_result['is_match'] else 'no_matches'
                            
                            sqs_key = f"{current_date}/{category}/{opportunity_id}.json"
                            
                            logger.info(f"📍 SQS bucket write:")
                            logger.info(f"  Bucket: {sqs_bucket}")
                            logger.info(f"  Key: {sqs_key}")
                            
                            try:
                                s3_client.put_object(
                                    Bucket=sqs_bucket,
                                    Key=sqs_key,
                                    Body=json.dumps(match_result, indent=2, default=str),
                                    ContentType='application/json'
                                )
                                
                                logger.info("✅ S3 OUTPUT: Successfully wrote to SQS bucket!")
                                
                            except Exception as sqs_error:
                                logger.error(f"❌ S3 OUTPUT: Failed to write to SQS bucket: {sqs_error}")
                                raise
                            
                            # Write to Runs bucket
                            run_summary = {
                                'run_id': f"{datetime.now().strftime('%Y%m%dt%H%M%S')}_{opportunity_id}",
                                'timestamp': datetime.now().isoformat(),
                                'date_prefix': datetime.now().strftime('%Y%m%d'),
                                'solicitation_id': opportunity_id,
                                'category': category,
                                'match_score': match_result['match_score'],
                                'is_match': match_result['is_match'],
                                'opportunity_title': match_result['opportunity_summary']['title'],
                                'processing_status': 'success',
                                'message_id': message_id,
                                'source_bucket': source_bucket,
                                'source_key': source_key
                            }
                            
                            timestamp = datetime.now().strftime('%Y%m%dt%H%MZ')
                            runs_key = f"runs/{timestamp}_{opportunity_id}.json"
                            
                            logger.info(f"🎯 S3 OUTPUT: Writing run summary to Runs bucket")
                            logger.info(f"📍 Runs bucket write:")
                            logger.info(f"  Bucket: {runs_bucket}")
                            logger.info(f"  Key: {runs_key}")
                            
                            try:
                                s3_client.put_object(
                                    Bucket=runs_bucket,
                                    Key=runs_key,
                                    Body=json.dumps(run_summary, indent=2, default=str),
                                    ContentType='application/json'
                                )
                                
                                logger.info("✅ S3 OUTPUT: Successfully wrote to Runs bucket!")
                                
                            except Exception as runs_error:
                                logger.error(f"❌ S3 OUTPUT: Failed to write to Runs bucket: {runs_error}")
                                raise
                            
                            results.append({
                                'message_id': message_id,
                                'success': True,
                                'opportunity_id': opportunity_id,
                                'sqs_key': sqs_key,
                                'runs_key': runs_key
                            })
                            
                        else:
                            logger.warning(f"⚠️ No S3 info found in record")
                            results.append({
                                'message_id': message_id,
                                'success': False,
                                'error': 'No S3 info in record'
                            })
                    else:
                        logger.warning(f"⚠️ No S3 records found in message body")
                        results.append({
                            'message_id': message_id,
                            'success': False,
                            'error': 'No S3 records in message'
                        })
                        
                except json.JSONDecodeError as parse_error:
                    logger.error(f"❌ Failed to parse message body: {parse_error}")
                    results.append({
                        'message_id': message_id,
                        'success': False,
                        'error': f'JSON parse error: {parse_error}'
                    })
                    
            except Exception as record_error:
                logger.error(f"❌ Failed to process record {i+1}: {record_error}")
                results.append({
                    'message_id': record.get('messageId', f'unknown_{i}'),
                    'success': False,
                    'error': str(record_error)
                })
        
        # Summary
        successful = len([r for r in results if r['success']])
        failed = len([r for r in results if not r['success']])
        
        logger.info(f"📊 PROCESSING SUMMARY:")
        logger.info(f"  Total messages: {len(results)}")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Failed: {failed}")
        
        if successful > 0:
            logger.info("🎉 S3 OUTPUT SUCCESS: Files written to both buckets!")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'S3 output processing completed',
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
