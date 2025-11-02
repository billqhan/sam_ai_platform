"""
Dead Letter Queue handling utilities.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .aws_clients import aws_clients, handle_aws_error
from .config import config
from .error_handling import ProcessingError
from .logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class DLQMessage:
    """Structure for dead letter queue message analysis."""
    message_id: str
    body: str
    attributes: Dict[str, Any]
    message_attributes: Dict[str, Any]
    receive_count: int
    first_received_timestamp: datetime
    sent_timestamp: datetime
    error_analysis: Optional[str] = None

class DeadLetterQueueHandler:
    """Handler for dead letter queue operations and analysis."""
    
    def __init__(self):
        self.sqs_client = aws_clients.sqs
        self.dlq_url = None
    
    @handle_aws_error
    def get_dlq_url(self) -> str:
        """Get dead letter queue URL."""
        if not self.dlq_url:
            try:
                response = self.sqs_client.get_queue_url(
                    QueueName=config.sqs.dead_letter_queue
                )
                self.dlq_url = response['QueueUrl']
            except Exception as e:
                logger.error(f"Failed to get DLQ URL: {e}")
                raise ProcessingError(f"Dead letter queue not accessible: {e}")
        
        return self.dlq_url
    
    @handle_aws_error
    def get_dlq_messages(self, max_messages: int = 10) -> List[DLQMessage]:
        """
        Retrieve messages from dead letter queue for analysis.
        
        Args:
            max_messages: Maximum number of messages to retrieve
            
        Returns:
            List of DLQMessage objects
        """
        dlq_url = self.get_dlq_url()
        
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=dlq_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=1,  # Short wait for DLQ
                MessageAttributeNames=['All'],
                AttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            dlq_messages = []
            
            for msg in messages:
                dlq_message = self._parse_dlq_message(msg)
                dlq_messages.append(dlq_message)
            
            logger.info(f"Retrieved {len(dlq_messages)} messages from DLQ")
            return dlq_messages
            
        except Exception as e:
            logger.error(f"Failed to retrieve DLQ messages: {e}")
            raise ProcessingError(f"Failed to retrieve DLQ messages: {e}")
    
    def _parse_dlq_message(self, sqs_message: Dict[str, Any]) -> DLQMessage:
        """Parse SQS message into DLQMessage structure."""
        attributes = sqs_message.get('Attributes', {})
        
        # Parse timestamps
        sent_timestamp = datetime.fromtimestamp(
            int(attributes.get('SentTimestamp', '0')) / 1000
        )
        first_received_timestamp = datetime.fromtimestamp(
            int(attributes.get('ApproximateFirstReceiveTimestamp', '0')) / 1000
        )
        
        receive_count = int(attributes.get('ApproximateReceiveCount', '0'))
        
        dlq_message = DLQMessage(
            message_id=sqs_message['MessageId'],
            body=sqs_message['Body'],
            attributes=attributes,
            message_attributes=sqs_message.get('MessageAttributes', {}),
            receive_count=receive_count,
            first_received_timestamp=first_received_timestamp,
            sent_timestamp=sent_timestamp
        )
        
        # Analyze the error
        dlq_message.error_analysis = self._analyze_message_error(dlq_message)
        
        return dlq_message
    
    def _analyze_message_error(self, dlq_message: DLQMessage) -> str:
        """Analyze DLQ message to determine likely error cause."""
        try:
            # Try to parse the message body
            message_data = json.loads(dlq_message.body)
            
            # Check for common error patterns
            error_indicators = []
            
            # Check message age
            age_hours = (datetime.now() - dlq_message.sent_timestamp).total_seconds() / 3600
            if age_hours > 24:
                error_indicators.append(f"Message is {age_hours:.1f} hours old")
            
            # Check receive count
            if dlq_message.receive_count > 3:
                error_indicators.append(f"High receive count: {dlq_message.receive_count}")
            
            # Check message structure
            if 'bucket_name' not in message_data:
                error_indicators.append("Missing bucket_name in message")
            
            if 'object_key' not in message_data:
                error_indicators.append("Missing object_key in message")
            
            # Check object key format
            object_key = message_data.get('object_key', '')
            if not object_key.endswith('.json'):
                error_indicators.append(f"Invalid object key format: {object_key}")
            
            if error_indicators:
                return "; ".join(error_indicators)
            else:
                return "No obvious error patterns detected"
                
        except json.JSONDecodeError:
            return "Invalid JSON in message body"
        except Exception as e:
            return f"Error analyzing message: {str(e)}"
    
    @handle_aws_error
    def purge_dlq(self) -> None:
        """
        Purge all messages from dead letter queue.
        WARNING: This permanently deletes all messages.
        """
        dlq_url = self.get_dlq_url()
        
        try:
            self.sqs_client.purge_queue(QueueUrl=dlq_url)
            logger.warning("Dead letter queue has been purged")
            
        except Exception as e:
            logger.error(f"Failed to purge DLQ: {e}")
            raise ProcessingError(f"Failed to purge DLQ: {e}")
    
    @handle_aws_error
    def requeue_dlq_message(self, dlq_message: DLQMessage, target_queue_name: str) -> str:
        """
        Requeue a message from DLQ back to the main queue.
        
        Args:
            dlq_message: Message to requeue
            target_queue_name: Name of target queue
            
        Returns:
            New message ID
        """
        try:
            # Get target queue URL
            target_response = self.sqs_client.get_queue_url(QueueName=target_queue_name)
            target_queue_url = target_response['QueueUrl']
            
            # Send message to target queue
            send_response = self.sqs_client.send_message(
                QueueUrl=target_queue_url,
                MessageBody=dlq_message.body,
                MessageAttributes=dlq_message.message_attributes
            )
            
            new_message_id = send_response['MessageId']
            logger.info(f"Requeued message {dlq_message.message_id} as {new_message_id}")
            
            return new_message_id
            
        except Exception as e:
            logger.error(f"Failed to requeue message: {e}")
            raise ProcessingError(f"Failed to requeue message: {e}")
    
    @handle_aws_error
    def get_dlq_statistics(self) -> Dict[str, Any]:
        """Get statistics about dead letter queue."""
        dlq_url = self.get_dlq_url()
        
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=[
                    'ApproximateNumberOfMessages',
                    'ApproximateNumberOfMessagesNotVisible',
                    'CreatedTimestamp',
                    'LastModifiedTimestamp'
                ]
            )
            
            attributes = response['Attributes']
            
            return {
                'total_messages': int(attributes.get('ApproximateNumberOfMessages', '0')),
                'messages_in_flight': int(attributes.get('ApproximateNumberOfMessagesNotVisible', '0')),
                'created_timestamp': datetime.fromtimestamp(
                    int(attributes.get('CreatedTimestamp', '0'))
                ),
                'last_modified_timestamp': datetime.fromtimestamp(
                    int(attributes.get('LastModifiedTimestamp', '0'))
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get DLQ statistics: {e}")
            raise ProcessingError(f"Failed to get DLQ statistics: {e}")

def create_dlq_monitoring_report() -> Dict[str, Any]:
    """
    Create a monitoring report for dead letter queue health.
    
    Returns:
        Dictionary containing DLQ health metrics
    """
    dlq_handler = DeadLetterQueueHandler()
    
    try:
        # Get basic statistics
        stats = dlq_handler.get_dlq_statistics()
        
        # Get sample messages for analysis
        sample_messages = dlq_handler.get_dlq_messages(max_messages=5)
        
        # Analyze error patterns
        error_patterns = {}
        for msg in sample_messages:
            if msg.error_analysis:
                error_patterns[msg.error_analysis] = error_patterns.get(msg.error_analysis, 0) + 1
        
        return {
            'timestamp': datetime.now().isoformat(),
            'queue_statistics': stats,
            'sample_message_count': len(sample_messages),
            'error_patterns': error_patterns,
            'recommendations': _generate_dlq_recommendations(stats, error_patterns)
        }
        
    except Exception as e:
        logger.error(f"Failed to create DLQ monitoring report: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'status': 'failed'
        }

def _generate_dlq_recommendations(stats: Dict[str, Any], error_patterns: Dict[str, int]) -> List[str]:
    """Generate recommendations based on DLQ analysis."""
    recommendations = []
    
    total_messages = stats.get('total_messages', 0)
    
    if total_messages > 100:
        recommendations.append("High number of messages in DLQ - investigate processing failures")
    
    if total_messages > 0:
        recommendations.append("Review error patterns and consider message reprocessing")
    
    if 'Invalid JSON in message body' in error_patterns:
        recommendations.append("Fix message formatting issues in upstream systems")
    
    if any('Missing' in pattern for pattern in error_patterns):
        recommendations.append("Validate message structure before sending to queue")
    
    if not recommendations:
        recommendations.append("DLQ appears healthy - no immediate action required")
    
    return recommendations

# Global DLQ handler instance
dlq_handler = DeadLetterQueueHandler()