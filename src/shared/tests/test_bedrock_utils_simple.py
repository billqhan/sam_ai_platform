"""
Simple unit tests for Bedrock utilities without complex mocking.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Test the utility functions without creating actual AWS clients
def test_truncate_text():
    """Test text truncation functionality."""
    from src.shared.bedrock_utils import BedrockClient
    
    # Create a mock client without initializing AWS clients
    with patch('src.shared.bedrock_utils.aws_clients'):
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.model_id_desc = 'test-model'
            mock_config.bedrock.model_id_match = 'test-model'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            
            client = BedrockClient()
            
            # Test no truncation needed
            text = "Short text"
            result = client._truncate_text(text, 100)
            assert result == text
            
            # Test truncation needed
            text = "This is a very long text that needs to be truncated"
            result = client._truncate_text(text, 20)
            assert len(result) <= 35  # 20 + "... [truncated]"
            assert result.endswith("... [truncated]")

def test_bedrock_client_initialization():
    """Test BedrockClient initialization with mocked dependencies."""
    with patch('src.shared.bedrock_utils.aws_clients') as mock_aws_clients:
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.model_id_desc = 'test-model-desc'
            mock_config.bedrock.model_id_match = 'test-model-match'
            mock_config.processing.process_delay_seconds = 60
            mock_config.processing.max_description_chars = 20000
            mock_config.processing.max_attachment_chars = 16000
            
            mock_aws_clients.bedrock = Mock()
            mock_aws_clients.bedrock_agent_runtime = Mock()
            
            from src.shared.bedrock_utils import BedrockClient
            client = BedrockClient()
            
            assert client.model_id_desc == 'test-model-desc'
            assert client.model_id_match == 'test-model-match'
            assert client.process_delay_seconds == 60
            assert client.max_description_chars == 20000
            assert client.max_attachment_chars == 16000

def test_extract_opportunity_info_structure():
    """Test that extract_opportunity_info creates proper prompt structure."""
    with patch('src.shared.bedrock_utils.aws_clients') as mock_aws_clients:
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.model_id_desc = 'test-model'
            mock_config.bedrock.model_id_match = 'test-model'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            
            mock_aws_clients.bedrock = Mock()
            mock_aws_clients.bedrock_agent_runtime = Mock()
            
            from src.shared.bedrock_utils import BedrockClient
            client = BedrockClient()
            
            # Mock the invoke_llm_model method
            with patch.object(client, 'invoke_llm_model') as mock_invoke:
                mock_invoke.return_value = 'Extracted info'
                
                opportunity_data = {
                    'title': 'Test Opportunity',
                    'description': 'Test description'
                }
                attachments = ['Attachment 1', 'Attachment 2']
                
                result = client.extract_opportunity_info(opportunity_data, attachments)
                
                assert result == 'Extracted info'
                mock_invoke.assert_called_once()
                
                # Check that the prompt contains expected elements
                call_args = mock_invoke.call_args[0]
                model_id = call_args[0]
                prompt = call_args[1]
                
                assert model_id == 'test-model'
                assert 'Test Opportunity' in prompt
                assert 'Test description' in prompt
                assert 'Attachment 1' in prompt

def test_calculate_company_match_structure():
    """Test that calculate_company_match handles the flow correctly."""
    with patch('src.shared.bedrock_utils.aws_clients') as mock_aws_clients:
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.model_id_desc = 'test-model-desc'
            mock_config.bedrock.model_id_match = 'test-model-match'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            
            mock_aws_clients.bedrock = Mock()
            mock_aws_clients.bedrock_agent_runtime = Mock()
            
            from src.shared.bedrock_utils import BedrockClient
            client = BedrockClient()
            
            # Mock S3 vector results
            s3_results = [
                {
                    'content': 'Company capability 1',
                    'score': 0.9,
                    'metadata': {},
                    'location': {'s3Location': {'uri': 's3://bucket/company-info.json'}}
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
            
            with patch.object(client, 'query_s3_vectors') as mock_s3:
                with patch.object(client, 'invoke_llm_model') as mock_llm:
                    mock_s3.return_value = s3_results
                    mock_llm.return_value = llm_response
                    
                    result = client.calculate_company_match(
                        'Test opportunity info', 
                        {'title': 'Test Opportunity'}
                    )
                    
                    assert result['match_score'] == 0.8
                    assert result['is_match'] is True
                    assert result['rationale'] == 'Good match based on capabilities'
                    assert len(result['citations']) == 1
                    assert result['citations'][0]['document_title'] == 's3://bucket/company-info.json'

def test_get_bedrock_client_lazy_initialization():
    """Test lazy initialization of global client."""
    with patch('src.shared.bedrock_utils.aws_clients') as mock_aws_clients:
        with patch('src.shared.bedrock_utils.config') as mock_config:
            mock_config.bedrock.model_id_desc = 'test-model'
            mock_config.bedrock.model_id_match = 'test-model'
            mock_config.processing.process_delay_seconds = 1
            mock_config.processing.max_description_chars = 1000
            mock_config.processing.max_attachment_chars = 500
            
            mock_aws_clients.bedrock = Mock()
            mock_aws_clients.bedrock_agent_runtime = Mock()
            
            # Reset global client
            import src.shared.bedrock_utils
            src.shared.bedrock_utils._bedrock_client = None
            
            from src.shared.bedrock_utils import get_bedrock_client, BedrockClient
            
            client = get_bedrock_client()
            assert client is not None
            assert isinstance(client, BedrockClient)
            
            # Second call should return same instance
            client2 = get_bedrock_client()
            assert client is client2