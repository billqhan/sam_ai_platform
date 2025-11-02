"""
Configuration management for environment variables and constants.
"""
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class Environment(Enum):
    """Environment types."""
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"

@dataclass
class S3Config:
    """S3 bucket configuration."""
    sam_data_in: str
    sam_extracted_json_resources: str
    sam_matching_out_sqs: str
    sam_matching_out_runs: str
    sam_opportunity_responses: str
    sam_website: str
    sam_company_info: str
    sam_download_files_logs: str

@dataclass
class SQSConfig:
    """SQS configuration."""
    sam_json_messages_queue: str
    dead_letter_queue: str

@dataclass
class BedrockConfig:
    """Bedrock AI configuration."""
    region: str
    knowledge_base_id: str
    model_id_desc: str
    model_id_match: str
    max_tokens: int
    temperature: float

@dataclass
class ProcessingConfig:
    """Processing limits and thresholds."""
    match_threshold: float
    max_attachment_files: int
    max_description_chars: int
    max_attachment_chars: int
    max_concurrent_downloads: int
    process_delay_seconds: int
    api_limit: int

@dataclass
class SAMAPIConfig:
    """SAM.gov API configuration."""
    base_url: str
    api_key: str
    timeout: int
    max_retries: int

class ConfigManager:
    """Centralized configuration management."""
    
    def __init__(self):
        self.environment = Environment(os.environ.get('ENVIRONMENT', 'dev'))
        self._s3_config = None
        self._sqs_config = None
        self._bedrock_config = None
        self._processing_config = None
        self._sam_api_config = None
    
    @property
    def s3(self) -> S3Config:
        """Get S3 configuration."""
        if self._s3_config is None:
            self._s3_config = S3Config(
                sam_data_in=self._get_required_env('SAM_DATA_IN_BUCKET', 'sam-data-in'),
                sam_extracted_json_resources=self._get_required_env('SAM_EXTRACTED_JSON_RESOURCES_BUCKET', 'sam-extracted-json-resources'),
                sam_matching_out_sqs=self._get_required_env('SAM_MATCHING_OUT_SQS_BUCKET', 'sam-matching-out-sqs'),
                sam_matching_out_runs=self._get_required_env('SAM_MATCHING_OUT_RUNS_BUCKET', 'sam-matching-out-runs'),
                sam_opportunity_responses=self._get_required_env('SAM_OPPORTUNITY_RESPONSES_BUCKET', 'sam-opportunity-responses'),
                sam_website=self._get_required_env('SAM_WEBSITE_BUCKET', 'sam-website'),
                sam_company_info=self._get_required_env('SAM_COMPANY_INFO_BUCKET', 'sam-company-info'),
                sam_download_files_logs=self._get_required_env('SAM_DOWNLOAD_FILES_LOGS_BUCKET', 'sam-download-files-logs')
            )
        return self._s3_config
    
    @property
    def sqs(self) -> SQSConfig:
        """Get SQS configuration."""
        if self._sqs_config is None:
            self._sqs_config = SQSConfig(
                sam_json_messages_queue=self._get_required_env('SQS_SAM_JSON_MESSAGES_QUEUE', 'sqs-sam-json-messages'),
                dead_letter_queue=self._get_required_env('SQS_DEAD_LETTER_QUEUE', 'sqs-sam-json-messages-dlq')
            )
        return self._sqs_config
    
    @property
    def bedrock(self) -> BedrockConfig:
        """Get Bedrock configuration."""
        if self._bedrock_config is None:
            self._bedrock_config = BedrockConfig(
                region=self._get_required_env('BEDROCK_REGION', 'us-east-1'),
                knowledge_base_id=self._get_required_env('KNOWLEDGE_BASE_ID', ''),  # Optional for S3 vector store
                model_id_desc=self._get_required_env('MODEL_ID_DESC', 'anthropic.claude-3-sonnet-20240229-v1:0'),
                model_id_match=self._get_required_env('MODEL_ID_MATCH', 'anthropic.claude-3-sonnet-20240229-v1:0'),
                max_tokens=int(self._get_required_env('MAX_TOKENS', '4000')),
                temperature=float(self._get_required_env('TEMPERATURE', '0.1'))
            )
        return self._bedrock_config
    
    @property
    def processing(self) -> ProcessingConfig:
        """Get processing configuration."""
        if self._processing_config is None:
            self._processing_config = ProcessingConfig(
                match_threshold=float(self._get_required_env('MATCH_THRESHOLD', '0.7')),
                max_attachment_files=int(self._get_required_env('MAX_ATTACHMENT_FILES', '4')),
                max_description_chars=int(self._get_required_env('MAX_DESCRIPTION_CHARS', '20000')),
                max_attachment_chars=int(self._get_required_env('MAX_ATTACHMENT_CHARS', '16000')),
                max_concurrent_downloads=int(self._get_required_env('MAX_CONCURRENT_DOWNLOADS', '10')),
                process_delay_seconds=int(self._get_required_env('PROCESS_DELAY_SECONDS', '60')),
                api_limit=int(self._get_required_env('API_LIMIT', '1000'))
            )
        return self._processing_config
    
    @property
    def sam_api(self) -> SAMAPIConfig:
        """Get SAM API configuration."""
        if self._sam_api_config is None:
            self._sam_api_config = SAMAPIConfig(
                base_url=self._get_required_env('SAM_API_URL', 'https://api.sam.gov/prod/opportunities/v2/search'),
                api_key=self._get_required_env('SAM_API_KEY'),
                timeout=int(self._get_required_env('SAM_API_TIMEOUT', '300')),
                max_retries=int(self._get_required_env('SAM_API_MAX_RETRIES', '0'))
            )
        return self._sam_api_config
    
    def _get_required_env(self, key: str, default: Optional[str] = None) -> str:
        """Get required environment variable with optional default."""
        value = os.environ.get(key, default)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def get_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
    
    def get_company_info(self) -> Dict[str, str]:
        """Get company information for report generation."""
        return {
            'name': self._get_required_env('COMPANY_NAME', 'Your Company'),
            'contact': self._get_required_env('COMPANY_CONTACT', 'contact@yourcompany.com')
        }

