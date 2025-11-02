"""
Unit tests for SAM JSON processor Lambda function.
Tests JSON parsing, opportunity extraction, file downloading, and error handling.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
from botocore.exceptions import ClientError
import requests
from requests.exceptions import RequestException, Timeout, HTTPError

# Mock the shared modules before importing handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

# Mock shared modules
mock_logger = Mock()
mock_logger.correlation_id = 'test-correlation-id'

mock_error_handling = Mock()
mock_error_handling.RetryableError = type('RetryableError', (Exception,), {
    '__init__': lambda self, message, error_type: setattr(self, 'error_type', error_type) or Exception.__init__(self, message)
})
mock_error_handling.NonRetryableError = type('NonRetryableError', (Exception,), {
    '__init__': lambda self, message, error_type: setattr(self, 'error_type', error_type) or Exception.__init__(self, message)
})
mock_error_handling.ErrorType = Mock()
mock_error_handling.ErrorType.DATA_ERROR = 'data_error'
mock_error_handling.ErrorType.SYSTEM_ERROR = 'system_error'
mock_error_handling.handle_lambda_error = lambda func: func

mock_aws_clients = Mock()
mock_aws_clients.s3 = Mock()

mock_config = Mock()
mock_config.s3.sam_extracted_json_resources = 'test-output-bucket'
mock_config.processing.max_concurrent_downloads = 5

# Patch the modules before importing handler
with patch.dict('sys.modules', {
    'shared.logging_config': Mock(get_logger=lambda name: mock_logger),
    'shared.error_handling': mock_error_handling,
    'shared.aws_clients': Mock(aws_clients=mock_aws_clients),
    'shared.config': Mock(config=mock_config)
}):
    from handler import OpportunityProcessor, lambda_handler

# Import the error classes for use in tests
RetryableError = mock_error_handling.RetryableError
NonRetryableError = mock_error_handling.NonRetryableError
ErrorType = mock_error_handling.ErrorType


class TestOpportunityProcessor:
    """Test cases for OpportunityProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create OpportunityProcessor instance for testing."""
        with patch('handler.aws_clients') as mock_clients, \
             patch('handler.config') as mock_config:
            
            mock_config.s3.sam_extracted_json_resources = 'test-output-bucket'
            mock_config.processing.max_concurrent_downloads = 5
            
            processor = OpportunityProcessor()
            processor.s3_client = Mock()
            return processor
    
    @pytest.fixture
    def sample_opportunity(self):
        """Sample opportunity data for testing."""
        return {
            'opportunity_id': 'TEST-001',
            'solicitation_number': 'SOL-123',
            'title': 'Test Opportunity',
            'description': 'Test description',
            'posted_date': '2024-01-01T00:00:00Z',
            'response_deadline': '2024-02-01T00:00:00Z',
            'naics_codes': ['541511'],
            'resource_links': [
                'https://example.com/file1.pdf',
                'https://example.com/file2.doc'
            ]
        }
    
    @pytest.fixture
    def sample_sam_data(self, sample_opportunity):
        """Sample SAM.gov API response data."""
        return {
            'opportunitiesData': [
                sample_opportunity,
                {
                    'opportunity_id': 'TEST-002',
                    'solicitation_number': 'SOL-456',
                    'title': 'Another Test Opportunity',
                    'description': 'Another test description',
                    'resource_links': []
                }
            ]
        }


class TestJSONParsingAndOpportunityExtraction:
    """Test JSON parsing and opportunity extraction functionality."""
    
    def test_extract_opportunities_with_opportunities_data_key(self, processor, sample_sam_data):
        """Test extracting opportunities from JSON with 'opportunitiesData' key."""
        opportunities = processor._extract_opportunities(sample_sam_data)
        
        assert len(opportunities) == 2
        assert opportunities[0]['opportunity_id'] == 'TEST-001'
        assert opportunities[1]['opportunity_id'] == 'TEST-002'
    
    def test_extract_opportunities_with_opportunities_key(self, processor):
        """Test extracting opportunities from JSON with 'opportunities' key."""
        sam_data = {
            'opportunities': [
                {'opportunity_id': 'TEST-001', 'title': 'Test 1'},
                {'opportunity_id': 'TEST-002', 'title': 'Test 2'}
            ]
        }
        
        opportunities = processor._extract_opportunities(sam_data)
        
        assert len(opportunities) == 2
        assert opportunities[0]['opportunity_id'] == 'TEST-001'
    
    def test_extract_opportunities_from_list(self, processor):
        """Test extracting opportunities when root is a list."""
        sam_data = [
            {'opportunity_id': 'TEST-001', 'title': 'Test 1'},
            {'opportunity_id': 'TEST-002', 'title': 'Test 2'}
        ]
        
        opportunities = processor._extract_opportunities(sam_data)
        
        assert len(opportunities) == 2
        assert opportunities[0]['opportunity_id'] == 'TEST-001'
    
    def test_extract_opportunities_from_nested_structure(self, processor):
        """Test extracting opportunities from nested JSON structure."""
        sam_data = {
            'response': {
                'data': [
                    {'solicitation_number': 'SOL-001', 'title': 'Test 1'},
                    {'solicitation_number': 'SOL-002', 'title': 'Test 2'}
                ]
            }
        }
        
        opportunities = processor._extract_opportunities(sam_data)
        
        assert len(opportunities) == 2
        assert opportunities[0]['solicitation_number'] == 'SOL-001'
    
    def test_extract_opportunities_empty_data(self, processor):
        """Test extracting opportunities from empty data."""
        opportunities = processor._extract_opportunities({})
        assert len(opportunities) == 0
        
        opportunities = processor._extract_opportunities({'other_data': 'value'})
        assert len(opportunities) == 0
    
    def test_get_opportunity_number_various_fields(self, processor):
        """Test getting opportunity number from different field names."""
        # Test opportunity_number field
        opp1 = {'opportunity_number': 'OPP-001'}
        assert processor._get_opportunity_number(opp1) == 'OPP-001'
        
        # Test solicitation_number field
        opp2 = {'solicitation_number': 'SOL-002'}
        assert processor._get_opportunity_number(opp2) == 'SOL-002'
        
        # Test opportunity_id field
        opp3 = {'opportunity_id': 'ID-003'}
        assert processor._get_opportunity_number(opp3) == 'ID-003'
        
        # Test solicitationNumber field
        opp4 = {'solicitationNumber': 'SOLNUM-004'}
        assert processor._get_opportunity_number(opp4) == 'SOLNUM-004'
    
    def test_get_opportunity_number_missing_fields(self, processor):
        """Test getting opportunity number when fields are missing."""
        opp_empty = {}
        assert processor._get_opportunity_number(opp_empty) is None
        
        opp_none = {'opportunity_number': None}
        assert processor._get_opportunity_number(opp_none) is None
        
        opp_empty_string = {'opportunity_number': ''}
        assert processor._get_opportunity_number(opp_empty_string) is None
    
    def test_get_opportunity_number_whitespace_handling(self, processor):
        """Test opportunity number extraction handles whitespace."""
        opp = {'opportunity_number': '  OPP-001  '}
        assert processor._get_opportunity_number(opp) == 'OPP-001'
    
    def test_get_opportunity_number_url_decoding(self, processor):
        """Test opportunity number extraction handles URL encoding."""
        # Test URL encoded parentheses
        opp1 = {'opportunity_number': '1PR2142%28RLP%29'}
        assert processor._get_opportunity_number(opp1) == '1PR2142_RLP_'
        
        # Test other special characters
        opp2 = {'opportunity_number': 'TEST%20SPACE%26AMPERSAND'}
        assert processor._get_opportunity_number(opp2) == 'TEST_SPACE_AMPERSAND'
        
        # Test mixed case
        opp3 = {'opportunity_number': 'SOL%2D123%2ETEST'}
        assert processor._get_opportunity_number(opp3) == 'SOL-123.TEST'
    
    def test_process_sam_json_file_success(self, processor, sample_sam_data):
        """Test successful processing of SAM JSON file."""
        # Mock S3 get_object response
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = json.dumps(sample_sam_data).encode('utf-8')
        processor.s3_client.get_object.return_value = mock_response
        
        # Mock the opportunity processing
        with patch.object(processor, '_process_single_opportunity') as mock_process:
            result = processor._process_sam_json_file('test-bucket', 'test-key.json')
        
        assert result['source_file'] == 'test-key.json'
        assert result['opportunities_found'] == 2
        assert result['opportunities_processed'] == 2
        assert mock_process.call_count == 2
    
    def test_process_sam_json_file_invalid_json(self, processor):
        """Test processing file with invalid JSON."""
        # Mock S3 get_object response with invalid JSON
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = b'invalid json content'
        processor.s3_client.get_object.return_value = mock_response
        
        with pytest.raises(NonRetryableError) as exc_info:
            processor._process_sam_json_file('test-bucket', 'test-key.json')
        
        assert exc_info.value.error_type == ErrorType.DATA_ERROR
        assert 'Invalid JSON' in str(exc_info.value)
    
    def test_process_sam_json_file_s3_error(self, processor):
        """Test processing file with S3 error."""
        # Mock S3 get_object to raise an exception
        processor.s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )
        
        with pytest.raises(RetryableError) as exc_info:
            processor._process_sam_json_file('test-bucket', 'test-key.json')
        
        assert exc_info.value.error_type == ErrorType.SYSTEM_ERROR


class TestFileDownloading:
    """Test file downloading functionality with mocked HTTP responses."""
    
    @pytest.fixture
    def processor(self):
        """Create processor with mocked dependencies."""
        with patch('handler.aws_clients') as mock_clients, \
             patch('handler.config') as mock_config:
            
            mock_config.s3.sam_extracted_json_resources = 'test-output-bucket'
            mock_config.processing.max_concurrent_downloads = 2
            
            processor = OpportunityProcessor()
            processor.s3_client = Mock()
            return processor
    
    @patch('handler.requests.get')
    def test_download_single_resource_success(self, mock_get, processor):
        """Test successful download of a single resource file."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.content = b'file content'
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = processor._download_single_resource(
            'https://example.com/document.pdf',
            'OPP-001',
            'OPP-001/'
        )
        
        assert result is True
        mock_get.assert_called_once_with('https://example.com/document.pdf', timeout=30, stream=True)
        processor.s3_client.put_object.assert_called_once_with(
            Bucket='test-output-bucket',
            Key='OPP-001/OPP-001_document.pdf',
            Body=b'file content',
            ContentType='application/pdf'
        )
    
    @patch('handler.requests.get')
    def test_download_single_resource_http_error(self, mock_get, processor):
        """Test download with HTTP error."""
        # Mock HTTP error
        mock_get.side_effect = HTTPError('404 Not Found')
        
        result = processor._download_single_resource(
            'https://example.com/missing.pdf',
            'OPP-001',
            'OPP-001/'
        )
        
        assert result is False
        processor.s3_client.put_object.assert_not_called()
    
    @patch('handler.requests.get')
    def test_download_single_resource_timeout(self, mock_get, processor):
        """Test download with timeout error."""
        # Mock timeout error
        mock_get.side_effect = Timeout('Request timed out')
        
        result = processor._download_single_resource(
            'https://example.com/slow.pdf',
            'OPP-001',
            'OPP-001/'
        )
        
        assert result is False
        processor.s3_client.put_object.assert_not_called()
    
    @patch('handler.requests.get')
    def test_download_single_resource_s3_error(self, mock_get, processor):
        """Test download with S3 upload error."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.content = b'file content'
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Mock S3 put_object error
        processor.s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )
        
        result = processor._download_single_resource(
            'https://example.com/document.pdf',
            'OPP-001',
            'OPP-001/'
        )
        
        assert result is False
    
    @patch('handler.requests.get')
    def test_download_single_resource_filename_handling(self, mock_get, processor):
        """Test filename extraction and prefixing."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.content = b'file content'
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test URL without filename
        result = processor._download_single_resource(
            'https://example.com/',
            'OPP-001',
            'OPP-001/'
        )
        
        assert result is True
        processor.s3_client.put_object.assert_called_with(
            Bucket='test-output-bucket',
            Key='OPP-001/OPP-001_resource_file',
            Body=b'file content',
            ContentType='application/pdf'
        )
    
    def test_download_resource_files_multiple_files(self, processor):
        """Test downloading multiple resource files concurrently."""
        resource_links = [
            'https://example.com/file1.pdf',
            'https://example.com/file2.doc',
            'https://example.com/file3.txt'
        ]
        
        with patch.object(processor, '_download_single_resource') as mock_download:
            mock_download.return_value = True
            
            processor._download_resource_files(resource_links, 'OPP-001', 'OPP-001/')
            
            assert mock_download.call_count == 3
            expected_calls = [
                call('https://example.com/file1.pdf', 'OPP-001', 'OPP-001/'),
                call('https://example.com/file2.doc', 'OPP-001', 'OPP-001/'),
                call('https://example.com/file3.txt', 'OPP-001', 'OPP-001/')
            ]
            mock_download.assert_has_calls(expected_calls, any_order=True)
    
    def test_download_resource_files_empty_list(self, processor):
        """Test downloading with empty resource links list."""
        with patch.object(processor, '_download_single_resource') as mock_download:
            processor._download_resource_files([], 'OPP-001', 'OPP-001/')
            mock_download.assert_not_called()
    
    def test_download_resource_files_partial_failures(self, processor):
        """Test downloading with some failures."""
        resource_links = [
            'https://example.com/file1.pdf',
            'https://example.com/file2.doc'
        ]
        
        with patch.object(processor, '_download_single_resource') as mock_download:
            # First download succeeds, second fails
            mock_download.side_effect = [True, False]
            
            processor._download_resource_files(resource_links, 'OPP-001', 'OPP-001/')
            
            assert mock_download.call_count == 2


