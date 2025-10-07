"""
Data aggregation utilities for web dashboard generation.
Handles parsing and aggregating run result files for daily statistics.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from shared import get_logger, get_s3_client, config

logger = get_logger(__name__)

@dataclass
class DailyStats:
    """Daily aggregated statistics."""
    date: str
    total_opportunities: int = 0
    matches_found: int = 0
    no_matches: int = 0
    errors: int = 0
    total_processing_time: int = 0
    run_count: int = 0
    top_matches: List[Dict[str, Any]] = field(default_factory=list)
    match_score_distribution: Dict[str, int] = field(default_factory=dict)
    hourly_distribution: Dict[str, int] = field(default_factory=dict)
    average_match_score: float = 0.0
    success_rate: float = 0.0

@dataclass
class OpportunityMatch:
    """Individual opportunity match data."""
    solicitation_id: str
    match_score: float
    title: str
    timestamp: str
    value: Optional[str] = None
    deadline: Optional[str] = None

class DataAggregator:
    """Aggregates run result data for dashboard generation."""
    
    def __init__(self):
        self.s3_client = get_s3_client()
        self.runs_bucket = config.s3.sam_matching_out_runs
    
    def aggregate_daily_data(self, date_prefix: str) -> Optional[DailyStats]:
        """
        Aggregate all run results for a specific date.
        
        Args:
            date_prefix: Date prefix (YYYYMMDD) to aggregate data for
            
        Returns:
            DailyStats object with aggregated data or None if no data found
        """
        logger.info(f"Starting data aggregation", date=date_prefix)
        
        try:
            # Find all run files for the date
            run_files = self._find_run_files(date_prefix)
            if not run_files:
                logger.warning(f"No run files found for date", date=date_prefix)
                return None
            
            logger.info(f"Found {len(run_files)} run files", date=date_prefix)
            
            # Initialize daily stats
            daily_stats = DailyStats(date=date_prefix)
            all_matches = []
            match_scores = []
            
            # Process each run file
            for run_file in run_files:
                run_data = self._load_run_file(run_file)
                if run_data:
                    self._aggregate_run_data(daily_stats, run_data, all_matches, match_scores)
            
            # Calculate derived statistics
            self._calculate_derived_stats(daily_stats, all_matches, match_scores)
            
            logger.info(f"Data aggregation completed", 
                       date=date_prefix,
                       total_opportunities=daily_stats.total_opportunities,
                       matches=daily_stats.matches_found)
            
            return daily_stats
            
        except Exception as e:
            logger.error(f"Error aggregating daily data: {str(e)}", date=date_prefix)
            return None
    
    def _find_run_files(self, date_prefix: str) -> List[str]:
        """
        Find all run files matching the date prefix.
        
        Args:
            date_prefix: Date prefix (YYYYMMDD) to search for
            
        Returns:
            List of S3 object keys for matching run files
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.runs_bucket,
                Prefix=f"runs/{date_prefix}"
            )
            
            run_files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Only include .json files that start with the date prefix
                    if key.endswith('.json') and f"runs/{date_prefix}" in key:
                        run_files.append(key)
            
            return sorted(run_files)
            
        except Exception as e:
            logger.error(f"Error finding run files: {str(e)}", date=date_prefix)
            return []
    
    def _load_run_file(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Load and parse a run result file from S3.
        
        Args:
            object_key: S3 object key for the run file
            
        Returns:
            Parsed run data dictionary or None if failed
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.runs_bucket,
                Key=object_key
            )
            
            content = response['Body'].read().decode('utf-8')
            run_data = json.loads(content)
            
            logger.debug(f"Loaded run file", key=object_key, 
                        opportunities=run_data.get('total_opportunities', 0))
            
            return run_data
            
        except Exception as e:
            logger.error(f"Error loading run file: {str(e)}", key=object_key)
            return None
    
    def _aggregate_run_data(self, daily_stats: DailyStats, run_data: Dict[str, Any], 
                           all_matches: List[OpportunityMatch], match_scores: List[float]):
        """
        Aggregate data from a single run into daily statistics.
        
        Args:
            daily_stats: DailyStats object to update
            run_data: Individual run data
            all_matches: List to collect all matches
            match_scores: List to collect all match scores
        """
        try:
            # Aggregate basic counts
            daily_stats.total_opportunities += run_data.get('total_opportunities', 0)
            daily_stats.matches_found += run_data.get('matches_found', 0)
            daily_stats.no_matches += run_data.get('no_matches', 0)
            daily_stats.errors += run_data.get('errors', 0)
            daily_stats.total_processing_time += run_data.get('processing_time_seconds', 0)
            daily_stats.run_count += 1
            
            # Extract timestamp for hourly distribution
            timestamp = run_data.get('timestamp', '')
            if timestamp:
                hour = self._extract_hour_from_timestamp(timestamp)
                if hour is not None:
                    daily_stats.hourly_distribution[hour] = daily_stats.hourly_distribution.get(hour, 0) + 1
            
            # Collect top matches
            top_matches = run_data.get('top_matches', [])
            for match in top_matches:
                if isinstance(match, dict):
                    opportunity_match = OpportunityMatch(
                        solicitation_id=match.get('solicitation_id', ''),
                        match_score=float(match.get('match_score', 0.0)),
                        title=match.get('title', ''),
                        timestamp=timestamp,
                        value=match.get('value'),
                        deadline=match.get('deadline')
                    )
                    all_matches.append(opportunity_match)
                    match_scores.append(opportunity_match.match_score)
            
        except Exception as e:
            logger.error(f"Error aggregating run data: {str(e)}", run_data=run_data)
    
    def _calculate_derived_stats(self, daily_stats: DailyStats, 
                                all_matches: List[OpportunityMatch], 
                                match_scores: List[float]):
        """
        Calculate derived statistics from aggregated data.
        
        Args:
            daily_stats: DailyStats object to update
            all_matches: All collected matches
            match_scores: All collected match scores
        """
        try:
            # Calculate success rate
            total_processed = daily_stats.total_opportunities
            if total_processed > 0:
                successful = total_processed - daily_stats.errors
                daily_stats.success_rate = (successful / total_processed) * 100
            
            # Calculate average match score
            if match_scores:
                daily_stats.average_match_score = sum(match_scores) / len(match_scores)
            
            # Get top matches (sorted by score, limit to top 10)
            sorted_matches = sorted(all_matches, key=lambda x: x.match_score, reverse=True)
            daily_stats.top_matches = [
                {
                    'solicitation_id': match.solicitation_id,
                    'match_score': match.match_score,
                    'title': match.title,
                    'timestamp': match.timestamp,
                    'value': match.value,
                    'deadline': match.deadline
                }
                for match in sorted_matches[:10]
            ]
            
            # Calculate match score distribution
            daily_stats.match_score_distribution = self._calculate_score_distribution(match_scores)
            
        except Exception as e:
            logger.error(f"Error calculating derived stats: {str(e)}")
    
    def _calculate_score_distribution(self, match_scores: List[float]) -> Dict[str, int]:
        """
        Calculate match score distribution in ranges.
        
        Args:
            match_scores: List of match scores
            
        Returns:
            Dictionary with score ranges and counts
        """
        distribution = {
            '0.0-0.2': 0,
            '0.2-0.4': 0,
            '0.4-0.6': 0,
            '0.6-0.8': 0,
            '0.8-1.0': 0
        }
        
        for score in match_scores:
            if score < 0.2:
                distribution['0.0-0.2'] += 1
            elif score < 0.4:
                distribution['0.2-0.4'] += 1
            elif score < 0.6:
                distribution['0.4-0.6'] += 1
            elif score < 0.8:
                distribution['0.6-0.8'] += 1
            else:
                distribution['0.8-1.0'] += 1
        
        return distribution
    
    def _extract_hour_from_timestamp(self, timestamp: str) -> Optional[str]:
        """
        Extract hour from timestamp for hourly distribution.
        
        Args:
            timestamp: ISO timestamp string
            
        Returns:
            Hour string (HH:00) or None if parsing fails
        """
        try:
            # Try parsing ISO format first
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Try parsing YYYYMMDDtHHMMZ format
                dt = datetime.strptime(timestamp, '%Y%m%dt%H%MZ')
            
            return f"{dt.hour:02d}:00"
            
        except Exception as e:
            logger.debug(f"Could not parse timestamp: {str(e)}", timestamp=timestamp)
            return None