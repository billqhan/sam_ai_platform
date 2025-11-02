"""
Unit tests for Bedrock utilities.
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from ..bedrock_utils import BedrockClient, get_bedrock_client


class TestBedrockClient:
    """Test cases for BedrockClient."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.knowledge_base_id = 'test-kb-id'
            mock_config.bedrock.model_id_desc = 'test-model-desc'
            mock_config.bedrock.model_id_match = 'test-model-match'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            yield mock_config
    
    @pytest.fixture
    def mock_aws_clients(self):
        """Mock AWS clients."""
        with patch('src.shared.bedrock_utils.aws_clients') as mock_clients:
            mock_clients.bedrock = Mock()
            mock_clients.bedrock_agent_runtime = Mock()
            yield mock_clients
    
    @pytest.fixture
    def bedrock_client_instance(self, mock_config, mock_aws_clients):
        """Create BedrockClient instance with mocked dependencies."""
        with patch('src.shared.bedrock_utils.aws_clients', mock_aws_clients):
            return BedrockClient()
    
    def test_init(self, bedrock_client_instance, mock_config):
        """Test BedrockClient initialization."""
        assert bedrock_client_instance.knowledge_base_id == 'test-kb-id'
        assert bedrock_client_instance.model_id_desc == 'test-model-desc'
        assert bedrock_client_instance.model_id_match == 'test-model-match'
        assert bedrock_client_instance.process_delay_seconds == 1
        assert bedrock_client_instance.max_description_chars == 1000
        assert bedrock_client_instance.max_attachment_chars == 500
    
    def test_truncate_text_no_truncation_needed(self, bedrock_client_instance):
        """Test text truncation when no truncation is needed."""
        text = "Short text"
        result = bedrock_client_instance._truncate_text(text, 100)
        assert result == text
    
    def test_truncate_text_with_truncation(self, bedrock_client_instance):
        """Test text truncation when truncation is needed."""
        text = "This is a very long text that needs to be truncated"
        result = bedrock_client_instance._truncate_text(text, 20)
        assert len(result) <= 35  # 20 + "... [truncated]"
        assert result.endswith("... [truncated]")
    
    def test_truncate_text_word_boundary(self, bedrock_client_instance):
        """Test text truncation at word boundary."""
        text = "This is a test sentence with multiple words"
        result = bedrock_client_instance._truncate_text(text, 15)
        assert result.endswith("... [truncated]")
        # Should truncate at word boundary if possible
        assert not result.replace("... [truncated]", "").endswith(" ")
    
    @patch('time.sleep')
    @patch('time.time')
    def test_apply_rate_limiting(self, mock_time, mock_sleep, bedrock_client_instance):
        """Test rate limiting functionality."""
        # First call - no delay needed
        mock_time.return_value = 100
        bedrock_client_instance._last_request_time = 0
        bedrock_client_instance._apply_rate_limiting()
        mock_sleep.assert_not_called()
        
        # Second call - delay needed
        mock_time.return_value = 100.5  # 0.5 seconds later
        bedrock_client_instance._apply_rate_limiting()
        mock_sleep.assert_called_once_with(0.5)  # Should sleep for remaining time
    
    def test_invoke_llm_model_claude_success(self, bedrock_client_instance):
        """Test successful Claude model invocation."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Test response'}]
        }).encode()
        
        bedrock_client_instance.bedrock_runtime.invoke_model.return_value = mock_response
        
        with patch.object(bedrock_client_instance, '_apply_rate_limiting'):
            result = bedrock_client_instance.invoke_llm_model(
                'anthropic.claude-3-sonnet', 
                'Test prompt'
            )
        
        assert result == 'Test response'
        bedrock_client_instance.bedrock_runtime.invoke_model.assert_called_once()
    
    def test_invoke_llm_model_generic_success(self, bedrock_client_instance):
        """Test successful generic model invocation."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'results': [{'outputText': 'Generic response'}]
        }).encode()
        
        bedrock_client_instance.bedrock_runtime.invoke_model.return_value = mock_response
        
        with patch.object(bedrock_client_instance, '_apply_rate_limiting'):
            result = bedrock_client_instance.invoke_llm_model(
                'generic-model', 
                'Test prompt'
            )
        
        assert result == 'Generic response'
    
    def test_invoke_llm_model_throttling_exception(self, bedrock_client_instance):
        """Test handling of throttling exception."""
        error = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'InvokeModel'
        )
        bedrock_client_instance.bedrock_runtime.invoke_model.side_effect = error
        
        with patch.object(bedrock_client_instance, '_apply_rate_limiting'):
            with patch('time.sleep') as mock_sleep:
                with pytest.raises(ClientError):
                    bedrock_client_instance.invoke_llm_model('test-model', 'Test prompt')
                
                mock_sleep.assert_called_once_with(2)  # 2 * process_delay_seconds
    
    def test_extract_opportunity_info(self, bedrock_client_instance):
        """Test opportunity information extraction."""
        opportunity_data = {
            'title': 'Test Opportunity',
            'description': 'Test description'
        }
        attachments = ['Attachment content 1', 'Attachment content 2']
        
        with patch.object(bedrock_client_instance, 'invoke_llm_model') as mock_invoke:
            mock_invoke.return_value = 'Extracted info'
            
            result = bedrock_client_instance.extract_opportunity_info(
                opportunity_data, 
                attachments
            )
        
        assert result == 'Extracted info'
        mock_invoke.assert_called_once()
        
        # Check that the prompt contains expected elements
        call_args = mock_invoke.call_args[0]
        prompt = call_args[1]
        assert 'Test Opportunity' in prompt
        assert 'Test description' in prompt
        assert 'Attachment content 1' in prompt
    
    def test_extract_opportunity_info_error_handling(self, bedrock_client_instance):
        """Test error handling in opportunity information extraction."""
        opportunity_data = {'title': 'Test', 'description': 'Test'}
        
        with patch.object(bedrock_client_instance, 'invoke_llm_model') as mock_invoke:
            mock_invoke.side_effect = Exception('Test error')
            
            result = bedrock_client_instance.extract_opportunity_info(opportunity_data)
        
        assert 'Error extracting opportunity information' in result
        assert 'Test error' in result
    
    def test_query_s3_vectors_success(self, bedrock_client_instance):
        """Test successful S3 vector query."""
        mock_results = [
            {
                'content': 'Result 1',
                'score': 0.9,
                'metadata': {'key': 'value'},
                'location': {'s3Location': {'uri': 's3://bucket/doc1.json'}}
            },
            {
                'content': 'Result 2',
                'score': 0.8,
                'metadata': {},
                'location': {'s3Location': {'uri': 's3://bucket/doc2.json'}}
            }
        ]
        
        with patch.object(bedrock_client_instance, '_generate_embedding') as mock_embed:
            with patch.object(bedrock_client_instance, '_search_similar_vectors') as mock_search:
                mock_embed.return_value = [0.1, 0.2, 0.3]
                mock_search.return_value = mock_results
                
                results = bedrock_client_instance.query_s3_vectors('test query')
                
                assert len(results) == 2
                assert results[0]['content'] == 'Result 1'
                assert results[0]['score'] == 0.9
                assert results[1]['content'] == 'Result 2'
                assert results[1]['score'] == 0.8
    
    def test_query_s3_vectors_no_embedding(self, bedrock_client_instance):
        """Test S3 vector query with embedding generation failure."""
        with patch.object(bedrock_client_instance, '_generate_embedding') as mock_embed:
            mock_embed.return_value = None
            
            results = bedrock_client_instance.query_s3_vectors('test query')
            
            assert results == []
    
    def test_generate_embedding_success(self, bedrock_client_instance):
        """Test successful embedding generation."""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'embedding': [0.1, 0.2, 0.3, 0.4]
        }).encode()
        
        bedrock_client_instance.bedrock_runtime.invoke_model.return_value = mock_response
        
        embedding = bedrock_client_instance._generate_embedding('test text')
        
        assert embedding == [0.1, 0.2, 0.3, 0.4]
    
    def test_calculate_similarity(self, bedrock_client_instance):
        """Test similarity calculation."""
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]
        
        similarity = bedrock_client_instance._calculate_similarity(embedding1, embedding2)
        
        assert similarity == 1.0  # Perfect similarity
        
        embedding3 = [0.0, 1.0, 0.0]
        similarity2 = bedrock_client_instance._calculate_similarity(embedding1, embedding3)
        
        assert similarity2 == 0.0  # No similarity
    
    def test_calculate_company_match_success(self, bedrock_client_instance):
        """Test successful company match calculation."""
        opportunity_info = "Test opportunity info"
        opportunity_data = {'title': 'Test Opportunity'}
        
        # Mock knowledge base results
        kb_results = [
            {
                'content': 'Company capability 1',
                'score': 0.9,
                'metadata': {},
                'location': {'s3Location': {'uri': 'company-info.pdf'}}
            }
        ]
        
        # Mock LLM response
        llm_response = json.dumps({
            'match_score': 0.8,
            'is_match': True,
            'rationale': 'Good match based on capabilities',
            'opportunity_required_skills': ['skill1', 'skill2'],
            'company_skills': ['skill1', 'skill3'],
            'past_performance': ['project1']
        })
        
        with patch.object(bedrock_client_instance, 'query_knowledge_base') as mock_kb:
            with patch.object(bedrock_client_instance, 'invoke_llm_model') as mock_llm:
                mock_kb.return_value = kb_results
                mock_llm.return_value = llm_response
                
                result = bedrock_client_instance.calculate_company_match(
                    opportunity_info, 
                    opportunity_data
                )
        
        assert result['match_score'] == 0.8
        assert result['is_match'] is True
        assert result['rationale'] == 'Good match based on capabilities'
        assert len(result['citations']) == 1
        assert result['citations'][0]['document_title'] == 'company-info.pdf'
    
    def test_calculate_company_match_no_kb_results(self, bedrock_client_instance):
        """Test company match calculation with no knowledge base results."""
        opportunity_info = "Test opportunity info"
        opportunity_data = {'title': 'Test Opportunity'}
        
        with patch.object(bedrock_client_instance, 'query_knowledge_base') as mock_kb:
            mock_kb.return_value = []
            
            result = bedrock_client_instance.calculate_company_match(
                opportunity_info, 
                opportunity_data
            )
        
        assert result['match_score'] == 0.0
        assert result['is_match'] is False
        assert 'No relevant company information found' in result['rationale']
        assert result['citations'] == []
    
    def test_calculate_company_match_invalid_json_response(self, bedrock_client_instance):
        """Test company match calculation with invalid JSON response."""
        opportunity_info = "Test opportunity info"
        opportunity_data = {'title': 'Test Opportunity'}
        
        kb_results = [{'content': 'test', 'score': 0.9, 'metadata': {}, 'location': {}}]
        
        with patch.object(bedrock_client_instance, 'query_knowledge_base') as mock_kb:
            with patch.object(bedrock_client_instance, 'invoke_llm_model') as mock_llm:
                mock_kb.return_value = kb_results
                mock_llm.return_value = 'Invalid JSON response'
                
                result = bedrock_client_instance.calculate_company_match(
                    opportunity_info, 
                    opportunity_data
                )
        
        assert result['match_score'] == 0.5
        assert result['is_match'] is False
        assert 'Analysis completed but response format was invalid' in result['rationale']
    
    def test_calculate_company_match_llm_error(self, bedrock_client_instance):
        """Test company match calculation with LLM error."""
        opportunity_info = "Test opportunity info"
        opportunity_data = {'title': 'Test Opportunity'}
        
        kb_results = [{'content': 'test', 'score': 0.9, 'metadata': {}, 'location': {}}]
        
        with patch.object(bedrock_client_instance, 'query_knowledge_base') as mock_kb:
            with patch.object(bedrock_client_instance, 'invoke_llm_model') as mock_llm:
                mock_kb.return_value = kb_results
                mock_llm.side_effect = Exception('LLM error')
                
                result = bedrock_client_instance.calculate_company_match(
                    opportunity_info, 
                    opportunity_data
                )
        
        assert result['match_score'] == 0.0
        assert result['is_match'] is False
        assert 'Error during matching analysis' in result['rationale']


def test_global_bedrock_client_instance():
    """Test that global bedrock_client instance is created."""
    with patch('src.shared.bedrock_utils.config') as mock_config:
        with patch('src.shared.bedrock_utils.aws_clients') as mock_aws_clients:
            mock_config.bedrock.knowledge_base_id = 'test-kb-id'
            mock_config.bedrock.model_id_desc = 'test-model-desc'
            mock_config.bedrock.model_id_match = 'test-model-match'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            
            mock_aws_clients.bedrock = Mock()
            mock_aws_clients.bedrock_agent_runtime = Mock()
            
            # Reset the global client to ensure fresh instance
            import src.shared.bedrock_utils
            src.shared.bedrock_utils._bedrock_client = None
            
            client = get_bedrock_client()
            assert client is not None
            assert isinstance(client, BedrockClient)