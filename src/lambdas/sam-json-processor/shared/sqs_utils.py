"""
SQS utilities for message handling and S3 event integration.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from botocore.exceptions import ClientError

from .aws_clients import aws_clients, handle_aws_error
from .config import config
from .error_handling import ProcessingError

logger = logging.getLogger(__name__)

@dataclass
class S3EventMessage:
    """Structure for S3 event messages sent to SQS."""
    bucket_name: str
    object_key: str
    event_name: str
    event_time: str
    object_size: int
    etag: str
    opportunity_number: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_s3_event(cls, s3_event: Dict[str, Any]) -> 'S3EventMessage':
        """Create message from S3 event notification."""
        s3_record = s3_event['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = s3_record['object']['key']
        
        # Extract opportunity number from object key if present
        opportunity_number = None
        if '/' in object_key:
            opportunity_number = object_key.split('/')[0]
        
        return cls(
            bucket_name=bucket_name,
            object_key=object_key,
            event_name=s3_event['eventName'],
            event_time=s3_event['eventTime'],
            object_size=s3_record['object']['size'],
            etag=s3_record['object']['eTag'],
            opportunity_number=opportunity_number
        )

class SQSMessageHandler:
    """Handler for SQS message operations."""
    
    def __init__(self):
        self.sqs_client = aws_clients.sqs
        self.queue_url = None
        self.dlq_url = None
    
    @handle_aws_error
    def get_queue_url(self, queue_name: str) -> str:
        """Get SQS queue URL by name."""
        try:
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except ClientError as e:
            if e.response['Error']['Code'] == 'AWS.SimpleQueueService.NonExistentQueue':
                logger.error(f"Queue {queue_name} does not exist")
                raise ProcessingError(f"SQS queue {queue_name} not found")
            raise
    
    @handle_aws_error
    def send_s3_event_message(self, s3_event_message: S3EventMessage) -> str:
        """Send S3 event message to SQS queue."""
        if not self.queue_url:
            self.queue_url = self.get_queue_url(config.sqs.sam_json_messages_queue)
        
        message_body = json.dumps(s3_event_message.to_dict())
        
        # Add message attributes for filtering and routing
        message_attributes = {
            'EventName': {
                'StringValue': s3_event_message.event_name,
                'DataType': 'String'
            },
            'BucketName': {
                'StringValue': s3_event_message.bucket_name,
                'DataType': 'String'
            }
        }
        
        if s3_event_message.opportunity_number:
            message_attributes['OpportunityNumber'] = {
                'StringValue': s3_event_message.opportunity_number,
                'DataType': 'String'
            }
        
        try:
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body,
                MessageAttributes=message_attributes
            )
            
            message_id = response['MessageId']
            logger.info(f"Sent SQS message {message_id} for object {s3_event_message.object_key}")
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to send SQS message: {e}")
            raise ProcessingError(f"Failed to send SQS message: {e}")
    
    @handle_aws_error
    def receive_messages(self, max_messages: int = 1, wait_time: int = 20) -> List[Dict[str, Any]]:
        """Receive messages from SQS queue."""
        if not self.queue_url:
            self.queue_url = self.get_queue_url(config.sqs.sam_json_messages_queue)
        
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All'],
                AttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            logger.info(f"Received {len(messages)} messages from SQS")
            return messages
            
        except ClientError as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            raise ProcessingError(f"Failed to receive SQS messages: {e}")
    
    @handle_aws_error
    def delete_message(self, receipt_handle: str) -> None:
        """Delete processed message from SQS queue."""
        if not self.queue_url:
            self.queue_url = self.get_queue_url(config.sqs.sam_json_messages_queue)
        
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info("Successfully deleted SQS message")
            
        except ClientError as e:
            logger.error(f"Failed to delete SQS message: {e}")
            raise ProcessingError(f"Failed to delete SQS message: {e}")
    
    @handle_aws_error
    def parse_s3_event_message(self, message_body: str) -> S3EventMessage:
        """Parse SQS message body to extract S3 event information."""
        try:
            message_data = json.loads(message_body)
            
            # Validate required fields
            required_fields = ['bucket_name', 'object_key', 'event_name', 'event_time']
            for field in required_fields:
                if field not in message_data:
                    raise ValueError(f"Missing required field: {field}")
            
            return S3EventMessage(**message_data)
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse SQS message: {e}")
            raise ProcessingError(f"Invalid SQS message format: {e}")
    
    @handle_aws_error
    def get_queue_attributes(self, queue_name: str) -> Dict[str, Any]:
        """Get queue attributes including dead letter queue configuration."""
        queue_url = self.get_queue_url(queue_name)
        
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            return response['Attributes']
            
        except ClientError as e:
            logger.error(f"Failed to get queue attributes: {e}")
            raise ProcessingError(f"Failed to get queue attributes: {e}")

def create_s3_event_notification_config() -> Dict[str, Any]:
    """Create S3 event notification configuration for SQS integration."""
    return {
        'QueueConfigurations': [
            {
                'Id': 'sam-json-processor-notification',
                'QueueArn': f'arn:aws:sqs:us-east-1:{{AWS::AccountId}}:{config.sqs.sam_json_messages_queue}',
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {
                                'Name': 'suffix',
                                'Value': '.json'
                            }
                        ]
                    }
                }
            }
        ]
    }

def format_lambda_sqs_event_record(sqs_message: Dict[str, Any]) -> Dict[str, Any]:
    """Format SQS message for Lambda event processing."""
    return {
        'messageId': sqs_message['MessageId'],
        'receiptHandle': sqs_message['ReceiptHandle'],
        'body': sqs_message['Body'],
        'attributes': sqs_message.get('Attributes', {}),
        'messageAttributes': sqs_message.get('MessageAttributes', {}),
        'md5OfBody': sqs_message['MD5OfBody'],
        'eventSource': 'aws:sqs',
        'eventSourceARN': f'arn:aws:sqs:us-east-1:{{AWS::AccountId}}:{config.sqs.sam_json_messages_queue}',
        'awsRegion': 'us-east-1'
    }

# Global SQS handler instance
sqs_handler = SQSMessageHandler()