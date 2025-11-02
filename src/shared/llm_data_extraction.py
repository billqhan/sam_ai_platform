"""
LLM service integration and data extraction utilities for opportunity processing.
Implements Bedrock client initialization, S3 data reading, and content processing.
"""
import json
import logging
import time
import random
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError
try:
    from .aws_clients import aws_clients, handle_aws_error
    from .config import config
    from .error_handling import ErrorHandler
except ImportError:
    # Fallback for test environments
    from aws_clients import aws_clients, handle_aws_error
    from config import config
    from error_handling import ErrorHandler

logger = logging.getLogger(__name__)

class LLMDataExtractor:
    """
    Handles data extraction and preparation for LLM processing.
    Manages S3 data reading, content truncation, and attachment processing.
    """
    
    def __init__(self):
        """Initialize the data extractor with configuration."""
        self.s3_client = aws_clients.s3
        self.bedrock_client = aws_clients.bedrock
        self.bedrock_agent_runtime = aws_clients.bedrock_agent_runtime
        
        # Load configuration from environment variables
        self.max_description_chars = config.processing.max_description_chars
        self.max_attachment_chars = config.processing.max_attachment_chars
        self.max_attachment_files = config.processing.max_attachment_files
        self.debug_mode = config.get_debug_mode()
        
        logger.info(f"LLMDataExtractor initialized with limits: "
                   f"description={self.max_description_chars}, "
                   f"attachments={self.max_attachment_chars}, "
                   f"max_files={self.max_attachment_files}")
    
    @handle_aws_error
    def read_opportunity_data(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Read opportunity JSON data from S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key for the opportunity JSON file
            
        Returns:
            Dictionary containing the opportunity data
            
        Raises:
            ClientError: If S3 read fails
            json.JSONDecodeError: If JSON parsing fails
        """
        try:
            logger.info(f"Reading opportunity data from s3://{bucket}/{key}")
            
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            
            opportunity_data = json.loads(content)
            
            if self.debug_mode:
                logger.debug(f"Opportunity data keys: {list(opportunity_data.keys())}")
                logger.debug(f"Opportunity title: {opportunity_data.get('title', 'N/A')}")
            
            logger.info(f"Successfully read opportunity data: {len(content)} characters")
            return opportunity_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Failed to read opportunity data from S3: {error_code}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse opportunity JSON: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading opportunity data: {str(e)}")
            raise
    
    @handle_aws_error
    def read_attachment_files(self, bucket: str, opportunity_id: str) -> List[str]:
        """
        Read attachment files for an opportunity from S3.
        Limits the number of files processed based on MAX_ATTACHMENT_FILES.
        
        Args:
            bucket: S3 bucket name
            opportunity_id: The opportunity ID to find attachments for
            
        Returns:
            List of attachment content strings (limited by max_attachment_files)
        """
        try:
            # List objects with the opportunity ID prefix to find attachments
            prefix = f"{opportunity_id}/"
            logger.info(f"Looking for attachments with prefix: {prefix}")
            
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=self.max_attachment_files * 2  # Get more to filter
            )
            
            objects = response.get('Contents', [])
            attachment_files = []
            
            # Filter for attachment files (exclude the main opportunity.json)
            for obj in objects:
                key = obj['Key']
                if not key.endswith('opportunity.json') and not key.endswith('/'):
                    attachment_files.append(key)
            
            # Limit to max_attachment_files
            attachment_files = attachment_files[:self.max_attachment_files]
            
            logger.info(f"Found {len(attachment_files)} attachment files to process")
            
            # Read content from each attachment file
            attachments_content = []
            for file_key in attachment_files:
                try:
                    logger.debug(f"Reading attachment: {file_key}")
                    
                    file_response = self.s3_client.get_object(Bucket=bucket, Key=file_key)
                    file_content = file_response['Body'].read()
                    
                    # Try to decode as text (handle different file types)
                    try:
                        content_text = file_content.decode('utf-8')
                    except UnicodeDecodeError:
                        # For binary files, try to extract text or skip
                        try:
                            content_text = file_content.decode('latin-1')
                        except:
                            logger.warning(f"Skipping binary file: {file_key}")
                            continue
                    
                    # Add file identifier and content
                    attachment_text = f"=== FILE: {file_key.split('/')[-1]} ===\n{content_text}\n"
                    attachments_content.append(attachment_text)
                    
                    logger.debug(f"Successfully read attachment: {len(content_text)} characters")
                    
                except Exception as e:
                    logger.warning(f"Failed to read attachment {file_key}: {str(e)}")
                    continue
            
            logger.info(f"Successfully read {len(attachments_content)} attachment files")
            return attachments_content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Failed to list/read attachments from S3: {error_code}")
            return []  # Return empty list on S3 errors
        except Exception as e:
            logger.error(f"Unexpected error reading attachments: {str(e)}")
            return []
    
    def truncate_content(self, content: str, max_chars: int, content_type: str = "content") -> str:
        """
        Truncate content to maximum character limit with smart truncation.
        
        Args:
            content: The content to truncate
            max_chars: Maximum number of characters allowed
            content_type: Type of content for logging purposes
            
        Returns:
            Truncated content string
        """
        if len(content) <= max_chars:
            return content
        
        logger.info(f"Truncating {content_type}: {len(content)} -> {max_chars} characters")
        
        # Truncate to max_chars
        truncated = content[:max_chars]
        
        # Try to truncate at word boundary to avoid cutting words
        last_space = truncated.rfind(' ')
        last_newline = truncated.rfind('\n')
        
        # Use the latest word/line boundary if it doesn't lose too much content
        boundary_pos = max(last_space, last_newline)
        if boundary_pos > max_chars * 0.8:  # Only if we don't lose more than 20%
            truncated = truncated[:boundary_pos]
        
        # Add truncation indicator
        truncated += "\n\n... [CONTENT TRUNCATED DUE TO LENGTH LIMITS] ..."
        
        logger.debug(f"Content truncated to {len(truncated)} characters")
        return truncated
    
    def prepare_opportunity_content(self, opportunity_data: Dict[str, Any], 
                                  attachments: List[str]) -> Tuple[str, str]:
        """
        Prepare opportunity content for LLM processing with proper truncation.
        
        Args:
            opportunity_data: The opportunity JSON data
            attachments: List of attachment content strings
            
        Returns:
            Tuple of (truncated_description, truncated_attachments)
        """
        # Extract and truncate opportunity description
        description = opportunity_data.get('description', '')
        title = opportunity_data.get('title', '')
        
        # Combine title and description for better context
        full_description = f"TITLE: {title}\n\nDESCRIPTION:\n{description}"
        truncated_description = self.truncate_content(
            full_description, 
            self.max_description_chars, 
            "opportunity description"
        )
        
        # Combine and truncate attachments
        if attachments:
            combined_attachments = "\n\n".join(attachments)
            truncated_attachments = self.truncate_content(
                combined_attachments,
                self.max_attachment_chars,
                "attachments"
            )
        else:
            truncated_attachments = "No attachment files available."
        
        logger.info(f"Prepared content: description={len(truncated_description)} chars, "
                   f"attachments={len(truncated_attachments)} chars")
        
        return truncated_description, truncated_attachments
    
    def extract_opportunity_id(self, s3_key: str) -> str:
        """
        Extract opportunity ID from S3 key path.
        
        Args:
            s3_key: The S3 object key
            
        Returns:
            The extracted opportunity ID
        """
        # Assume format like "opportunity_id/opportunity.json" or similar
        if '/' in s3_key:
            opportunity_id = s3_key.split('/')[0]
        else:
            # Fallback: use filename without extension
            opportunity_id = s3_key.replace('.json', '').replace('opportunity', '')
        
        logger.debug(f"Extracted opportunity ID '{opportunity_id}' from key '{s3_key}'")
        return opportunity_id
    
    def validate_opportunity_data(self, opportunity_data: Dict[str, Any]) -> bool:
        """
        Validate that opportunity data contains required fields.
        
        Args:
            opportunity_data: The opportunity data to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        required_fields = ['title', 'description']
        missing_fields = []
        
        for field in required_fields:
            if field not in opportunity_data or not opportunity_data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            logger.warning(f"Opportunity data missing required fields: {missing_fields}")
            return False
        
        logger.debug("Opportunity data validation passed")
        return True


class BedrockLLMClient:
    """
    Bedrock LLM client with proper error handling and retry logic.
    Handles model invocations for opportunity processing.
    """
    
    def __init__(self):
        """Initialize Bedrock client with configuration."""
        self.bedrock_runtime = aws_clients.bedrock
        self.bedrock_agent_runtime = aws_clients.bedrock_agent_runtime
        
        # Load model configuration
        self.model_id_desc = config.bedrock.model_id_desc
        self.model_id_match = config.bedrock.model_id_match
        self.knowledge_base_id = config.bedrock.knowledge_base_id
        self.max_tokens = config.bedrock.max_tokens
        self.temperature = config.bedrock.temperature
        
        # Processing configuration
        self.process_delay_seconds = config.processing.process_delay_seconds
        self.debug_mode = config.get_debug_mode()
        
        logger.info(f"BedrockLLMClient initialized with models: "
                   f"desc={self.model_id_desc}, match={self.model_id_match}")
    
    @handle_aws_error
    def initialize_bedrock_client(self) -> bool:
        """
        Initialize and test Bedrock client connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing Bedrock client connection")
            
            # Test connection by listing foundation models (if available)
            try:
                # This is a simple test to verify the client works
                # We don't actually need the response, just want to verify connectivity
                test_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": "test"}]
                }
                
                # Don't actually invoke, just validate the client is properly configured
                logger.info("Bedrock client initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"Bedrock client test failed: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            return False
    
    def _prepare_converse_request(self, model_id: str, prompt: str) -> Dict[str, Any]:
        """
        Prepare request for Bedrock Converse API.
        This provides better model compatibility and flexibility.
        
        Args:
            model_id: The model ID to invoke
            prompt: The prompt to send
            
        Returns:
            Formatted request for Converse API
        """
        return {
            "modelId": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": self.max_tokens,
                "temperature": self.temperature
            }
        }
    
    def _extract_converse_response(self, response: Dict[str, Any]) -> str:
        """
        Extract text response from Bedrock Converse API response.
        
        Args:
            response: The response from Bedrock Converse API
            
        Returns:
            Extracted text response
        """
        try:
            # Converse API response format
            if 'output' in response and 'message' in response['output']:
                message = response['output']['message']
                if 'content' in message and len(message['content']) > 0:
                    return message['content'][0]['text']
            
            logger.warning(f"Unexpected Converse API response format: {list(response.keys())}")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting Converse API response: {str(e)}")
            return ""
    
    def _extract_model_response(self, model_id: str, response_body: Dict[str, Any]) -> str:
        """
        Extract text response based on model type (legacy method for backward compatibility).
        
        Args:
            model_id: The model ID that was invoked
            response_body: The response body from Bedrock
            
        Returns:
            Extracted text response
        """
        # Models that use the messages format (Claude and Nova Pro)
        if 'claude' in model_id.lower() or 'nova' in model_id.lower():
            if 'content' in response_body and len(response_body['content']) > 0:
                return response_body['content'][0]['text']
            else:
                logger.warning(f"Unexpected {model_id} response format: {list(response_body.keys())}")
                return ""
        else:
            # Generic format for other models (Titan, etc.)
            return response_body.get('results', [{}])[0].get('outputText', '')
    
    def create_opportunity_enhancement_prompt(self, opportunity_description: str, attachment_content: str) -> str:
        """
        Create LLM prompt template for opportunity enhancement with structured sections.
        Ensures compliance with Requirement 4.2 for structured Business Summary and Non-Technical Summary.
        
        Args:
            opportunity_description: The opportunity description text
            attachment_content: Combined attachment content
            
        Returns:
            Formatted prompt for opportunity enhancement with strict structure requirements
        """
        prompt = f"""Analyze the following government contracting opportunity and create an enhanced description with EXACTLY the structured sections shown below. This format is required for system compatibility.

OPPORTUNITY DATA:
{opportunity_description}

ATTACHMENTS:
{attachment_content}

REQUIRED OUTPUT FORMAT - You must follow this structure exactly:

BUSINESS SUMMARY:

Purpose of the Solicitation: [Clearly state the main purpose and objectives of this government contract]

Information Unique to the Project: [Highlight unique aspects, special requirements, or distinguishing features that set this opportunity apart]

Overall Description of the Work: [Provide a comprehensive overview of the work to be performed, deliverables, and scope]

Technical Capabilities, Specific Skills, or Experience Required: [List specific technical requirements, skills, certifications, and experience needed]

NON-TECHNICAL SUMMARY:

Clearances Information: [Security clearance requirements, if any, or state "Not specified in available documentation"]

Technical Proposal Evaluation: [How technical proposals will be evaluated, scoring criteria, or state "Standard government evaluation criteria"]

Security: [Security requirements, protocols, facility requirements, or state "Standard government security requirements"]

Compliance: [Regulatory and compliance requirements, certifications needed, or state "Federal contracting compliance requirements"]

EXTRACTED SKILLS AND REQUIREMENTS:
SKILLS_JSON: ["skill1", "skill2", "skill3", ...]

CRITICAL INSTRUCTIONS:
1. You MUST use the exact section headers shown above (BUSINESS SUMMARY:, NON-TECHNICAL SUMMARY:, etc.)
2. You MUST include all subsections under each main section
3. If information is not available, use the suggested fallback text rather than omitting sections
4. Extract 5-15 specific skills/requirements for the SKILLS_JSON array
5. Focus on accuracy and completeness while maintaining the required structure"""

        return prompt
    
    def parse_opportunity_enhancement_response(self, response_text: str) -> Tuple[str, List[str]]:
        """
        Parse the LLM response to extract enhanced_description and opportunity_required_skills.
        Ensures structured format compliance with Requirements 4.2.
        
        Args:
            response_text: The raw response from the LLM
            
        Returns:
            Tuple of (enhanced_description, opportunity_required_skills)
        """
        try:
            # Extract skills JSON if present
            skills = []
            enhanced_description = response_text.strip()
            
            if "SKILLS_JSON:" in response_text:
                skills_start = response_text.find("SKILLS_JSON:") + len("SKILLS_JSON:")
                skills_end = response_text.find("\n", skills_start)
                if skills_end == -1:
                    skills_end = len(response_text)
                
                skills_json_str = response_text[skills_start:skills_end].strip()
                try:
                    # Handle potential formatting issues
                    skills_json_str = skills_json_str.strip('[]').strip()
                    if skills_json_str.startswith('[') and skills_json_str.endswith(']'):
                        skills = json.loads(skills_json_str)
                    else:
                        # Try to parse as array
                        skills = json.loads(f'[{skills_json_str}]')
                    
                    if not isinstance(skills, list):
                        skills = []
                    
                    # Clean up skills list
                    skills = [str(skill).strip().strip('"\'') for skill in skills if skill and str(skill).strip()]
                    skills = [skill for skill in skills if len(skill) > 2 and len(skill) < 200]  # Reasonable skill length
                    
                except json.JSONDecodeError:
                    logger.warning("Failed to parse skills JSON from LLM response, trying alternative parsing")
                    # Try to extract skills from comma-separated format
                    skills_text = skills_json_str.strip('[]"\'')
                    if ',' in skills_text:
                        skills = [skill.strip().strip('"\'') for skill in skills_text.split(',')]
                        skills = [skill for skill in skills if skill and len(skill) > 2]
                    else:
                        skills = []
                
                # Remove the skills JSON from the enhanced description
                enhanced_description = response_text[:response_text.find("SKILLS_JSON:")].strip()
            
            # Validate structured format compliance (Requirement 4.2)
            if not self._validate_structured_format(enhanced_description):
                logger.warning("Enhanced description missing required structured format")
                enhanced_description = self._ensure_structured_format(enhanced_description)
            
            # Ensure we have some skills even if parsing failed
            if not skills:
                skills = self._extract_skills_from_description(enhanced_description)
            
            # Limit skills to reasonable number
            if len(skills) > 20:
                skills = skills[:20]
                logger.info(f"Truncated skills list to 20 items")
            
            logger.info(f"Parsed enhancement response: {len(enhanced_description)} chars, {len(skills)} skills")
            logger.info(f"Structured format validation: {'PASS' if self._validate_structured_format(enhanced_description) else 'FAIL'}")
            
            return enhanced_description, skills
            
        except Exception as e:
            logger.error(f"Error parsing opportunity enhancement response: {str(e)}")
            # Return the raw response and empty skills list as fallback
            return response_text.strip(), []
    
    def _validate_structured_format(self, description: str) -> bool:
        """
        Validate that the description contains required structured sections.
        
        Args:
            description: The enhanced description to validate
            
        Returns:
            True if structured format is present, False otherwise
        """
        required_sections = [
            "BUSINESS SUMMARY:",
            "Purpose of the Solicitation:",
            "Information Unique to the Project:",
            "Overall Description of the Work:",
            "Technical Capabilities, Specific Skills, or Experience Required:",
            "NON-TECHNICAL SUMMARY:",
            "Clearances Information:",
            "Technical Proposal Evaluation:",
            "Security:",
            "Compliance:"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in description:
                missing_sections.append(section)
        
        if missing_sections:
            logger.debug(f"Missing structured sections: {missing_sections}")
            return False
        
        return True
    
    def _ensure_structured_format(self, description: str) -> str:
        """
        Ensure the description has the required structured format.
        
        Args:
            description: Original description
            
        Returns:
            Description with structured format
        """
        if self._validate_structured_format(description):
            return description
        
        # If already has some structure, try to preserve it
        if "BUSINESS SUMMARY:" in description or "NON-TECHNICAL SUMMARY:" in description:
            return description
        
        # Create minimal structured format
        structured_description = f"""BUSINESS SUMMARY:

Purpose of the Solicitation: Government contracting opportunity requiring analysis

Information Unique to the Project: {description[:300]}{'...' if len(description) > 300 else ''}

Overall Description of the Work: {description[:500]}{'...' if len(description) > 500 else ''}

Technical Capabilities, Specific Skills, or Experience Required: Not specified in available documentation

NON-TECHNICAL SUMMARY:

Clearances Information: Not specified in available documentation

Technical Proposal Evaluation: Standard government evaluation criteria

Security: Standard government security requirements

Compliance: Federal contracting compliance requirements

[Note: Original unstructured content: {description[:200]}{'...' if len(description) > 200 else ''}]"""
        
        return structured_description
    
    def _extract_skills_from_description(self, description: str) -> List[str]:
        """
        Extract skills from the technical capabilities section of the description.
        
        Args:
            description: The enhanced description
            
        Returns:
            List of extracted skills
        """
        skills = []
        
        try:
            # Look for technical capabilities section
            if "Technical Capabilities, Specific Skills, or Experience Required:" in description:
                tech_section_start = description.find("Technical Capabilities, Specific Skills, or Experience Required:")
                tech_section_end = description.find("NON-TECHNICAL SUMMARY:", tech_section_start)
                if tech_section_end == -1:
                    tech_section_end = len(description)
                
                tech_section = description[tech_section_start:tech_section_end]
                
                # Extract skills from bullet points or lists
                lines = tech_section.split('\n')
                for line in lines[1:]:  # Skip the header line
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                        skill = line.lstrip('-•* ').strip()
                        if skill and len(skill) > 3 and len(skill) < 100:  # Reasonable skill length
                            skills.append(skill)
                    elif line and len(line) > 10 and len(line) < 100 and not line.endswith(':'):
                        # Potential skill without bullet point
                        skills.append(line)
            
            # If no skills found, create generic ones
            if not skills:
                skills = ["Government contracting experience", "Technical proposal writing", "Federal compliance knowledge"]
            
        except Exception as e:
            logger.warning(f"Error extracting skills from description: {str(e)}")
            skills = ["Manual review required - skill extraction failed"]
        
        return skills[:10]  # Limit to 10 skills
    
    def retry_with_exponential_backoff(self, func, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        """
        Retry function with exponential backoff for LLM API calls.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Function result if successful
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.1)  # Add up to 10% jitter
                    total_delay = delay + jitter
                    
                    logger.info(f"Retrying LLM call (attempt {attempt + 1}/{max_retries + 1}) after {total_delay:.2f}s delay")
                    time.sleep(total_delay)
                
                result = func()
                
                if attempt > 0:
                    logger.info(f"LLM call succeeded on retry attempt {attempt + 1}")
                
                return result
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                last_exception = e
                
                if error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
                    if attempt < max_retries:
                        logger.warning(f"LLM call throttled, will retry (attempt {attempt + 1}/{max_retries + 1})")
                        continue
                    else:
                        logger.error(f"LLM call failed after {max_retries + 1} attempts due to throttling")
                        raise
                else:
                    # Non-retryable error
                    logger.error(f"LLM call failed with non-retryable error: {error_code}")
                    raise
                    
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"LLM call failed, will retry (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    continue
                else:
                    logger.error(f"LLM call failed after {max_retries + 1} attempts")
                    raise
        
        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise Exception("Retry logic failed unexpectedly")
    
    def apply_process_delay(self):
        """
        Apply PROCESS_DELAY_SECONDS rate limiting between API calls.
        """
        if self.process_delay_seconds > 0:
            logger.debug(f"Applying process delay: {self.process_delay_seconds} seconds")
            time.sleep(self.process_delay_seconds)
    
    @handle_aws_error
    def extract_opportunity_info(self, opportunity_description: str, attachment_content: str) -> Tuple[str, List[str]]:
        """
        Extract and enhance opportunity information using Bedrock LLM.
        Implements the "Get Opportunity Info" functionality with retry logic and rate limiting.
        
        Args:
            opportunity_description: The opportunity description text
            attachment_content: Combined attachment content
            
        Returns:
            Tuple of (enhanced_description, opportunity_required_skills)
            
        Raises:
            ClientError: If Bedrock API calls fail after retries
        """
        logger.info("Starting opportunity information extraction using LLM")
        
        # Apply rate limiting before making the call
        self.apply_process_delay()
        
        # Create the enhancement prompt
        prompt = self.create_opportunity_enhancement_prompt(opportunity_description, attachment_content)
        
        if self.debug_mode:
            logger.debug(f"Opportunity enhancement prompt length: {len(prompt)}")
            logger.debug(f"Using model: {self.model_id_desc}")
        
        # Define the function to retry
        def make_llm_call():
            return self.invoke_model(self.model_id_desc, prompt)
        
        try:
            # Make the LLM call with retry logic
            response_text = self.retry_with_exponential_backoff(make_llm_call)
            
            if self.debug_mode:
                logger.debug(f"LLM response length: {len(response_text)}")
                logger.debug(f"LLM response preview: {response_text[:300]}...")
            
            # Parse the response
            enhanced_description, opportunity_required_skills = self.parse_opportunity_enhancement_response(response_text)
            
            logger.info(f"Successfully extracted opportunity info: "
                       f"description={len(enhanced_description)} chars, "
                       f"skills={len(opportunity_required_skills)} items")
            
            return enhanced_description, opportunity_required_skills
            
        except Exception as e:
            logger.error(f"Failed to extract opportunity information: {str(e)}")
            
            # Create fallback enhanced description
            fallback_description = f"""
BUSINESS SUMMARY:
Purpose of the Solicitation: {opportunity_description[:200]}...
Information Unique to the Project: Unable to extract due to LLM processing error
Overall Description of the Work: {opportunity_description[:500]}...
Technical Capabilities, Specific Skills, or Experience Required: Unable to extract due to LLM processing error

NON-TECHNICAL SUMMARY:
Clearances Information: Not specified in available documentation
Technical Proposal Evaluation: Standard government evaluation criteria
Security: Standard government security requirements
Compliance: Federal contracting compliance requirements

[Note: This is a fallback description due to LLM processing error: {str(e)}]
"""
            
            fallback_skills = ["LLM processing failed - manual review required"]
            
            logger.warning("Using fallback opportunity description due to LLM error")
            return fallback_description.strip(), fallback_skills

    @handle_aws_error
    def invoke_model(self, model_id: str, prompt: str) -> str:
        """
        Invoke a Bedrock model with proper error handling.
        
        Args:
            model_id: The model ID to invoke
            prompt: The prompt to send to the model
            
        Returns:
            The model's response text
            
        Raises:
            ClientError: If Bedrock API call fails
        """
        try:
            if self.debug_mode:
                logger.debug(f"Invoking model {model_id} with prompt length: {len(prompt)}")
                logger.debug(f"Prompt preview: {prompt[:200]}...")
            
            # Prepare request for Converse API
            converse_request = self._prepare_converse_request(model_id, prompt)
            
            # Invoke the model using Converse API
            response = self.bedrock_runtime.converse(**converse_request)
            
            # Parse Converse API response
            if self.debug_mode:
                logger.debug(f"Converse response keys: {list(response.keys())}")
            
            # Extract text from Converse API response
            response_text = self._extract_converse_response(response)
            
            logger.info(f"Model invocation successful: {len(response_text)} characters returned")
            return response_text
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'ThrottlingException':
                logger.warning(f"Model invocation throttled: {error_message}")
                # Let the caller handle retry logic
                raise
            else:
                logger.error(f"Model invocation failed: {error_code} - {error_message}")
                raise
                
        except Exception as e:
            logger.error(f"Unexpected error during model invocation: {str(e)}")
            raise

    @handle_aws_error
    def query_knowledge_base(self, query_text: str, max_results: int = 10, 
                           error_handler: ErrorHandler = None, opportunity_id: str = None) -> List[Dict[str, Any]]:
        """
        Query the Bedrock Knowledge Base for company capability information.
        Enhanced with comprehensive error handling and logging.
        
        Args:
            query_text: The query text to search for
            max_results: Maximum number of results to return
            error_handler: Error handler for enhanced logging
            opportunity_id: Opportunity ID for error tracking
            
        Returns:
            List of knowledge base results with proper kb_retrieval_results formatting
            
        Raises:
            ClientError: If Knowledge Base query fails
        """
        if not self.knowledge_base_id:
            logger.warning("No KNOWLEDGE_BASE_ID configured, returning empty results")
            return []
        
        try:
            # Log knowledge base request
            if error_handler:
                error_handler.log_knowledge_base_request(
                    query_text, 
                    self.knowledge_base_id,
                    {'numberOfResults': max_results}
                )
            
            logger.info(f"Querying Knowledge Base {self.knowledge_base_id} with query: {query_text[:100]}...")
            
            # Apply rate limiting before making the call
            self.apply_process_delay()
            
            start_time = time.time()
            
            # Query the knowledge base using bedrock-agent-runtime
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={
                    'text': query_text
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results
                    }
                }
            )
            
            processing_time = time.time() - start_time
            
            # Format results according to kb_retrieval_results structure
            kb_results = []
            retrieval_results = response.get('retrievalResults', [])
            
            for i, result in enumerate(retrieval_results):
                content = result.get('content', {})
                location = result.get('location', {})
                metadata = result.get('metadata', {})
                
                # Extract text content
                text_content = content.get('text', '')
                
                # Format location information
                location_info = {}
                if 's3Location' in location:
                    s3_location = location['s3Location']
                    location_info = {
                        's3Location': {
                            'uri': s3_location.get('uri', ''),
                            'bucketOwner': s3_location.get('bucketOwner', '')
                        }
                    }
                
                # Create formatted result
                formatted_result = {
                    'index': i,
                    'title': metadata.get('title', f"Document {i+1}"),
                    'snippet': text_content[:500] + "..." if len(text_content) > 500 else text_content,
                    'source': location_info.get('s3Location', {}).get('uri', 'Unknown Source'),
                    'metadata': metadata,
                    'location': location_info,
                    'score': result.get('score', 0.0),
                    'full_content': text_content  # Keep full content for LLM processing
                }
                
                kb_results.append(formatted_result)
            
            # Log knowledge base response
            if error_handler:
                error_handler.log_knowledge_base_response(
                    self.knowledge_base_id,
                    len(kb_results),
                    processing_time,
                    {'retrievalResults': len(retrieval_results)}
                )
            
            logger.info(f"Successfully retrieved {len(kb_results)} results from Knowledge Base")
            
            if self.debug_mode:
                for i, result in enumerate(kb_results[:3]):  # Log first 3 results
                    logger.debug(f"KB Result {i+1}: title='{result['title']}', "
                               f"snippet_length={len(result['snippet'])}, score={result['score']}")
            
            return kb_results
            
        except Exception as e:
            # Enhanced knowledge base error logging
            if error_handler and opportunity_id:
                error_handler.log_knowledge_base_error(
                    opportunity_id, e, query_text, self.knowledge_base_id
                )
            else:
                logger.error(f"Knowledge Base query failed: {str(e)}")
                logger.error(f"Query: {query_text[:200]}{'...' if len(query_text) > 200 else ''}")
                logger.error(f"Knowledge Base ID: {self.knowledge_base_id}")
            
            raise
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Knowledge Base query failed: {error_code} - {error_message}")
            
            if error_code in ['ThrottlingException', 'ServiceQuotaExceededException']:
                # Let the caller handle retry logic
                raise
            else:
                # For other errors, return empty results but log the error
                logger.warning(f"Returning empty KB results due to error: {error_code}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error during Knowledge Base query: {str(e)}")
            return []

    def create_company_matching_prompt(self, enhanced_description: str, 
                                     opportunity_required_skills: List[str],
                                     kb_results: List[Dict[str, Any]]) -> str:
        """
        Create LLM prompt template for company matching analysis.
        Prevents hallucinations when no knowledge base data is available.
        
        Args:
            enhanced_description: The enhanced opportunity description
            opportunity_required_skills: List of required skills from opportunity
            kb_results: Knowledge base results with company capabilities
            
        Returns:
            Formatted prompt for company matching analysis
        """
        # Check if we have any knowledge base results
        has_company_data = bool(kb_results)
        
        # Prepare company capabilities context from KB results
        company_context = ""
        if has_company_data:
            company_context = "COMPANY CAPABILITIES FROM KNOWLEDGE BASE:\n\n"
            for i, result in enumerate(kb_results[:5]):  # Use top 5 results
                company_context += f"Document {i+1}: {result['title']}\n"
                company_context += f"Content: {result['full_content']}\n"
                company_context += f"Source: {result['source']}\n\n"
        else:
            company_context = "COMPANY CAPABILITIES: No relevant company information found in knowledge base.\n\n"
        
        # Format opportunity skills
        skills_text = ", ".join(opportunity_required_skills) if opportunity_required_skills else "None specified"
        
        # Create different prompts based on whether we have company data
        if has_company_data:
            prompt = f"""You are an expert at analyzing government contracting opportunities and matching them against company capabilities. Please analyze how well our company matches this opportunity.

OPPORTUNITY INFORMATION:
{enhanced_description}

OPPORTUNITY REQUIRED SKILLS:
{skills_text}

{company_context}

Please provide a comprehensive analysis in the following JSON format:

{{
    "score": <float between 0.0 and 1.0 representing match strength>,
    "rationale": "<detailed 6-10 sentence explanation of the match assessment, highlighting specific company strengths, capability gaps, and overall fit>",
    "opportunity_required_skills": [<list of key skills/capabilities required by the opportunity>],
    "company_skills": [<list of relevant company skills/capabilities that match the opportunity>],
    "past_performance": [<list of relevant past performance examples or experience areas>],
    "citations": [
        {{
            "document_title": "<title of source document>",
            "section_or_page": "<section or page reference>",
            "excerpt": "<relevant excerpt from the document>"
        }}
    ]
}}

ANALYSIS GUIDELINES:
- Score should reflect realistic match strength (0.0 = no match, 1.0 = perfect match)
- Rationale should be specific and reference both opportunity requirements and company capabilities
- Include specific technical skills, experience areas, and qualifications
- Citations should reference the knowledge base documents provided
- Be objective and highlight both strengths and potential gaps
- Consider past performance, technical capabilities, and relevant experience

Focus on providing actionable insights for business development decision-making."""
        else:
            # Special prompt for when no company data is available - prevents hallucination
            prompt = f"""You are analyzing a government contracting opportunity, but no company capability information is available in the knowledge base.

OPPORTUNITY INFORMATION:
{enhanced_description}

OPPORTUNITY REQUIRED SKILLS:
{skills_text}

IMPORTANT: No company information was found in the knowledge base. You must NOT make up or assume any company capabilities.

Please provide the following JSON response indicating that no match assessment can be performed:

{{
    "score": 0.0,
    "rationale": "Unable to assess company match for this opportunity because no company capability information was found in the knowledge base. To properly evaluate this opportunity, company information including past performance, technical capabilities, certifications, and relevant experience would need to be available in the system. Manual review is recommended to determine if the company has the required capabilities.",
    "opportunity_required_skills": [<extract key skills/capabilities required by the opportunity>],
    "company_skills": [],
    "past_performance": [],
    "citations": []
}}

CRITICAL INSTRUCTIONS:
- You MUST set the score to 0.0 since no company data is available
- You MUST NOT list any company skills or capabilities in company_skills array
- You MUST NOT create any citations since no company documents were found
- You MUST NOT assume or invent company capabilities
- You SHOULD extract the opportunity required skills accurately
- Your rationale MUST explain that no company information was available"""

        return prompt

    def parse_company_matching_response(self, response_text: str, 
                                      kb_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse the LLM response for company matching to extract structured data.
        
        Args:
            response_text: The raw response from the LLM
            kb_results: Original KB results for citation mapping
            
        Returns:
            Dictionary with match score, rationale, skills, and citations
        """
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                match_result = json.loads(json_text)
            else:
                raise ValueError("No JSON found in response")
            
            # Validate and ensure required fields exist
            required_fields = {
                'score': 0.0,
                'rationale': 'Analysis completed but rationale not provided',
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': [],
                'citations': []
            }
            
            for field, default_value in required_fields.items():
                if field not in match_result:
                    match_result[field] = default_value
            
            # Ensure score is within valid range
            score = match_result.get('score', 0.0)
            if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
                logger.warning(f"Invalid score value: {score}, setting to 0.0")
                match_result['score'] = 0.0
            
            # Ensure lists are actually lists
            list_fields = ['opportunity_required_skills', 'company_skills', 'past_performance', 'citations']
            for field in list_fields:
                if not isinstance(match_result.get(field), list):
                    match_result[field] = []
            
            # Validate and enhance citations format using KB results
            validated_citations = self._create_citations_from_kb_results(
                match_result.get('citations', []), kb_results
            )
            match_result['citations'] = validated_citations
            
            # Add kb_retrieval_results from original KB query
            match_result['kb_retrieval_results'] = [
                {
                    'index': result['index'],
                    'title': result['title'],
                    'snippet': result['snippet'],
                    'source': result['source'],
                    'metadata': result['metadata'],
                    'location': result['location']
                }
                for result in kb_results
            ]
            
            logger.info(f"Successfully parsed company matching response: "
                       f"score={match_result['score']}, "
                       f"skills={len(match_result['company_skills'])}, "
                       f"citations={len(match_result['citations'])}")
            
            return match_result
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse company matching JSON response: {str(e)}")
            
            # Create fallback response
            fallback_result = {
                'score': 0.0,
                'rationale': f'Analysis completed but response format was invalid. Error: {str(e)}. Raw response preview: {response_text[:300]}...',
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': [
                    {
                        'index': result['index'],
                        'title': result['title'],
                        'snippet': result['snippet'],
                        'source': result['source'],
                        'metadata': result['metadata'],
                        'location': result['location']
                    }
                    for result in kb_results
                ]
            }
            
            return fallback_result
            
        except Exception as e:
            logger.error(f"Unexpected error parsing company matching response: {str(e)}")
            
            # Create error response
            error_result = {
                'score': 0.0,
                'rationale': f'Error during response parsing: {str(e)}',
                'opportunity_required_skills': [],
                'company_skills': [],
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': []
            }
            
            return error_result
    
    def _create_citations_from_kb_results(self, llm_citations: List[Dict[str, Any]], 
                                         kb_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create proper citations that reference actual KB content instead of generic placeholders.
        
        Args:
            llm_citations: Citations from LLM response (may be generic)
            kb_results: Knowledge base results with actual content
            
        Returns:
            List of validated citations with proper source references
        """
        if not kb_results:
            return []
        
        validated_citations = []
        
        # If LLM provided meaningful citations, try to map them to KB results
        if llm_citations and any(c.get('excerpt') and c.get('excerpt') != 'No excerpt provided' for c in llm_citations):
            for citation in llm_citations:
                if isinstance(citation, dict) and citation.get('excerpt'):
                    # Try to find matching KB result based on content similarity
                    best_match = self._find_best_kb_match_for_citation(citation, kb_results)
                    if best_match:
                        validated_citation = {
                            'document_title': self._extract_filename_from_source(best_match['source']),
                            'section_or_page': citation.get('section_or_page', ''),
                            'excerpt': citation.get('excerpt', '')
                        }
                        validated_citations.append(validated_citation)
        
        # If no meaningful LLM citations or we need more, create citations from top KB results
        if len(validated_citations) < 3 and len(kb_results) > 0:
            # Add citations from top KB results that weren't already included
            used_sources = {c['document_title'] for c in validated_citations}
            
            for kb_result in kb_results[:5]:  # Use top 5 KB results
                filename = self._extract_filename_from_source(kb_result['source'])
                if filename not in used_sources:
                    # Extract meaningful excerpt from KB content
                    excerpt = self._extract_meaningful_excerpt(kb_result)
                    if excerpt:
                        citation = {
                            'document_title': filename,
                            'section_or_page': self._extract_section_from_kb_result(kb_result),
                            'excerpt': excerpt
                        }
                        validated_citations.append(citation)
                        used_sources.add(filename)
                        
                        # Limit to reasonable number of citations
                        if len(validated_citations) >= 5:
                            break
        
        logger.info(f"Created {len(validated_citations)} citations from {len(kb_results)} KB results")
        return validated_citations
    
    def _find_best_kb_match_for_citation(self, citation: Dict[str, Any], 
                                        kb_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Find the best KB result that matches a citation excerpt.
        
        Args:
            citation: Citation with excerpt to match
            kb_results: Available KB results
            
        Returns:
            Best matching KB result or None
        """
        citation_excerpt = citation.get('excerpt', '').lower()
        if not citation_excerpt or len(citation_excerpt) < 10:
            return None
        
        best_match = None
        best_score = 0
        
        for kb_result in kb_results:
            kb_content = kb_result.get('full_content', kb_result.get('snippet', '')).lower()
            
            # Simple similarity check - count common words
            citation_words = set(citation_excerpt.split())
            kb_words = set(kb_content.split())
            common_words = citation_words.intersection(kb_words)
            
            if len(common_words) > 0:
                score = len(common_words) / len(citation_words)
                if score > best_score:
                    best_score = score
                    best_match = kb_result
        
        return best_match if best_score > 0.3 else None  # Require 30% word overlap
    
    def _extract_filename_from_source(self, source_uri: str) -> str:
        """
        Extract filename from S3 URI or source path.
        
        Args:
            source_uri: S3 URI or file path
            
        Returns:
            Filename without path
        """
        if not source_uri:
            return "Unknown Document"
        
        # Handle S3 URIs
        if source_uri.startswith('s3://'):
            return source_uri.split('/')[-1]
        
        # Handle regular file paths
        return source_uri.split('/')[-1] if '/' in source_uri else source_uri
    
    def _extract_meaningful_excerpt(self, kb_result: Dict[str, Any]) -> str:
        """
        Extract a meaningful excerpt from KB result content.
        
        Args:
            kb_result: Knowledge base result
            
        Returns:
            Meaningful excerpt or empty string
        """
        # Try to get full content first, then snippet
        content = kb_result.get('full_content', kb_result.get('snippet', ''))
        
        if not content:
            return ""
        
        # Clean up JSON formatting if present
        if content.startswith('{"text":'):
            try:
                parsed = json.loads(content)
                content = parsed.get('text', content)
            except:
                pass
        
        # Extract first meaningful sentence or paragraph
        sentences = content.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and not sentence.startswith('#') and not sentence.startswith('<'):
                # Limit excerpt length
                if len(sentence) > 200:
                    sentence = sentence[:200] + "..."
                return sentence
        
        # Fallback to first 200 characters
        clean_content = content.replace('\n', ' ').strip()
        if len(clean_content) > 200:
            return clean_content[:200] + "..."
        
        return clean_content if len(clean_content) > 10 else ""
    
    def _extract_section_from_kb_result(self, kb_result: Dict[str, Any]) -> str:
        """
        Extract section information from KB result metadata.
        
        Args:
            kb_result: Knowledge base result
            
        Returns:
            Section identifier or empty string
        """
        metadata = kb_result.get('metadata', {})
        
        # Try to get page number
        page_num = metadata.get('x-amz-bedrock-kb-document-page-number')
        if page_num is not None:
            return f"Page {int(page_num)}"
        
        # Try to extract section from content
        content = kb_result.get('full_content', kb_result.get('snippet', ''))
        if content and '#' in content:
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('#') and not line.startswith('##'):
                    # Extract section title
                    section = line.replace('#', '').strip()
                    if len(section) > 0 and len(section) < 100:
                        return section
        
        return ""

    @handle_aws_error
    def calculate_company_match(self, enhanced_description: str, 
                              opportunity_required_skills: List[str],
                              error_handler: ErrorHandler = None,
                              opportunity_id: str = None) -> Tuple[Dict[str, Any], bool]:
        """
        Calculate company match using Knowledge Base integration and LLM analysis.
        Implements the "Calculate Company Match" functionality with proper error handling.
        Prevents hallucinations when no knowledge base data is available.
        
        Args:
            enhanced_description: The enhanced opportunity description
            opportunity_required_skills: List of skills required by the opportunity
            error_handler: Error handler for enhanced logging
            opportunity_id: Opportunity ID for error tracking
            
        Returns:
            Tuple of (match_result_dict, success_boolean)
            
        Raises:
            ClientError: If Bedrock API calls fail after retries
        """
        logger.info("Starting company match calculation using Knowledge Base and LLM")
        
        try:
            # Step 1: Query Knowledge Base for relevant company capabilities
            logger.info("Step 1: Querying Knowledge Base for company capabilities")
            
            # Create query from enhanced description and required skills
            query_parts = [enhanced_description[:500]]  # Use first 500 chars of description
            if opportunity_required_skills:
                query_parts.append("Required skills: " + ", ".join(opportunity_required_skills[:10]))
            
            kb_query = " ".join(query_parts)
            
            # Define the KB query function for retry logic
            def make_kb_query():
                return self.query_knowledge_base(kb_query, max_results=10, 
                                               error_handler=error_handler, 
                                               opportunity_id=opportunity_id)
            
            # Query KB with retry logic
            kb_results = self.retry_with_exponential_backoff(make_kb_query)
            
            # Check if we have any meaningful knowledge base results
            has_company_data = bool(kb_results)
            
            if not has_company_data:
                logger.warning("No Knowledge Base results found - will return 0.0 score to prevent hallucination")
                
                # Return immediate result without LLM call to prevent hallucination
                no_data_result = {
                    'score': 0.0,
                    'rationale': 'Unable to assess company match for this opportunity because no company capability information was found in the knowledge base. To properly evaluate this opportunity, company information including past performance, technical capabilities, certifications, and relevant experience would need to be available in the system. Manual review is recommended to determine if the company has the required capabilities for this solicitation.',
                    'opportunity_required_skills': opportunity_required_skills or [],
                    'company_skills': [],
                    'past_performance': [],
                    'citations': [],
                    'kb_retrieval_results': []
                }
                
                logger.info("Returning no-data result to prevent hallucination: score=0.0, no company capabilities")
                return no_data_result, False  # False indicates no actual match processing occurred
            else:
                logger.info(f"Retrieved {len(kb_results)} results from Knowledge Base - proceeding with match analysis")
            
            # Step 2: Create company matching prompt
            logger.info("Step 2: Creating company matching prompt")
            matching_prompt = self.create_company_matching_prompt(
                enhanced_description, 
                opportunity_required_skills, 
                kb_results
            )
            
            if self.debug_mode:
                logger.debug(f"Company matching prompt length: {len(matching_prompt)}")
                logger.debug(f"Using model: {self.model_id_match}")
            
            # Step 3: Call LLM for company matching analysis
            logger.info("Step 3: Calling LLM for company matching analysis")
            
            # Apply rate limiting before making the call
            self.apply_process_delay()
            
            # Define the LLM call function for retry logic
            def make_matching_call():
                return self.invoke_model(self.model_id_match, matching_prompt)
            
            # Make the LLM call with retry logic
            response_text = self.retry_with_exponential_backoff(make_matching_call)
            
            if self.debug_mode:
                logger.debug(f"LLM matching response length: {len(response_text)}")
                logger.debug(f"LLM matching response preview: {response_text[:300]}...")
            
            # Step 4: Parse the response
            logger.info("Step 4: Parsing company matching response")
            match_result = self.parse_company_matching_response(response_text, kb_results)
            
            # Validate that the result doesn't contain hallucinated company capabilities
            if not has_company_data and (match_result.get('company_skills') or match_result.get('score', 0.0) > 0.0):
                logger.warning("LLM attempted to hallucinate company capabilities - overriding with no-data result")
                match_result = {
                    'score': 0.0,
                    'rationale': 'LLM attempted to generate company capabilities without knowledge base data. No company information available for match assessment.',
                    'opportunity_required_skills': opportunity_required_skills or [],
                    'company_skills': [],
                    'past_performance': [],
                    'citations': [],
                    'kb_retrieval_results': []
                }
                return match_result, False
            
            logger.info(f"Successfully calculated company match: "
                       f"score={match_result['score']}, "
                       f"company_skills={len(match_result['company_skills'])}, "
                       f"kb_results={len(match_result['kb_retrieval_results'])}")
            
            return match_result, True
            
        except Exception as e:
            logger.error(f"Failed to calculate company match: {str(e)}")
            
            # Create fallback match result
            fallback_result = {
                'score': 0.0,
                'rationale': f'Company match calculation failed due to error: {str(e)}. Manual review required.',
                'opportunity_required_skills': opportunity_required_skills or [],
                'company_skills': [],
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': []
            }
            
            logger.warning("Using fallback company match result due to processing error")
            return fallback_result, False


# Global instances for easy access
_llm_data_extractor = None
_bedrock_llm_client = None

def get_llm_data_extractor() -> LLMDataExtractor:
    """Get the global LLM data extractor instance (lazy initialization)."""
    global _llm_data_extractor
    if _llm_data_extractor is None:
        _llm_data_extractor = LLMDataExtractor()
    return _llm_data_extractor

def get_bedrock_llm_client() -> BedrockLLMClient:
    """Get the global Bedrock LLM client instance (lazy initialization)."""
    global _bedrock_llm_client
    if _bedrock_llm_client is None:
        _bedrock_llm_client = BedrockLLMClient()
    return _bedrock_llm_client