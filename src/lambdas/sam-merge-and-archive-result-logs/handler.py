"""
SAM merge and archive result logs Lambda function handler.
Aggregates run results and archives individual files.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from shared import (
    get_logger, 
    handle_lambda_error, 
    config, 
    aws_clients,
    handle_aws_error,
    RetryableError,
    NonRetryableError,
    Constants
)

logger = get_logger(__name__)

@dataclass
class RunFile:
    """Represents a run result file."""
    key: str
    timestamp: datetime
    size: int
    last_modified: datetime

@dataclass
class AggregationResult:
    """Results of the aggregation process."""
    processed_files: int
    archived_files: int
    aggregate_file_key: str
    total_opportunities: int
    total_matches: int
    total_no_matches: int
    total_errors: int
    processing_time_seconds: float

class ResultAggregator:
    """Handles result aggregation and archiving operations."""
    
    def __init__(self):
        self.s3_client = aws_clients.s3
        self.runs_bucket = config.s3.sam_matching_out_runs
        self.runs_folder = "runs/"
        self.archive_folder = "archive/"
        self.aggregation_window_minutes = 5
    
    @handle_aws_error
    def process_scheduled_event(self, event: Dict[str, Any]) -> AggregationResult:
        """
        Process EventBridge scheduled event for result aggregation.
        
        Args:
            event: EventBridge scheduled event
            
        Returns:
            AggregationResult: Results of the aggregation process
        """
        start_time = datetime.utcnow()
        
        # Calculate time window for processing (last 5 minutes)
        end_time = start_time
        start_window = end_time - timedelta(minutes=self.aggregation_window_minutes)
        
        logger.info("Processing aggregation window", 
                   start_window=start_window.isoformat(),
                   end_window=end_time.isoformat())
        
        # Find run files in the time window
        run_files = self._find_run_files_in_window(start_window, end_time)
        
        if not run_files:
            logger.info("No run files found in aggregation window")
            return AggregationResult(
                processed_files=0,
                archived_files=0,
                aggregate_file_key="",
                total_opportunities=0,
                total_matches=0,
                total_no_matches=0,
                total_errors=0,
                processing_time_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
        
        logger.info("Found run files for aggregation", count=len(run_files))
        
        # Aggregate the run results
        aggregated_data = self._aggregate_run_results(run_files)
        
        # Create timestamped aggregate file
        aggregate_key = self._create_aggregate_file(aggregated_data, end_time)
        
        # Archive processed files
        archived_count = self._archive_run_files(run_files)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return AggregationResult(
            processed_files=len(run_files),
            archived_files=archived_count,
            aggregate_file_key=aggregate_key,
            total_opportunities=aggregated_data.get('total_opportunities', 0),
            total_matches=aggregated_data.get('total_matches', 0),
            total_no_matches=aggregated_data.get('total_no_matches', 0),
            total_errors=aggregated_data.get('total_errors', 0),
            processing_time_seconds=processing_time
        )
    
    @handle_aws_error
    def _find_run_files_in_window(self, start_time: datetime, end_time: datetime) -> List[RunFile]:
        """
        Find run files within the specified time window.
        
        Args:
            start_time: Start of the time window
            end_time: End of the time window
            
        Returns:
            List[RunFile]: List of run files in the time window
        """
        run_files = []
        
        try:
            # List objects in the runs folder
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.runs_bucket,
                Prefix=self.runs_folder
            )
            
            for page in page_iterator:
                contents = page.get('Contents', [])
                
                for obj in contents:
                    key = obj['Key']
                    last_modified = obj['LastModified'].replace(tzinfo=None)
                    size = obj['Size']
                    
                    # Skip the runs folder itself
                    if key == self.runs_folder:
                        continue
                    
                    # Skip already aggregated files (they have timestamp format)
                    filename = key.replace(self.runs_folder, '')
                    if self._is_aggregate_file(filename):
                        continue
                    
                    # Check if file was modified within our time window
                    if start_time <= last_modified <= end_time:
                        # Try to parse timestamp from filename if possible
                        file_timestamp = self._extract_timestamp_from_filename(filename)
                        if file_timestamp is None:
                            file_timestamp = last_modified
                        
                        run_files.append(RunFile(
                            key=key,
                            timestamp=file_timestamp,
                            size=size,
                            last_modified=last_modified
                        ))
            
        except Exception as e:
            raise RetryableError(f"Failed to list run files: {str(e)}")
        
        # Sort by timestamp
        run_files.sort(key=lambda x: x.timestamp)
        
        return run_files
    
    def _is_aggregate_file(self, filename: str) -> bool:
        """
        Check if a filename represents an aggregate file.
        
        Args:
            filename: The filename to check
            
        Returns:
            bool: True if it's an aggregate file
        """
        # Aggregate files follow YYYYMMDDtHHMMZ.json format
        if not filename.endswith('.json'):
            return False
        
        base_name = filename[:-5]  # Remove .json
        
        # Check if it matches the timestamp format
        try:
            datetime.strptime(base_name, '%Y%m%dt%H%MZ')
            return True
        except ValueError:
            return False
    
    def _extract_timestamp_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract timestamp from filename if possible.
        
        Args:
            filename: The filename to parse
            
        Returns:
            Optional[datetime]: Extracted timestamp or None
        """
        # Try to extract timestamp from various filename patterns
        if filename.endswith('.json'):
            base_name = filename[:-5]
            
            # Try YYYYMMDDtHHMMZ format
            try:
                return datetime.strptime(base_name, '%Y%m%dt%H%MZ')
            except ValueError:
                pass
            
            # Try other common timestamp formats in the filename
            # This can be extended based on actual filename patterns
        
        return None
    
    @handle_aws_error
    def _aggregate_run_results(self, run_files: List[RunFile]) -> Dict[str, Any]:
        """
        Aggregate results from multiple run files.
        
        Args:
            run_files: List of run files to aggregate
            
        Returns:
            Dict[str, Any]: Aggregated results
        """
        aggregated_data = {
            'aggregation_timestamp': datetime.utcnow().isoformat(),
            'aggregation_window_minutes': self.aggregation_window_minutes,
            'source_files': [],
            'total_opportunities': 0,
            'total_matches': 0,
            'total_no_matches': 0,
            'total_errors': 0,
            'processing_time_seconds': 0.0,
            'top_matches': [],
            'run_summaries': []
        }
        
        all_matches = []
        
        for run_file in run_files:
            try:
                # Download and parse the run file
                response = self.s3_client.get_object(
                    Bucket=self.runs_bucket,
                    Key=run_file.key
                )
                run_data = json.loads(response['Body'].read().decode('utf-8'))
                
                # Add to source files list
                aggregated_data['source_files'].append({
                    'key': run_file.key,
                    'timestamp': run_file.timestamp.isoformat(),
                    'size': run_file.size
                })
                
                # Aggregate statistics
                aggregated_data['total_opportunities'] += run_data.get('total_opportunities', 0)
                aggregated_data['total_matches'] += run_data.get('matches_found', 0)
                aggregated_data['total_no_matches'] += run_data.get('no_matches', 0)
                aggregated_data['total_errors'] += run_data.get('errors', 0)
                aggregated_data['processing_time_seconds'] += run_data.get('processing_time_seconds', 0.0)
                
                # Collect top matches
                top_matches = run_data.get('top_matches', [])
                all_matches.extend(top_matches)
                
                # Add run summary
                aggregated_data['run_summaries'].append({
                    'run_id': run_data.get('run_id', run_file.key),
                    'timestamp': run_data.get('timestamp', run_file.timestamp.isoformat()),
                    'opportunities': run_data.get('total_opportunities', 0),
                    'matches': run_data.get('matches_found', 0),
                    'processing_time': run_data.get('processing_time_seconds', 0.0)
                })
                
            except Exception as e:
                logger.error("Failed to process run file", 
                           key=run_file.key, 
                           error=str(e))
                # Continue processing other files
                continue
        
        # Sort and limit top matches
        if all_matches:
            # Sort by match score (descending)
            all_matches.sort(key=lambda x: x.get('match_score', 0), reverse=True)
            # Keep top 10 matches
            aggregated_data['top_matches'] = all_matches[:10]
        
        return aggregated_data
    
    @handle_aws_error
    def _create_aggregate_file(self, aggregated_data: Dict[str, Any], timestamp: datetime) -> str:
        """
        Create timestamped aggregate file.
        
        Args:
            aggregated_data: Aggregated results data
            timestamp: Timestamp for the aggregate file
            
        Returns:
            str: S3 key of the created aggregate file
        """
        # Create filename with YYYYMMDDtHHMMZ format
        timestamp_str = timestamp.strftime('%Y%m%dt%H%MZ')
        aggregate_key = f"{self.runs_folder}{timestamp_str}.json"
        
        try:
            # Store the aggregate file
            self.s3_client.put_object(
                Bucket=self.runs_bucket,
                Key=aggregate_key,
                Body=json.dumps(aggregated_data, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info("Created aggregate file", key=aggregate_key)
            return aggregate_key
            
        except Exception as e:
            raise RetryableError(f"Failed to create aggregate file: {str(e)}")
    
    @handle_aws_error
    def _archive_run_files(self, run_files: List[RunFile]) -> int:
        """
        Archive processed run files to archive folder.
        
        Args:
            run_files: List of run files to archive
            
        Returns:
            int: Number of successfully archived files
        """
        archived_count = 0
        failed_operations = []
        
        for run_file in run_files:
            try:
                # Create archive key
                filename = run_file.key.replace(self.runs_folder, '')
                archive_key = f"{self.archive_folder}{filename}"
                
                # Copy file to archive location
                copy_source = {
                    'Bucket': self.runs_bucket,
                    'Key': run_file.key
                }
                
                self.s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=self.runs_bucket,
                    Key=archive_key
                )
                
                # Delete original file
                self.s3_client.delete_object(
                    Bucket=self.runs_bucket,
                    Key=run_file.key
                )
                
                archived_count += 1
                logger.debug("Archived run file", 
                           original_key=run_file.key,
                           archive_key=archive_key)
                
            except Exception as e:
                error_msg = f"Failed to archive {run_file.key}: {str(e)}"
                logger.error(error_msg)
                failed_operations.append({
                    'key': run_file.key,
                    'error': str(e)
                })
        
        if failed_operations:
            logger.warning("Some archive operations failed", 
                         failed_count=len(failed_operations),
                         failures=failed_operations)
        
        return archived_count

# Global aggregator instance
aggregator = ResultAggregator()

@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for result aggregation and archiving.
    
    Args:
        event: EventBridge scheduled event
        context: Lambda context object
        
    Returns:
        dict: Response with status and message
    """
    logger.info("Starting result aggregation and archiving", event=event)
    
    try:
        # Process the scheduled event
        result = aggregator.process_scheduled_event(event)
        
        logger.info("Result aggregation and archiving completed", 
                   processed_files=result.processed_files,
                   archived_files=result.archived_files,
                   aggregate_file=result.aggregate_file_key,
                   processing_time=result.processing_time_seconds)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Result aggregation and archiving completed successfully',
                'results': {
                    'processed_files': result.processed_files,
                    'archived_files': result.archived_files,
                    'aggregate_file_key': result.aggregate_file_key,
                    'total_opportunities': result.total_opportunities,
                    'total_matches': result.total_matches,
                    'total_no_matches': result.total_no_matches,
                    'total_errors': result.total_errors,
                    'processing_time_seconds': result.processing_time_seconds
                },
                'correlation_id': logger.correlation_id
            })
        }
        
    except Exception as e:
        logger.error("Result aggregation and archiving failed", error=str(e))
        raise