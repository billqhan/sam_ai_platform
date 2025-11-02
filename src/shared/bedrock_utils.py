"""
Bedrock AI client utilities for LLM model invocations and knowledge base queries.
"""
import json
import time
import logging
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError
from .aws_clients import aws_clients, handle_aws_error
from .config import config

logger = logging.getLogger(__name__)

class BedrockClient:
    """Client for Bedrock AI operations including LLM invocations and knowledge base queries."""
    
    def __init__(self, region_name: str = 'us-east-1'):
        self.region_name = region_name
        self.bedrock_runtime = aws_clients.bedrock
        self.bedrock_agent_runtime = aws_clients.bedrock_agent_runtime
        
        # Configuration from environment variables
        self.model_id_desc = config.bedrock.model_id_desc
        self.model_id_match = config.bedrock.model_id_match
        self.process_delay_seconds = config.processing.process_delay_seconds
        self.max_description_chars = config.processing.max_description_chars
        self.max_attachment_chars = config.processing.max_attachment_chars
        
        # Rate limiting
        self._last_request_time = 0
    
    def _apply_rate_limiting(self):
        """Apply rate limiting between requests to prevent throttling."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.process_delay_seconds:
            sleep_time = self.process_delay_seconds - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _truncate_text(self, text: str, max_chars: int) -> str:
        """Truncate text to maximum character limit."""
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        # Try to truncate at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.8:  # Only if we don't lose too much content
            truncated = truncated[:last_space]
        
        return truncated + "... [truncated]"
    
    @handle_aws_error
    def invoke_llm_model(self, model_id: str, prompt: str, max_tokens: int = 4000, temperature: float = 0.1) -> str:
        """
        Invoke a Bedrock LLM model with the given prompt.
        
        Args:
            model_id: The model ID to invoke
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in response
            temperature: Temperature for response generation
            
        Returns:
            The model's response text
        """
        self._apply_rate_limiting()
        
        # Prepare the request body based on model type
        if 'claude' in model_id.lower():
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        else:
            # Generic format for other models
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature
                }
            }
        
        try:
            logger.info(f"Invoking model {model_id} with prompt length: {len(prompt)}")
            
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            
            # Extract text based on model type
            if 'claude' in model_id.lower():
                if 'content' in response_body and len(response_body['content']) > 0:
                    return response_body['content'][0]['text']
                else:
                    logger.warning("Unexpected Claude response format")
                    return ""
            else:
                # Generic format
                return response_body.get('results', [{}])[0].get('outputText', '')
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ThrottlingException':
                logger.warning(f"Model invocation throttled, applying additional delay")
                time.sleep(self.process_delay_seconds * 2)
                raise
            else:
                logger.error(f"Model invocation failed: {error_code}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error during model invocation: {str(e)}")
            raise
    
    def extract_opportunity_info(self, opportunity_data: Dict[str, Any], attachments: List[str] = None) -> str:
        """
        Extract key information from opportunity using the description extraction model.
        
        Args:
            opportunity_data: The opportunity JSON data
            attachments: List of attachment content strings
            
        Returns:
            Extracted opportunity information
        """
        # Prepare the opportunity description
        description = opportunity_data.get('description', '')
        title = opportunity_data.get('title', '')
        
        # Truncate description if too long
        description = self._truncate_text(description, self.max_description_chars)
        
        # Prepare attachment content
        attachment_content = ""
        if attachments:
            # Limit number of attachments and total content
            limited_attachments = attachments[:4]  # MAX_ATTACHMENT_FILES
            combined_attachments = "\n\n".join(limited_attachments)
            attachment_content = self._truncate_text(combined_attachments, self.max_attachment_chars)
        
        # Create the prompt for opportunity information extraction
        prompt = f"""
You are an expert at analyzing government contracting opportunities. Please extract and summarize the key information from this opportunity.

OPPORTUNITY TITLE: {title}

OPPORTUNITY DESCRIPTION:
{description}

ATTACHMENT CONTENT:
{attachment_content if attachment_content else "No attachments available"}

Please provide a comprehensive summary that includes:
1. Key requirements and scope of work
2. Technical specifications or skills needed
3. Performance requirements or deliverables
4. Any specific qualifications or certifications required
5. Timeline and key milestones
6. Budget or contract value information (if available)

