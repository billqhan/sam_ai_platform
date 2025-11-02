"""
Test file for sam-sqs-generate-match-reports Lambda function.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the handler
from handler import lambda_handler, OpportunityMatchProcessor, process_single_message

class TestOpportunityMatchProcessor:
    """Test cases for OpportunityMatchProcessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = OpportunityMatchProcessor()
    
    @patch('handler.aws_clients')
    def test_download_opportunity_data(self, mock_aws_clients):
        """Test downloading opportunity data from S3."""
        # Mock S3 response
        mock_s3 = Mock()
        mock_aws_clients.s3 = mock_s3
        
        opportunity_data = {
            'opportunity_id': 'test-123',
            'title': 'Test Opportunity',
            'description': 'Test description'
        }
        
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = json.dumps(opportunity_data).encode('utf-8')
        mock_s3.get_object.return_value = mock_response
        
        # Create test S3 message
        from shared.sqs_utils import S3EventMessage
        s3_message = S3EventMessage(
            bucket_name='test-bucket',
            object_key='test/opportunity.json',
            event_name='s3:ObjectCreated:Put',
            event_time='2024-01-01T00:00:00Z'
        )
        
        # Test the method
        result = self.processor._download_opportunity_data(s3_message)
        
        assert result == opportunity_data
        mock_s3.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test/opportunity.json'
        )
    
    @patch('handler.aws_clients')
    def test_download_attachments_no_files(self, mock_aws_clients):
        """Test downloading attachments when no files exist."""
        # Mock S3 response with no objects
        mock_s3 = Mock()
        mock_aws_clients.s3 = mock_s3
        mock_s3.list_objects_v2.return_value = {'Contents': []}
        
        opportunity_data = {
            'opportunity_id': 'test-123',
            'resource_links': ['http://example.com/file1.pdf']
        }
        
        from shared.sqs_utils import S3EventMessage
        s3_message = S3EventMessage(
            bucket_name='test-bucket',
            object_key='test-123/opportunity.json',
            event_name='s3:ObjectCreated:Put',
            event_time='2024-01-01T00:00:00Z'
        )
        
        result = self.processor._download_attachments(opportunity_data, s3_message)
        
        assert result == []
    
    @patch('handler.get_bedrock_client')
    def test_extract_opportunity_info(self, mock_bedrock_client):
        """Test extracting opportunity information."""
        # Mock Bedrock client
        mock_client = Mock()
        mock_bedrock_client.return_value = mock_client
        mock_client.extract_opportunity_info.return_value = "Extracted opportunity info"
        
        opportunity_data = {
            'title': 'Test Opportunity',
            'description': 'Test description'
        }
        attachments = ['attachment content']
        
        result = self.processor._extract_opportunity_info(opportunity_data, attachments)
        
        assert result == "Extracted opportunity info"
        mock_client.extract_opportunity_info.assert_called_once_with(
            opportunity_data=opportunity_data,
            attachments=attachments
        )
    
    @patch('handler.get_bedrock_client')
    def test_calculate_company_match(self, mock_bedrock_client):
        """Test calculating company match."""
        # Mock Bedrock client
        mock_client = Mock()
        mock_bedrock_client.return_value = mock_client
        mock_client.calculate_company_match.return_value = {
            'match_score': 0.8,
            'is_match': True,
            'rationale': 'Good match',
            'citations': [],
            'opportunity_required_skills': ['skill1'],
            'company_skills': ['skill1', 'skill2'],
            'past_performance': ['project1']
        }
        
        opportunity_info = "Test opportunity info"
        opportunity_data = {
            'opportunity_id': 'test-123',
            'title': 'Test Opportunity',
            'solicitation_number': 'SOL-123'
        }
        
        result = self.processor._calculate_company_match(opportunity_info, opportunity_data)
        
        assert result['match_score'] == 0.8
        assert result['is_match'] == True
        assert 'processed_timestamp' in result
        assert 'solicitation_id' in result
        assert 'opportunity_summary' in result

class TestLambdaHandler:
    """Test cases for the Lambda handler."""
    
    @patch('handler.sqs_processor')
    @patch('handler.SQSMessageValidator')
    def test_lambda_handler_success(self, mock_validator, mock_sqs_processor):
        """Test successful Lambda handler execution."""
        # Mock event and context
        event = {
            'Records': [
                {
                    'messageId': 'test-message-1',
                    'body': json.dumps({
                        'Records': [
                            {
                                's3': {
                                    'bucket': {'name': 'test-bucket'},
                                    'object': {'key': 'test/opportunity.json'}
                                },
                                'eventName': 's3:ObjectCreated:Put',
                                'eventTime': '2024-01-01T00:00:00Z'
                            }
                        ]
                    }),
                    'receiptHandle': 'test-receipt-handle'
                }
            ]
        }
        
        context = Mock()
        context.function_name = 'test-function'
        context.aws_request_id = 'test-request-id'
        context.get_remaining_time_in_millis.return_value = 30000
        
        # Mock validator
        mock_validator.validate_lambda_sqs_event.return_value = True
        
        # Mock SQS processor
        mock_sqs_processor.process_lambda_event.return_value = {
            'statusCode': 200,
            'totalMessages': 1,
            'successfulMessages': 1,
            'failedMessages': 0
        }
        
        # Test the handler
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        assert result['totalMessages'] == 1
        assert result['successfulMessages'] == 1
        assert result['failedMessages'] == 0

if __name__ == '__main__':
    # Run basic tests
    print("Running basic tests...")
    
    # Test processor initialization
    processor = OpportunityMatchProcessor()
    print(f"✓ Processor initialized with debug_mode: {processor.debug_mode}")
    
    # Test configuration loading
    print(f"✓ Configuration loaded:")
    print(f"  - Match threshold: {processor.match_threshold}")
    print(f"  - Max attachment files: {processor.max_attachment_files}")
    print(f"  - Max description chars: {processor.max_description_chars}")
    print(f"  - Process delay seconds: {processor.process_delay_seconds}")
    
    print("Basic tests completed successfully!")