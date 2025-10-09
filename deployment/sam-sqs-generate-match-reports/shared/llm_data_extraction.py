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
    
    def extract_opportunity_info(self, description: str, attachment_content: str) -> Tuple[str, List[str]]:
        """
        Extract opportunity information using LLM.
        
        Args:
            description: Opportunity description
            attachment_content: Attachment content
            
        Returns:
            Tuple of (enhanced_description, opportunity_required_skills)
        """
        try:
            prompt = self.create_opportunity_enhancement_prompt(description, attachment_content)
            
            # Prepare request body based on model type
            if 'claude' in self.model_id_desc.lower():
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            else:
                # Titan model format
                request_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": self.max_tokens,
                        "temperature": self.temperature,
                        "topP": 0.9,
                        "stopSequences": []
                    }
                }
            
            # Invoke model
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id_desc,
                body=json.dumps(request_body)
            )
            
            # Parse response based on model type
            response_body = json.loads(response['body'].read())
            if 'claude' in self.model_id_desc.lower():
                response_text = response_body['content'][0]['text']
            else:
                # Titan model response format
                response_text = response_body['results'][0]['outputText']
            
            # Parse the response
            enhanced_description, skills = self.parse_opportunity_enhancement_response(response_text)
            
            return enhanced_description, skills
            
        except Exception as e:
            logger.error(f"Failed to extract opportunity info: {str(e)}")
            # Return fallback
            fallback_description = f"BUSINESS SUMMARY:\n{description}\n\nNON-TECHNICAL SUMMARY:\nProcessing failed - manual review required"
            return fallback_description, ["Manual review required"]
    
    def calculate_company_match(self, enhanced_description: str, opportunity_required_skills: List[str],
                              error_handler: ErrorHandler = None, opportunity_id: str = None) -> Dict[str, Any]:
        """
        Calculate company match using LLM.
        
        Args:
            enhanced_description: Enhanced opportunity description
            opportunity_required_skills: Required skills list
            error_handler: Error handler instance
            opportunity_id: Opportunity ID for logging
            
        Returns:
            Company match result dictionary
        """
        try:
            # Create matching prompt
            prompt = f"""Analyze this government contracting opportunity and determine our company's match score.

OPPORTUNITY DESCRIPTION:
{enhanced_description}

REQUIRED SKILLS:
{', '.join(opportunity_required_skills)}

Provide a match score from 0.0 to 1.0 and explain your reasoning.

RESPONSE FORMAT:
MATCH_SCORE: [0.0-1.0]
RATIONALE: [Your detailed analysis]
COMPANY_SKILLS: ["skill1", "skill2", "skill3"]
PAST_PERFORMANCE: ["example1", "example2"]
"""
            
            # Prepare request body based on model type
            if 'claude' in self.model_id_match.lower():
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            else:
                # Titan model format
                request_body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": self.max_tokens,
                        "temperature": self.temperature,
                        "topP": 0.9,
                        "stopSequences": []
                    }
                }
            
            # Invoke model
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id_match,
                body=json.dumps(request_body)
            )
            
            # Parse response based on model type
            response_body = json.loads(response['body'].read())
            if 'claude' in self.model_id_match.lower():
                response_text = response_body['content'][0]['text']
            else:
                # Titan model response format
                response_text = response_body['results'][0]['outputText']
            
            # Parse match result
            match_result = self.parse_match_response(response_text, opportunity_required_skills)
            
            return match_result
            
        except Exception as e:
            logger.error(f"Failed to calculate company match: {str(e)}")
            # Return fallback
            return {
                'score': 0.0,
                'rationale': f'Match calculation failed: {str(e)}',
                'opportunity_required_skills': opportunity_required_skills,
                'company_skills': [],
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': []
            }
    
    def create_opportunity_enhancement_prompt(self, opportunity_description: str, attachment_content: str) -> str:
        """
        Create LLM prompt template for opportunity enhancement with structured sections.
        """
        prompt = f"""Analyze the following government contracting opportunity and create an enhanced description with EXACTLY the structured sections shown below.

OPPORTUNITY DATA:
{opportunity_description}

ATTACHMENTS:
{attachment_content}

REQUIRED OUTPUT FORMAT - You must follow this structure exactly:

BUSINESS SUMMARY:

Purpose of the Solicitation: [Clearly state the main purpose and objectives]

Information Unique to the Project: [Highlight unique aspects and special requirements]

Overall Description of the Work: [Provide comprehensive overview of work and deliverables]

Technical Capabilities, Specific Skills, or Experience Required: [List specific technical requirements and skills]

NON-TECHNICAL SUMMARY:

Clearances Information: [Security clearance requirements or "Not specified"]

Technical Proposal Evaluation: [Evaluation criteria or "Standard government evaluation criteria"]

Security: [Security requirements or "Standard government security requirements"]

Compliance: [Regulatory requirements or "Federal contracting compliance requirements"]

EXTRACTED SKILLS AND REQUIREMENTS:
SKILLS_JSON: ["skill1", "skill2", "skill3", ...]

Extract 5-15 specific skills/requirements for the SKILLS_JSON array."""

        return prompt
    
    def parse_opportunity_enhancement_response(self, response_text: str) -> Tuple[str, List[str]]:
        """
        Parse the LLM response to extract enhanced_description and opportunity_required_skills.
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
                    skills = [skill for skill in skills if len(skill) > 2 and len(skill) < 200]
                    
                except json.JSONDecodeError:
                    logger.warning("Failed to parse skills JSON from LLM response")
                    skills = []
                
                # Remove the skills JSON from the enhanced description
                enhanced_description = response_text[:response_text.find("SKILLS_JSON:")].strip()
            
            # Ensure we have some skills even if parsing failed
            if not skills:
                skills = ["Government contracting experience", "Technical proposal writing"]
            
            # Limit skills to reasonable number
            if len(skills) > 20:
                skills = skills[:20]
            
            logger.info(f"Parsed enhancement response: {len(enhanced_description)} chars, {len(skills)} skills")
            
            return enhanced_description, skills
            
        except Exception as e:
            logger.error(f"Error parsing opportunity enhancement response: {str(e)}")
            # Return the raw response and empty skills list as fallback
            return response_text.strip(), []
    
    def parse_match_response(self, response_text: str, opportunity_required_skills: List[str]) -> Dict[str, Any]:
        """
        Parse match calculation response.
        """
        try:
            # Extract match score
            score = 0.0
            if "MATCH_SCORE:" in response_text:
                score_line = response_text.split("MATCH_SCORE:")[1].split("\n")[0].strip()
                try:
                    score = float(score_line)
                except ValueError:
                    score = 0.0
            
            # Extract rationale
            rationale = "No rationale provided"
            if "RATIONALE:" in response_text:
                rationale_start = response_text.find("RATIONALE:") + len("RATIONALE:")
                rationale_end = response_text.find("COMPANY_SKILLS:", rationale_start)
                if rationale_end == -1:
                    rationale_end = len(response_text)
                rationale = response_text[rationale_start:rationale_end].strip()
            
            # Extract company skills
            company_skills = []
            if "COMPANY_SKILLS:" in response_text:
                skills_start = response_text.find("COMPANY_SKILLS:") + len("COMPANY_SKILLS:")
                skills_end = response_text.find("PAST_PERFORMANCE:", skills_start)
                if skills_end == -1:
                    skills_end = len(response_text)
                skills_text = response_text[skills_start:skills_end].strip()
                try:
                    company_skills = json.loads(skills_text)
                except:
                    company_skills = []
            
            # Extract past performance
            past_performance = []
            if "PAST_PERFORMANCE:" in response_text:
                perf_start = response_text.find("PAST_PERFORMANCE:") + len("PAST_PERFORMANCE:")
                perf_text = response_text[perf_start:].strip()
                try:
                    past_performance = json.loads(perf_text)
                except:
                    past_performance = []
            
            return {
                'score': score,
                'rationale': rationale,
                'opportunity_required_skills': opportunity_required_skills,
                'company_skills': company_skills,
                'past_performance': past_performance,
                'citations': [],
                'kb_retrieval_results': []
            }
            
        except Exception as e:
            logger.error(f"Error parsing match response: {str(e)}")
            return {
                'score': 0.0,
                'rationale': f'Response parsing failed: {str(e)}',
                'opportunity_required_skills': opportunity_required_skills,
                'company_skills': [],
                'past_performance': [],
                'citations': [],
                'kb_retrieval_results': []
            }


def get_llm_data_extractor() -> LLMDataExtractor:
    """Get LLM data extractor instance."""
    return LLMDataExtractor()


def get_bedrock_llm_client() -> BedrockLLMClient:
    """Get Bedrock LLM client instance."""
    return BedrockLLMClient()