Format your response as a clear, structured summary that would help a business development professional quickly understand what this opportunity entails and what capabilities would be needed to respond successfully.
"""
        
        try:
            return self.invoke_llm_model(self.model_id_desc, prompt)
        except Exception as e:
            logger.error(f"Failed to extract opportunity info: {str(e)}")
            return f"Error extracting opportunity information: {str(e)}"
    
    @handle_aws_error
    def query_s3_vectors(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Query company information from S3-stored vectors using semantic search.
        
        Args:
            query: The query string
            max_results: Maximum number of results to return
            
        Returns:
            List of results with content and metadata
        """
        try:
            logger.info(f"Querying S3 vectors with: {query[:100]}...")
            
            # Generate embedding for the query
            query_embedding = self._generate_embedding(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # Search for similar vectors in S3
            results = self._search_similar_vectors(query_embedding, max_results)
            
            logger.info(f"Retrieved {len(results)} results from S3 vector store")
            return results
            
        except Exception as e:
            logger.error(f"Unexpected error querying S3 vectors: {str(e)}")
            return []
    
    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using Bedrock embedding model."""
        try:
            body = {
                "inputText": text
            }
            
            response = self.bedrock_runtime.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('embedding', [])
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None
    
    def _search_similar_vectors(self, query_embedding: List[float], max_results: int) -> List[Dict[str, Any]]:
        """Search for similar vectors in S3 storage."""
        try:
            from .aws_clients import aws_clients
            s3_client = aws_clients.s3
            
            # List objects in the vector store bucket
            vector_bucket = config.s3.sam_company_info.replace('-company-info', '-company-info-vectors')
            
            response = s3_client.list_objects_v2(Bucket=vector_bucket)
            
            results = []
            for obj in response.get('Contents', []):
                if obj['Key'].endswith('.json'):
                    # Load vector data
                    vector_obj = s3_client.get_object(Bucket=vector_bucket, Key=obj['Key'])
                    vector_data = json.loads(vector_obj['Body'].read())
                    
                    # Calculate similarity (simple dot product for now)
                    stored_embedding = vector_data.get('embedding', [])
                    if stored_embedding:
                        similarity = self._calculate_similarity(query_embedding, stored_embedding)
                        
                        results.append({
                            'content': vector_data.get('content', ''),
                            'score': similarity,
                            'metadata': vector_data.get('metadata', {}),
                            'location': {'s3Location': {'uri': f"s3://{vector_bucket}/{obj['Key']}"}}
                        })
            
            # Sort by similarity score and return top results
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Failed to search S3 vectors: {str(e)}")
            return []
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            import math
            
            # Dot product
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            
            # Magnitudes
            magnitude1 = math.sqrt(sum(a * a for a in embedding1))
            magnitude2 = math.sqrt(sum(a * a for a in embedding2))
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {str(e)}")
            return 0.0
    
    def calculate_company_match(self, opportunity_info: str, opportunity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate match score between opportunity and company capabilities.
        
        Args:
            opportunity_info: Extracted opportunity information
            opportunity_data: Original opportunity data
            
        Returns:
            Dictionary containing match score, rationale, and other match details
        """
        # Query S3 vectors for relevant company information
        kb_results = self.query_s3_vectors(opportunity_info)
        
        if not kb_results:
            logger.warning("No S3 vector results found for opportunity matching")
            return {
                'match_score': 0.0,
                'is_match': False,
                'rationale': 'No relevant company information found in S3 vector store.',
                'citations': [],
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': []
            }
        
        # Prepare company information context
        company_context = ""
        citations = []
        
        for i, result in enumerate(kb_results[:5]):  # Use top 5 results
            company_context += f"\n\nCompany Information {i+1}:\n{result['content']}"
            
            # Prepare citation information
            location = result.get('location', {})
            citation = {
                'document_title': location.get('s3Location', {}).get('uri', 'Unknown Document'),
                'section_or_page': f"Section {i+1}",
                'excerpt': result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
            }
            citations.append(citation)
        
        # Create the matching prompt
        prompt = f"""
You are an expert at matching government contracting opportunities with company capabilities. Please analyze the opportunity against the company information and provide a detailed assessment.

OPPORTUNITY INFORMATION:
{opportunity_info}

COMPANY INFORMATION:
{company_context}

Please provide your analysis in the following JSON format:
{{
    "match_score": <float between 0.0 and 1.0>,
    "is_match": <boolean based on match_score >= 0.7>,
    "rationale": "<6-10 sentences explaining the match assessment with specific references to company capabilities>",
    "opportunity_required_skills": ["<skill1>", "<skill2>", ...],
    "company_skills": ["<skill1>", "<skill2>", ...],
    "past_performance": ["<relevant experience 1>", "<relevant experience 2>", ...]
}}

Guidelines:
- Match score should reflect how well the company's capabilities align with opportunity requirements
- Rationale should be specific and reference both opportunity needs and company strengths
- Include relevant skills from both opportunity and company
- Highlight past performance that demonstrates relevant experience
- Be objective and realistic in your assessment
"""
        
        try:
            response_text = self.invoke_llm_model(self.model_id_match, prompt)
            
            # Try to parse JSON response
            try:
                # Extract JSON from response (in case there's additional text)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    match_result = json.loads(json_text)
                else:
                    raise ValueError("No JSON found in response")
                
                # Add citations to the result
                match_result['citations'] = citations
                
                # Ensure required fields exist
                required_fields = ['match_score', 'is_match', 'rationale', 'opportunity_required_skills', 'company_skills', 'past_performance']
                for field in required_fields:
                    if field not in match_result:
                        match_result[field] = [] if field.endswith('_skills') or field == 'past_performance' else (0.0 if field == 'match_score' else False if field == 'is_match' else 'Not provided')
                
                return match_result
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                # Return a fallback response
                return {
                    'match_score': 0.5,
                    'is_match': False,
                    'rationale': f'Analysis completed but response format was invalid. Raw response: {response_text[:500]}...',
                    'citations': citations,
                    'opportunity_required_skills': [],
                    'company_skills': [],
                    'past_performance': []
                }
                
        except Exception as e:
            logger.error(f"Failed to calculate company match: {str(e)}")
            return {
                'match_score': 0.0,
                'is_match': False,
                'rationale': f'Error during matching analysis: {str(e)}',
                'citations': citations,
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': []
            }

# Global Bedrock client instance (lazy initialization)
_bedrock_client = None

def get_bedrock_client() -> BedrockClient:
    """Get the global Bedrock client instance (lazy initialization)."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client