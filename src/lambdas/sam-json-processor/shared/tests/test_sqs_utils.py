"""
Unit tests for SQS utilities.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError

from ..sqs_utils import (
    S3EventMessage, 
    SQSMessageHandler, 
    create_s3_event_notification_config,
    format_lambda_sqs_event_record
)
from ..error_handling import ProcessingError


class TestS3EventMessage:
    """Test S3EventMessage dataclass."""
    
    def test_create_s3_event_message(self):
        """Test creating S3EventMessage."""
        message = S3EventMessage(
            bucket_name="test-bucket",
            object_key="test-key.json",
            event_name="s3:ObjectCreated:Put",
            event_time="2024-01-01T12:00:00Z",
            object_size=1024,
            etag="test-etag"
        )
        
        assert message.bucket_name == "test-bucket"
        assert message.object_key == "test-key.json"
        assert message.event_name == "s3:ObjectCreated:Put"
        assert message.opportunity_number is None
    
    def test_s3_event_message_with_opportunity_number(self):
        """Test S3EventMessage with opportunity number in key."""
        message = S3EventMessage(
            bucket_name="test-bucket",
            object_key="OPP123/opportunity.json",
            event_name="s3:ObjectCreated:Put",
            event_time="2024-01-01T12:00:00Z",
            object_size=1024,
            etag="test-etag",
            opportunity_number="OPP123"
        )
        
        assert message.opportunity_number == "OPP123"
    
    def test_to_dict(self):
        """Test converting S3EventMessage to dictionary."""
        message = S3EventMessage(
            bucket_name="test-bucket",
            object_key="test-key.json",
            event_name="s3:ObjectCreated:Put",
            event_time="2024-01-01T12:00:00Z",
            object_size=1024,
            etag="test-etag"
        )
        
        result = message.to_dict()
        
        assert isinstance(result, dict)
        assert result['bucket_name'] == "test-bucket"
        assert result['object_key'] == "test-key.json"
        assert result['opportunity_number'] is None
    
    def test_from_s3_event(self):
        """Test creating S3EventMessage from S3 event."""
        s3_event = {
            'eventName': 's3:ObjectCreated:Put',
            'eventTime': '2024-01-01T12:00:00Z',
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {
                    'key': 'OPP123/opportunity.json',
                    'size': 1024,
                    'eTag': 'test-etag'
                }
            }
        }
        
        message = S3EventMessage.from_s3_event(s3_event)
        
        assert message.bucket_name == "test-bucket"
        assert message.object_key == "OPP123/opportunity.json"
        assert message.opportunity_number == "OPP123"
        assert message.event_name == "s3:ObjectCreated:Put"
        assert message.object_size == 1024
    
    def test_from_s3_event_no_opportunity_number(self):
        """Test creating S3EventMessage from S3 event without opportunity number."""
        s3_event = {
            'eventName': 's3:ObjectCreated:Put',
            'eventTime': '2024-01-01T12:00:00Z',
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {
                    'key': 'simple-file.json',
                    'size': 1024,
                    'eTag': 'test-etag'
                }
            }
        }
        
        message = S3EventMessage.from_s3_event(s3_event)
        
        assert message.opportunity_number is None


class TestSQSMessageHandler:
    """Test SQSMessageHandler class."""
    
    @pytest.fixture
    def handler(self):
        """Create SQSMessageHandler instance."""
        return SQSMessageHandler()
    
    @pytest.fixture
    def mock_sqs_client(self):
        """Mock SQS client."""
        with patch('src.shared.sqs_utils.aws_clients.sqs') as mock_client:
            yield mock_client
    
    def test_get_queue_url_success(self, handler, mock_sqs_client):
        """Test successful queue URL retrieval."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        
        url = handler.get_queue_url('test-queue')
        
        assert url == 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        mock_sqs_client.get_queue_url.assert_called_once_with(QueueName='test-queue')
    
    def test_get_queue_url_not_found(self, handler, mock_sqs_client):
        """Test queue URL retrieval when queue doesn't exist."""
        mock_sqs_client.get_queue_url.side_effect = ClientError(
            {'Error': {'Code': 'AWS.SimpleQueueService.NonExistentQueue'}},
            'GetQueueUrl'
        )
        
        with pytest.raises(ProcessingError, match="SQS queue test-queue not found"):
            handler.get_queue_url('test-queue')
    
    def test_send_s3_event_message_success(self, handler, mock_sqs_client):
        """Test successful S3 event message sending."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.send_message.return_value = {
            'MessageId': 'test-message-id'
        }
        
        message = S3EventMessage(
            bucket_name="test-bucket",
            object_key="OPP123/opportunity.json",
            event_name="s3:ObjectCreated:Put",
            event_time="2024-01-01T12:00:00Z",
            object_size=1024,
            etag="test-etag",
            opportunity_number="OPP123"
        )
        
        message_id = handler.send_s3_event_message(message)
        
        assert message_id == 'test-message-id'
        
        # Verify send_message was called with correct parameters
        call_args = mock_sqs_client.send_message.call_args
        assert call_args[1]['QueueUrl'] == 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        
        # Verify message body
        message_body = json.loads(call_args[1]['MessageBody'])
        assert message_body['bucket_name'] == 'test-bucket'
        assert message_body['opportunity_number'] == 'OPP123'
        
        # Verify message attributes
        attributes = call_args[1]['MessageAttributes']
        assert attributes['EventName']['StringValue'] == 's3:ObjectCreated:Put'
        assert attributes['BucketName']['StringValue'] == 'test-bucket'
        assert attributes['OpportunityNumber']['StringValue'] == 'OPP123'
    
    def test_send_s3_event_message_no_opportunity_number(self, handler, mock_sqs_client):
        """Test sending S3 event message without opportunity number."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.send_message.return_value = {
            'MessageId': 'test-message-id'
        }
        
        message = S3EventMessage(
            bucket_name="test-bucket",
            object_key="simple-file.json",
            event_name="s3:ObjectCreated:Put",
            event_time="2024-01-01T12:00:00Z",
            object_size=1024,
            etag="test-etag"
        )
        
        handler.send_s3_event_message(message)
        
        # Verify message attributes don't include OpportunityNumber
        call_args = mock_sqs_client.send_message.call_args
        attributes = call_args[1]['MessageAttributes']
        assert 'OpportunityNumber' not in attributes
    
    def test_receive_messages_success(self, handler, mock_sqs_client):
        """Test successful message receiving."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.receive_message.return_value = {
            'Messages': [
                {
                    'MessageId': 'msg-1',
                    'Body': '{"test": "data"}',
                    'ReceiptHandle': 'receipt-1'
                }
            ]
        }
        
        messages = handler.receive_messages(max_messages=1)
        
        assert len(messages) == 1
        assert messages[0]['MessageId'] == 'msg-1'
        
        mock_sqs_client.receive_message.assert_called_once_with(
            QueueUrl='https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            MessageAttributeNames=['All'],
            AttributeNames=['All']
        )
    
    def test_receive_messages_empty(self, handler, mock_sqs_client):
        """Test receiving messages when queue is empty."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.receive_message.return_value = {}
        
        messages = handler.receive_messages()
        
        assert len(messages) == 0
    
    def test_delete_message_success(self, handler, mock_sqs_client):
        """Test successful message deletion."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        
        handler.delete_message('test-receipt-handle')
        
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl='https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
            ReceiptHandle='test-receipt-handle'
        )
    
    def test_parse_s3_event_message_success(self, handler):
        """Test successful S3 event message parsing."""
        message_body = json.dumps({
            'bucket_name': 'test-bucket',
            'object_key': 'OPP123/opportunity.json',
            'event_name': 's3:ObjectCreated:Put',
            'event_time': '2024-01-01T12:00:00Z',
            'object_size': 1024,
            'etag': 'test-etag',
            'opportunity_number': 'OPP123'
        })
        
        message = handler.parse_s3_event_message(message_body)
        
        assert isinstance(message, S3EventMessage)
        assert message.bucket_name == 'test-bucket'
        assert message.opportunity_number == 'OPP123'
    
    def test_parse_s3_event_message_invalid_json(self, handler):
        """Test parsing invalid JSON message."""
        with pytest.raises(ProcessingError, match="Invalid SQS message format"):
            handler.parse_s3_event_message('invalid json')
    
    def test_parse_s3_event_message_missing_fields(self, handler):
        """Test parsing message with missing required fields."""
        message_body = json.dumps({
            'bucket_name': 'test-bucket'
            # Missing required fields
        })
        
        with pytest.raises(ProcessingError, match="Invalid SQS message format"):
            handler.parse_s3_event_message(message_body)
    
    def test_get_queue_attributes_success(self, handler, mock_sqs_client):
        """Test successful queue attributes retrieval."""
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.get_queue_attributes.return_value = {
            'Attributes': {
                'ApproximateNumberOfMessages': '5',
                'VisibilityTimeoutSeconds': '300'
            }
        }
        
        attributes = handler.get_queue_attributes('test-queue')
        
        assert attributes['ApproximateNumberOfMessages'] == '5'
        assert attributes['VisibilityTimeoutSeconds'] == '300'


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_s3_event_notification_config(self):
        """Test S3 event notification configuration creation."""
        config = create_s3_event_notification_config()
        
        assert 'QueueConfigurations' in config
        queue_configs = config['QueueConfigurations']
        assert len(queue_configs) == 1
        
        queue_config = queue_configs[0]
        assert queue_config['Id'] == 'sam-json-processor-notification'
        assert 's3:ObjectCreated:*' in queue_config['Events']
        assert queue_config['Filter']['Key']['FilterRules'][0]['Value'] == '.json'
    
    def test_format_lambda_sqs_event_record(self):
        """Test formatting SQS message for Lambda event."""
        sqs_message = {
            'MessageId': 'test-msg-id',
            'ReceiptHandle': 'test-receipt',
            'Body': '{"test": "data"}',
            'MD5OfBody': 'test-md5',
            'Attributes': {'SentTimestamp': '1234567890'},
            'MessageAttributes': {'TestAttr': {'StringValue': 'test'}}
        }
        
        formatted = format_lambda_sqs_event_record(sqs_message)
        
        assert formatted['messageId'] == 'test-msg-id'
        assert formatted['receiptHandle'] == 'test-receipt'
        assert formatted['body'] == '{"test": "data"}'
        assert formatted['eventSource'] == 'aws:sqs'
        assert formatted['awsRegion'] == 'us-east-1'
        assert 'eventSourceARN' in formatted


@pytest.fixture
def sample_s3_event():
    """Sample S3 event for testing."""
    return {
        'eventName': 's3:ObjectCreated:Put',
        'eventTime': '2024-01-01T12:00:00Z',
        's3': {
            'bucket': {'name': 'test-bucket'},
            'object': {
                'key': 'OPP123/opportunity.json',
                'size': 1024,
                'eTag': 'test-etag'
            }
        }
    }


@pytest.fixture
def sample_sqs_message():
    """Sample SQS message for testing."""
    return {
        'MessageId': 'test-message-id',
        'ReceiptHandle': 'test-receipt-handle',
        'Body': json.dumps({
            'bucket_name': 'test-bucket',
            'object_key': 'OPP123/opportunity.json',
            'event_name': 's3:ObjectCreated:Put',
            'event_time': '2024-01-01T12:00:00Z',
            'object_size': 1024,
            'etag': 'test-etag',
            'opportunity_number': 'OPP123'
        }),
        'MD5OfBody': 'test-md5',
        'Attributes': {
            'SentTimestamp': '1704110400000',
            'ApproximateReceiveCount': '1'
        },
        'MessageAttributes': {
            'EventName': {'StringValue': 's3:ObjectCreated:Put'},
            'BucketName': {'StringValue': 'test-bucket'}
        }
    }


class TestIntegration:
    """Integration tests for SQS utilities."""
    
    def test_end_to_end_message_flow(self, sample_s3_event, mock_sqs_client):
        """Test complete message flow from S3 event to SQS processing."""
        # Mock SQS responses
        mock_sqs_client.get_queue_url.return_value = {
            'QueueUrl': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        }
        mock_sqs_client.send_message.return_value = {
            'MessageId': 'test-message-id'
        }
        
        # Create S3 event message
        s3_message = S3EventMessage.from_s3_event(sample_s3_event)
        
        # Send to SQS
        handler = SQSMessageHandler()
        message_id = handler.send_s3_event_message(s3_message)
        
        # Verify message was sent
        assert message_id == 'test-message-id'
        
        # Verify the message body can be parsed back
        call_args = mock_sqs_client.send_message.call_args
        message_body = call_args[1]['MessageBody']
        parsed_message = handler.parse_s3_event_message(message_body)
        
        assert parsed_message.bucket_name == s3_message.bucket_name
        assert parsed_message.object_key == s3_message.object_key
        assert parsed_message.opportunity_number == s3_message.opportunity_number