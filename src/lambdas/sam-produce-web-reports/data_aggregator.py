"""
Data aggregation utilities for web dashboard generation.
Handles parsing and aggregating run result files for daily statistics.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from shared import get_logger, aws_clients, config

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
    agencies: int = 0
    all_records: List[Dict[str, Any]] = field(default_factory=list)

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
        self.s3_client = aws_clients.s3
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
            all_records = []
            
            # Process each run file
            for run_file in run_files:
                records = self._load_run_file(run_file)
                if records:
                    all_records.extend(records)
            
            if not all_records:
                logger.warning(f"No records found in run files", date=date_prefix)
                return None
            
            # Aggregate the flattened records
            self._aggregate_records(daily_stats, all_records)
            
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
    
    def _load_run_file(self, object_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load and parse a run result file from S3.
        Flattens JSON list-of-lists into list of dicts for opportunity records.
        
        Args:
            object_key: S3 object key for the run file
            
        Returns:
            List of flattened opportunity records or None if failed
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.runs_bucket,
                Key=object_key
            )
            
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)
            
            # Flatten list-of-lists into list of dicts
            flat_records = []
            for entry in data:
                if isinstance(entry, list):
                    flat_records.extend(entry)
                elif isinstance(entry, dict):
                    flat_records.append(entry)
            
            logger.debug(f"Loaded run file", key=object_key, 
                        opportunities=len(flat_records))
            
            return flat_records
            
        except Exception as e:
            logger.error(f"Error loading run file: {str(e)}", key=object_key)
            return None
    
    def _aggregate_records(self, daily_stats: DailyStats, records: List[Dict[str, Any]]):
        """
        Aggregate flattened opportunity records into daily statistics.
        Store complete records for rich dashboard display.
        
        Args:
            daily_stats: DailyStats object to update
            records: List of flattened opportunity records
        """
        try:
            all_matches = []
            match_scores = []
            agencies = set()
            
            # Process each record
            for record in records:
                if not isinstance(record, dict):
                    continue
                
                # Count opportunities
                daily_stats.total_opportunities += 1
                
                # Check if matched
                matched = record.get('matched', False)
                if matched:
                    daily_stats.matches_found += 1
                else:
                    daily_stats.no_matches += 1
                
                # Track agencies
                agency = record.get('fullParentPathName')
                if agency:
                    agencies.add(agency)
                
                # Get match score
                score = record.get('score', 0.0)
                if isinstance(score, (int, float)):
                    match_scores.append(float(score))
                
                # Store complete record data for rich display
                opportunity_match = {
                    'solicitation_id': record.get('solicitationNumber', ''),
                    'match_score': float(score) if isinstance(score, (int, float)) else 0.0,
                    'title': record.get('title', ''),
                    'timestamp': record.get('postedDate', ''),
                    'value': record.get('awardAmount', ''),
                    'deadline': record.get('responseDeadLine', ''),
                    'matched': matched,
                    'agency': record.get('fullParentPathName', ''),
                    'rationale': record.get('rationale', ''),
                    'enhanced_description': record.get('enhanced_description', ''),
                    'opportunity_required_skills': record.get('opportunity_required_skills', []),
                    'company_skills': record.get('company_skills', []),
                    'past_performance': record.get('past_performance', []),
                    'citations': record.get('citations', []),
                    'type': record.get('type', ''),
                    'pointOfContact': record.get('pointOfContact', {}),
                    'uiLink': record.get('uiLink', ''),
                    'kb_retrieval_results': record.get('kb_retrieval_results', [])
                }
                all_matches.append(opportunity_match)
            
            # Store complete records and calculate stats
            daily_stats.all_records = all_matches
            daily_stats.agencies = len(agencies)
            
            # Calculate derived statistics
            self._calculate_derived_stats(daily_stats, all_matches, match_scores)
            
        except Exception as e:
            logger.error(f"Error aggregating records: {str(e)}")
    
    def _aggregate_run_data(self, daily_stats: DailyStats, run_data: Dict[str, Any], 
                           all_matches: List[OpportunityMatch], match_scores: List[float]):
        """
        Legacy method - kept for compatibility but not used with new flattened structure.
        """
        pass
    
    def group_by_confidence(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group opportunities by confidence score ranges.
        
        Args:
            records: List of opportunity records
            
        Returns:
            Dictionary with confidence ranges as keys and opportunity lists as values
        """
        groups = {
            "1.0 (Perfect match)": [],
            "0.9 (Outstanding match)": [],
            "0.8 (Strong match)": [],
            "0.7 (Good subject matter match)": [],
            "0.6 (Decent subject matter match)": [],
            "0.5 (Partial technical or conceptual match)": [],
            "0.3 (Weak or minimal match)": [],
            "0.0 (No demonstrated capability)": []
        }
        
        for r in records:
            s = r.get("match_score", 0.0)
            if s >= 0.95: 
                groups["1.0 (Perfect match)"].append(r)
            elif s >= 0.85: 
                groups["0.9 (Outstanding match)"].append(r)
            elif s >= 0.75: 
                groups["0.8 (Strong match)"].append(r)
            elif s >= 0.65: 
                groups["0.7 (Good subject matter match)"].append(r)
            elif s >= 0.55: 
                groups["0.6 (Decent subject matter match)"].append(r)
            elif s >= 0.4: 
                groups["0.5 (Partial technical or conceptual match)"].append(r)
            elif s >= 0.15: 
                groups["0.3 (Weak or minimal match)"].append(r)
            else: 
                groups["0.0 (No demonstrated capability)"].append(r)
        
        return groups

    def _calculate_derived_stats(self, daily_stats: DailyStats, 
                                all_matches: List[Dict[str, Any]], 
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
            
            # Store all matches for rich display (sorted by score)
            daily_stats.top_matches = sorted(all_matches, key=lambda x: x.get('match_score', 0), reverse=True)
            
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