class TestErrorHandling:
    """Test error handling for malformed data and various failure scenarios."""
    
    @pytest.fixture
    def processor(self):
        """Create processor with mocked dependencies."""
        with patch('handler.aws_clients') as mock_clients, \
             patch('handler.config') as mock_config:
            
            mock_config.s3.sam_extracted_json_resources = 'test-output-bucket'
            mock_config.processing.max_concurrent_downloads = 5
            
            processor = OpportunityProcessor()
            processor.s3_client = Mock()
            return processor
    
    def test_process_single_opportunity_missing_identifier(self, processor):
        """Test processing opportunity without required identifier."""
        opportunity = {
            'title': 'Test Opportunity',
            'description': 'Test description'
            # Missing opportunity_number, solicitation_number, etc.
        }
        
        with pytest.raises(NonRetryableError) as exc_info:
            processor._process_single_opportunity(opportunity)
        
        assert exc_info.value.error_type == ErrorType.DATA_ERROR
        assert 'missing required identifier' in str(exc_info.value)
    
    def test_process_single_opportunity_s3_store_error(self, processor):
        """Test processing opportunity with S3 storage error."""
        opportunity = {
            'opportunity_number': 'OPP-001',
            'title': 'Test Opportunity'
        }
        
        # Mock S3 put_object to raise an error
        processor.s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )
        
        with pytest.raises(RetryableError) as exc_info:
            processor._process_single_opportunity(opportunity)
        
        assert exc_info.value.error_type == ErrorType.SYSTEM_ERROR
    
    def test_store_opportunity_json_success(self, processor):
        """Test successful storage of opportunity JSON."""
        opportunity = {
            'opportunity_number': 'OPP-001',
            'title': 'Test Opportunity'
        }
        
        processor._store_opportunity_json(opportunity, '2024-01-15/OPP-001/OPP-001_opportunity.json')
        
        processor.s3_client.put_object.assert_called_once()
        call_args = processor.s3_client.put_object.call_args
        
        assert call_args[1]['Bucket'] == 'test-output-bucket'
        assert call_args[1]['Key'] == '2024-01-15/OPP-001/OPP-001_opportunity.json'
        assert call_args[1]['ContentType'] == 'application/json'
        
        # Verify JSON content
        body_content = call_args[1]['Body']
        parsed_json = json.loads(body_content)
        assert parsed_json['opportunity_number'] == 'OPP-001'
        assert parsed_json['title'] == 'Test Opportunity'
    
    def test_process_s3_event_invalid_record(self, processor):
        """Test processing S3 event with invalid record structure."""
        event = {
            'Records': [
                {
                    # Missing s3 key
                    'eventName': 'ObjectCreated:Put'
                },
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        # Missing object key
                    }
                }
            ]
        }
        
        result = processor.process_s3_event(event)
        
        assert result['processed_files'] == 0
        assert len(result['errors']) == 0  # Invalid records are logged but not counted as errors
    
    def test_process_s3_event_processing_errors(self, processor):
        """Test S3 event processing with file processing errors."""
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'test-file.json'}
                    }
                }
            ]
        }
        
        # Mock _process_sam_json_file to raise an exception
        with patch.object(processor, '_process_sam_json_file') as mock_process:
            mock_process.side_effect = Exception('Processing failed')
            
            result = processor.process_s3_event(event)
        
        assert result['processed_files'] == 0
        assert len(result['errors']) == 1
        assert 'Processing failed' in result['errors'][0]
    
    def test_process_single_opportunity_continue_on_resource_error(self, processor):
        """Test that opportunity processing continues when resource download fails."""
        opportunity = {
            'opportunity_number': 'OPP-001',
            'title': 'Test Opportunity',
            'resource_links': ['https://example.com/file.pdf']
        }
        
        # Mock successful JSON storage but failed resource download
        with patch.object(processor, '_download_resource_files') as mock_download:
            mock_download.side_effect = Exception('Download failed')
            
            # Should not raise exception - resource download errors are handled gracefully
            processor._process_single_opportunity(opportunity)
        
        # Verify opportunity JSON was still stored
        processor.s3_client.put_object.assert_called_once()


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    @patch('handler.OpportunityProcessor')
    def test_lambda_handler_success(self, mock_processor_class):
        """Test successful Lambda handler execution."""
        # Mock processor instance and result
        mock_processor = Mock()
        mock_processor.process_s3_event.return_value = {
            'processed_files': 1,
            'total_opportunities': 5,
            'errors': []
        }
        mock_processor_class.return_value = mock_processor
        
        event = {'Records': []}
        context = Mock()
        
        with patch('handler.logger') as mock_logger:
            mock_logger.correlation_id = 'test-correlation-id'
            
            result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['message'] == 'SAM JSON processing completed successfully'
        assert body['result']['processed_files'] == 1
        assert body['correlation_id'] == 'test-correlation-id'
    
    @patch('handler.OpportunityProcessor')
    def test_lambda_handler_error(self, mock_processor_class):
        """Test Lambda handler with processing error."""
        # Mock processor to raise an exception
        mock_processor = Mock()
        mock_processor.process_s3_event.side_effect = Exception('Processing failed')
        mock_processor_class.return_value = mock_processor
        
        event = {'Records': []}
        context = Mock()
        
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, context)
        
        assert 'Processing failed' in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])