"""
Unit tests for SQS processor utilities.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from ..sqs_processor import (
    SQSProcessingResult,
    SQSBatchProcessor,
    SQSMessageValidator,
    create_sqs_processor,
    handle_sqs_processing_errors
)
from ..sqs_utils import S3EventMessage
from ..error_handling import ProcessingError, RetryableError


class TestSQSProcessingResult:
    """Test SQSProcessingResult dataclass."""
    
    def test_create_processing_result(self):
        """Test creating SQSProcessingResult."""
        result = SQSProcessingResult(
            message_id="test-msg-id",
            success=True,
            processing_time_ms=1500
        )
        
        assert result.message_id == "test-msg-id"
        assert result.success is True
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.processing_time_ms == 1500
    
    def test_create_failed_processing_result(self):
        """Test creating failed SQSProcessingResult."""
        result = SQSProcessingResult(
            message_id="test-msg-id",
            success=False,
            error_message="Processing failed",
            retry_count=2
        )
        
        assert result.success is False
        assert result.error_message == "Processing failed"
        assert result.retry_count == 2


class TestSQSBatchProcessor:
    """Test SQSBatchProcessor class."""
    
    @pytest.fixture
    def mock_message_handler(self):
        """Mock message handler function."""
        return Mock()
    
    @pytest.fixture
    def processor(self, mock_message_handler):
        """Create SQSBatchProcessor instance."""
        return SQSBatchProcessor(mock_message_handler)
    
    @pytest.fixture
    def sample_lambda_event(self):
        """Sample Lambda SQS event."""
        return {
            'Records': [
                {
                    'messageId': 'msg-1',
                    'receiptHandle': 'receipt-1',
                    'body': json.dumps({
                        'bucket_name': 'test-bucket',
                        'object_key': 'OPP123/opportunity.json',
                        'event_name': 's3:ObjectCreated:Put',
                        'event_time': '2024-01-01T12:00:00Z',
                        'object_size': 1024,
                        'etag': 'test-etag',
                        'opportunity_number': 'OPP123'
                    }),
                    'attributes': {
                        'ApproximateReceiveCount': '1'
                    }
                }
            ]
        }
    
    def test_process_lambda_event_success(self, processor, mock_message_handler, sample_lambda_event):
        """Test successful Lambda event processing."""
        # Mock successful message handling
        mock_message_handler.return_value = None
        
        with patch('src.shared.sqs_processor.sqs_handler') as mock_sqs_handler:
            mock_sqs_handler.parse_s3_event_message.return_value = S3EventMessage(
                bucket_name='test-bucket',
                object_key='OPP123/opportunity.json',
                event_name='s3:ObjectCreated:Put',
                event_time='2024-01-01T12:00:00Z',
                object_size=1024,
                etag='test-etag',
                opportunity_number='OPP123'
            )
            
            result = processor.process_lambda_event(sample_lambda_event, None)
        
        assert result['statusCode'] == 200
        assert result['totalMessages'] == 1
        assert result['successfulMessages'] == 1
        assert result['failedMessages'] == 0
        
        # Verify handler was called
        mock_message_handler.assert_called_once()
    
    def test_process_lambda_event_with_failure(self, processor, mock_message_handler, sample_lambda_event):
        """Test Lambda event processing with message failure."""
        # Mock message handler to raise exception
        mock_message_handler.side_effect = Exception("Processing failed")
        
        with patch('src.shared.sqs_processor.sqs_handler') as mock_sqs_handler:
            mock_sqs_handler.parse_s3_event_message.return_value = S3EventMessage(
                bucket_name='test-bucket',
                object_key='OPP123/opportunity.json',
                event_name='s3:ObjectCreated:Put',
                event_time='2024-01-01T12:00:00Z',
                object_size=1024,
                etag='test-etag',
                opportunity_number='OPP123'
            )
            
            result = processor.process_lambda_event(sample_lambda_event, None)
        
        assert result['statusCode'] == 207  # Multi-Status
        assert result['totalMessages'] == 1
        assert result['successfulMessages'] == 0
        assert result['failedMessages'] == 1
    
    def test_process_lambda_event_with_retryable_error(self, processor, mock_message_handler, sample_lambda_event):
        """Test Lambda event processing with retryable error."""
        # Mock message handler to raise retryable error
        mock_message_handler.side_effect = RetryableError("Temporary failure")
        
        with patch('src.shared.sqs_processor.sqs_handler') as mock_sqs_handler:
            mock_sqs_handler.parse_s3_event_message.return_value = S3EventMessage(
                bucket_name='test-bucket',
                object_key='OPP123/opportunity.json',
                event_name='s3:ObjectCreated:Put',
                event_time='2024-01-01T12:00:00Z',
                object_size=1024,
                etag='test-etag',
                opportunity_number='OPP123'
            )
            
            result = processor.process_lambda_event(sample_lambda_event, None)
        
        assert result['statusCode'] == 207
        assert result['failedMessages'] == 1
        
        # Check that error message indicates retryable error
        failed_result = result['results'][0]
        assert 'Retryable error' in failed_result['error_message']
    
    def test_process_empty_event(self, processor):
        """Test processing empty Lambda event."""
        empty_event = {'Records': []}
        
        result = processor.process_lambda_event(empty_event, None)
        
        assert result['statusCode'] == 200
        assert result['totalMessages'] == 0
        assert result['successfulMessages'] == 0
        assert result['failedMessages'] == 0
    
    def test_get_retry_count(self, processor):
        """Test extracting retry count from SQS record."""
        record_with_retry = {
            'attributes': {
                'ApproximateReceiveCount': '3'
            }
        }
        
        retry_count = processor._get_retry_count(record_with_retry)
        assert retry_count == 2  # ApproximateReceiveCount - 1
        
        # Test with missing attributes
        record_without_retry = {}
        retry_count = processor._get_retry_count(record_without_retry)
        assert retry_count == 0
    
    def test_multiple_messages_processing(self, processor, mock_message_handler):
        """Test processing multiple messages in batch."""
        multi_message_event = {
            'Records': [
                {
                    'messageId': 'msg-1',
                    'receiptHandle': 'receipt-1',
                    'body': json.dumps({
                        'bucket_name': 'test-bucket',
                        'object_key': 'OPP123/opportunity.json',
                        'event_name': 's3:ObjectCreated:Put',
                        'event_time': '2024-01-01T12:00:00Z',
                        'object_size': 1024,
                        'etag': 'test-etag'
                    }),
                    'attributes': {'ApproximateReceiveCount': '1'}
                },
                {
                    'messageId': 'msg-2',
                    'receiptHandle': 'receipt-2',
                    'body': json.dumps({
                        'bucket_name': 'test-bucket',
                        'object_key': 'OPP456/opportunity.json',
                        'event_name': 's3:ObjectCreated:Put',
                        'event_time': '2024-01-01T12:00:00Z',
                        'object_size': 2048,
                        'etag': 'test-etag-2'
                    }),
                    'attributes': {'ApproximateReceiveCount': '1'}
                }
            ]
        }
        
        # Mock first message success, second message failure
        mock_message_handler.side_effect = [None, Exception("Second message failed")]
        
        with patch('src.shared.sqs_processor.sqs_handler') as mock_sqs_handler:
            mock_sqs_handler.parse_s3_event_message.side_effect = [
                S3EventMessage(
                    bucket_name='test-bucket',
                    object_key='OPP123/opportunity.json',
                    event_name='s3:ObjectCreated:Put',
                    event_time='2024-01-01T12:00:00Z',
                    object_size=1024,
                    etag='test-etag'
                ),
                S3EventMessage(
                    bucket_name='test-bucket',
                    object_key='OPP456/opportunity.json',
                    event_name='s3:ObjectCreated:Put',
                    event_time='2024-01-01T12:00:00Z',
                    object_size=2048,
                    etag='test-etag-2'
                )
            ]
            
            result = processor.process_lambda_event(multi_message_event, None)
        
        assert result['totalMessages'] == 2
        assert result['successfulMessages'] == 1
        assert result['failedMessages'] == 1
        assert len(result['results']) == 2


class TestSQSMessageValidator:
    """Test SQSMessageValidator class."""
    
    def test_validate_lambda_sqs_event_success(self):
        """Test successful Lambda SQS event validation."""
        valid_event = {
            'Records': [
                {
                    'messageId': 'test-msg-id',
                    'body': '{"test": "data"}',
                    'receiptHandle': 'test-receipt'
                }
            ]
        }
        
        result = SQSMessageValidator.validate_lambda_sqs_event(valid_event)
        assert result is True
    
    def test_validate_lambda_sqs_event_not_dict(self):
        """Test validation with non-dictionary event."""
        with pytest.raises(ProcessingError, match="Event must be a dictionary"):
            SQSMessageValidator.validate_lambda_sqs_event("not a dict")
    
    def test_validate_lambda_sqs_event_missing_records(self):
        """Test validation with missing Records field."""
        invalid_event = {'NotRecords': []}
        
        with pytest.raises(ProcessingError, match="Event must contain 'Records' field"):
            SQSMessageValidator.validate_lambda_sqs_event(invalid_event)
    
    def test_validate_lambda_sqs_event_records_not_list(self):
        """Test validation with Records not being a list."""
        invalid_event = {'Records': 'not a list'}
        
        with pytest.raises(ProcessingError, match="Records must be a list"):
            SQSMessageValidator.validate_lambda_sqs_event(invalid_event)
    
    def test_validate_lambda_sqs_event_empty_records(self):
        """Test validation with empty Records list."""
        invalid_event = {'Records': []}
        
        with pytest.raises(ProcessingError, match="Records list cannot be empty"):
            SQSMessageValidator.validate_lambda_sqs_event(invalid_event)
    
    def test_validate_sqs_record_success(self):
        """Test successful SQS record validation."""
        valid_record = {
            'messageId': 'test-msg-id',
            'body': '{"test": "data"}',
            'receiptHandle': 'test-receipt'
        }
        
        result = SQSMessageValidator.validate_sqs_record(valid_record)
        assert result is True
    
    def test_validate_sqs_record_missing_field(self):
        """Test SQS record validation with missing required field."""
        invalid_record = {
            'messageId': 'test-msg-id',
            'body': '{"test": "data"}'
            # Missing receiptHandle
        }
        
        with pytest.raises(ProcessingError, match="Record 0 missing required field: receiptHandle"):
            SQSMessageValidator.validate_sqs_record(invalid_record)
    
    def test_validate_sqs_record_invalid_json_body(self):
        """Test SQS record validation with invalid JSON body."""
        invalid_record = {
            'messageId': 'test-msg-id',
            'body': 'invalid json',
            'receiptHandle': 'test-receipt'
        }
        
        with pytest.raises(ProcessingError, match="Record 0 has invalid JSON body"):
            SQSMessageValidator.validate_sqs_record(invalid_record)
    
    def test_validate_s3_event_message_success(self):
        """Test successful S3 event message validation."""
        valid_message = S3EventMessage(
            bucket_name='test-bucket',
            object_key='test-file.json',
            event_name='s3:ObjectCreated:Put',
            event_time='2024-01-01T12:00:00Z',
            object_size=1024,
            etag='test-etag'
        )
        
        result = SQSMessageValidator.validate_s3_event_message(valid_message)
        assert result is True
    
    def test_validate_s3_event_message_missing_bucket(self):
        """Test S3 event message validation with missing bucket name."""
        invalid_message = S3EventMessage(
            bucket_name='',
            object_key='test-file.json',
            event_name='s3:ObjectCreated:Put',
            event_time='2024-01-01T12:00:00Z',
            object_size=1024,
            etag='test-etag'
        )
        
        with pytest.raises(ProcessingError, match="S3 event message missing bucket name"):
            SQSMessageValidator.validate_s3_event_message(invalid_message)
    
    def test_validate_s3_event_message_invalid_object_key(self):
        """Test S3 event message validation with invalid object key."""
        invalid_message = S3EventMessage(
            bucket_name='test-bucket',
            object_key='test-file.txt',  # Not .json
            event_name='s3:ObjectCreated:Put',
            event_time='2024-01-01T12:00:00Z',
            object_size=1024,
            etag='test-etag'
        )
        
        with pytest.raises(ProcessingError, match="Object key must end with .json"):
            SQSMessageValidator.validate_s3_event_message(invalid_message)
    
    def test_validate_s3_event_message_unsupported_event(self):
        """Test S3 event message validation with unsupported event type."""
        invalid_message = S3EventMessage(
            bucket_name='test-bucket',
            object_key='test-file.json',
            event_name='s3:ObjectRemoved:Delete',  # Not a creation event
            event_time='2024-01-01T12:00:00Z',
            object_size=1024,
            etag='test-etag'
        )
        
        with pytest.raises(ProcessingError, match="Unsupported event type"):
            SQSMessageValidator.validate_s3_event_message(invalid_message)


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_sqs_processor(self):
        """Test SQS processor factory function."""
        mock_handler = Mock()
        processor = create_sqs_processor(mock_handler)
        
        assert isinstance(processor, SQSBatchProcessor)
        assert processor.message_handler == mock_handler
    
    def test_handle_sqs_processing_errors_success(self):
        """Test error handling decorator with successful function."""
        @handle_sqs_processing_errors
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_handle_sqs_processing_errors_retryable_error(self):
        """Test error handling decorator with retryable error."""
        @handle_sqs_processing_errors
        def retryable_error_function():
            raise RetryableError("Temporary failure")
        
        with pytest.raises(RetryableError):
            retryable_error_function()
    
    def test_handle_sqs_processing_errors_processing_error(self):
        """Test error handling decorator with processing error."""
        @handle_sqs_processing_errors
        def processing_error_function():
            raise ProcessingError("Processing failed")
        
        result = processing_error_function()
        
        assert result['statusCode'] == 400
        assert 'Processing failed' in result['error']
        assert result['retryable'] is False
    
    def test_handle_sqs_processing_errors_unexpected_error(self):
        """Test error handling decorator with unexpected error."""
        @handle_sqs_processing_errors
        def unexpected_error_function():
            raise ValueError("Unexpected error")
        
        with pytest.raises(ValueError):
            unexpected_error_function()


class TestIntegration:
    """Integration tests for SQS processor."""
    
    def test_end_to_end_processing(self):
        """Test complete end-to-end message processing."""
        # Create a mock message handler
        processed_messages = []
        
        def mock_handler(s3_message: S3EventMessage):
            processed_messages.append(s3_message)
        
        # Create processor
        processor = SQSBatchProcessor(mock_handler)
        
        # Create test event
        test_event = {
            'Records': [
                {
                    'messageId': 'test-msg-1',
                    'receiptHandle': 'receipt-1',
                    'body': json.dumps({
                        'bucket_name': 'test-bucket',
                        'object_key': 'OPP123/opportunity.json',
                        'event_name': 's3:ObjectCreated:Put',
                        'event_time': '2024-01-01T12:00:00Z',
                        'object_size': 1024,
                        'etag': 'test-etag',
                        'opportunity_number': 'OPP123'
                    }),
                    'attributes': {'ApproximateReceiveCount': '1'}
                }
            ]
        }
        
        with patch('src.shared.sqs_processor.sqs_handler') as mock_sqs_handler:
            mock_sqs_handler.parse_s3_event_message.return_value = S3EventMessage(
                bucket_name='test-bucket',
                object_key='OPP123/opportunity.json',
                event_name='s3:ObjectCreated:Put',
                event_time='2024-01-01T12:00:00Z',
                object_size=1024,
                etag='test-etag',
                opportunity_number='OPP123'
            )
            
            # Process the event
            result = processor.process_lambda_event(test_event, None)
        
        # Verify processing results
        assert result['statusCode'] == 200
        assert result['successfulMessages'] == 1
        assert len(processed_messages) == 1
        
        # Verify the processed message
        processed_message = processed_messages[0]
        assert processed_message.bucket_name == 'test-bucket'
        assert processed_message.opportunity_number == 'OPP123'