# Global configuration instance
config = ConfigManager()

# Constants
class Constants:
    """Application constants."""
    
    # Date formats
    DATE_FORMAT_SAM_API = "%m/%d/%Y"
    DATE_FORMAT_ISO = "%Y-%m-%d"
    DATE_FORMAT_TIMESTAMP = "%Y%m%dt%H%MZ"
    DATE_FORMAT_DAILY = "%Y-%m-%d"
    
    # File patterns
    OPPORTUNITY_FILE_PATTERN = "{opportunity_number}/opportunity.json"
    MATCH_RESULT_PATTERN = "{date}/{category}/{solicitation_id}.json"
    RUN_SUMMARY_PATTERN = "runs/{timestamp}.json"
    DASHBOARD_PATTERN = "dashboards/Summary_{date}.html"
    
    # Processing categories
    MATCH_CATEGORIES = {
        'MATCH': 'matches',
        'NO_MATCH': 'no_matches',
        'ERROR': 'errors'
    }
    
    # Lambda timeouts (seconds)
    LAMBDA_TIMEOUTS = {
        'sam-gov-daily-download': 900,  # 15 minutes
        'sam-json-processor': 600,      # 10 minutes
        'sam-sqs-generate-match-reports': 300,  # 5 minutes
        'sam-produce-user-report': 180,  # 3 minutes
        'sam-email-notification': 60,   # 1 minute
        'sam-merge-and-archive-result-logs': 300,  # 5 minutes
        'sam-produce-web-reports': 300   # 5 minutes
    }
    
    # Memory configurations (MB)
    LAMBDA_MEMORY = {
        'sam-gov-daily-download': 512,
        'sam-json-processor': 2048,
        'sam-sqs-generate-match-reports': 2048,
        'sam-produce-user-report': 1024,
        'sam-email-notification': 256,
        'sam-merge-and-archive-result-logs': 128,
        'sam-produce-web-reports': 1024
    }