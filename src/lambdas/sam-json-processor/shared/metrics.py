"""
CloudWatch custom metrics utilities for the AI RFP Response Agent.
"""
import boto3
from datetime import datetime
from typing import Dict, List, Optional, Any
from .logging_config import get_logger

logger = get_logger(__name__)

class MetricsPublisher:
    """Publishes custom metrics to CloudWatch."""
    
    def __init__(self, namespace: str = 'AI-RFP-Response-Agent'):
        self.namespace = namespace
        self.cloudwatch = boto3.client('cloudwatch')
        self._metric_buffer = []
        self._max_buffer_size = 20  # CloudWatch limit
    
    def put_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                   dimensions: Optional[Dict[str, str]] = None, timestamp: Optional[datetime] = None):
        """Add a metric to the buffer for batch publishing."""
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': timestamp or datetime.utcnow()
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': key, 'Value': value} for key, value in dimensions.items()
            ]
        
        self._metric_buffer.append(metric_data)
        logger.metric(metric_name, value, unit, dimensions=dimensions)
        
        # Auto-flush if buffer is full
        if len(self._metric_buffer) >= self._max_buffer_size:
            self.flush()
    
    def flush(self):
        """Publish all buffered metrics to CloudWatch."""
        if not self._metric_buffer:
            return
        
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=self._metric_buffer
            )
            logger.info(f"Published {len(self._metric_buffer)} metrics to CloudWatch")
            self._metric_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {str(e)}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()

class BusinessMetrics:
    """High-level business metrics for the AI RFP Response Agent."""
    
    def __init__(self, metrics_publisher: MetricsPublisher):
        self.publisher = metrics_publisher
    
    def record_api_call(self, success: bool, service: str = 'SAM.gov'):
        """Record API call success/failure."""
        metric_name = 'SuccessfulApiCalls' if success else 'FailedApiCalls'
        dimensions = {'Service': service}
        self.publisher.put_metric(metric_name, 1, 'Count', dimensions)
    
    def record_opportunity_processed(self, success: bool):
        """Record opportunity processing result."""
        if success:
            self.publisher.put_metric('OpportunitiesProcessed', 1, 'Count')
        else:
            self.publisher.put_metric('OpportunityProcessingErrors', 1, 'Count')
    
    def record_match_result(self, is_match: bool, score: float):
        """Record match analysis result."""
        if is_match:
            self.publisher.put_metric('MatchesFound', 1, 'Count')
        else:
            self.publisher.put_metric('NoMatchesFound', 1, 'Count')
        
        self.publisher.put_metric('MatchScore', score, 'None')
    
    def record_bedrock_call(self, success: bool, model_id: str = None):
        """Record Bedrock API call result."""
        metric_name = 'BedrockCallsSuccess' if success else 'BedrockCallsError'
        dimensions = {'ModelId': model_id} if model_id else None
        self.publisher.put_metric(metric_name, 1, 'Count', dimensions)
    
    def record_processing_rate(self, opportunities_per_minute: float):
        """Record processing rate metric."""
        self.publisher.put_metric('ProcessingRate', opportunities_per_minute, 'Count/Second')
    
    def record_cost_metric(self, service: str, cost_usd: float):
        """Record cost metrics for monitoring."""
        dimensions = {'Service': service}
        self.publisher.put_metric('ServiceCost', cost_usd, 'None', dimensions)
    
    def record_resource_utilization(self, resource_type: str, utilization_percent: float):
        """Record resource utilization metrics."""
        dimensions = {'ResourceType': resource_type}
        self.publisher.put_metric('ResourceUtilization', utilization_percent, 'Percent', dimensions)

def get_metrics_publisher(namespace: str = 'AI-RFP-Response-Agent') -> MetricsPublisher:
    """Get a metrics publisher instance."""
    return MetricsPublisher(namespace)

def get_business_metrics(namespace: str = 'AI-RFP-Response-Agent') -> BusinessMetrics:
    """Get a business metrics instance."""
    publisher = get_metrics_publisher(namespace)
    return BusinessMetrics(publisher)