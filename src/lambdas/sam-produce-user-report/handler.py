"""
SAM produce user report Lambda function handler.
Generates readable reports and email templates for matched opportunities using Bedrock Agent.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import unquote_plus
from io import BytesIO

from shared import (
    get_logger, 
    handle_lambda_error, 
    config, 
    aws_clients,
    handle_aws_error,
    RetryableError,
    NonRetryableError
)
from report_generator import ReportGenerator
from template_manager import TemplateManager

logger = get_logger(__name__)

class UserReportHandler:
    """Handler for user report generation from match results using Bedrock Agent."""
    
    def __init__(self):
        self.s3_client = aws_clients.s3
        self.bedrock_agent = aws_clients.bedrock_agent
        self.output_bucket = config.s3.sam_opportunity_responses
        self.company_info = config.get_company_info()
        self.template_manager = TemplateManager()
        self.report_generator = ReportGenerator(self.template_manager, self.company_info)
        
        # Bedrock Agent configuration
        self.agent_id = os.environ["AGENT_ID"]
        self.agent_alias_id = os.environ["AGENT_ALIAS_ID"]
        
        # Output formats configuration
        self.output_formats = os.environ.get('OUTPUT_FORMATS', 'txt,docx').split(',')
    
    @handle_aws_error
    def process_s3_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process S3 PUT event for match result files.
        
        Args:
            event: S3 event containing object information
            
        Returns:
            dict: Processing results summary
        """
        results = {
            'processed_files': 0,
            'successful_reports': 0,
            'failed_reports': 0,
            'errors': []
        }
        
        # Extract S3 records from event
        records = event.get('Records', [])
        if not records:
            logger.warning("No S3 records found in event")
            return results
        
        for record in records:
            try:
                # Parse S3 event record
                s3_info = record.get('s3', {})
                bucket_name = s3_info.get('bucket', {}).get('name')
                object_key = unquote_plus(s3_info.get('object', {}).get('key', ''))
                
                if not bucket_name or not object_key:
                    logger.warning(f"Invalid S3 record format: {record}")
                    continue
                
                logger.info(f"Processing match result file: bucket={bucket_name}, key={object_key}")
                
                # Only process JSON files in the correct structure
                if not self._is_valid_match_result_file(object_key):
                    logger.info("Skipping non-match result file", key=object_key)
                    continue
                
                results['processed_files'] += 1
                
                # Generate reports for this match result
                self._generate_reports_for_file(bucket_name, object_key)
                results['successful_reports'] += 1
                
                logger.info(f"Successfully generated reports: bucket={bucket_name}, key={object_key}")
                
            except Exception as e:
                error_msg = f"Failed to process record: {str(e)}"
                logger.error(f"{error_msg}: record={record}, error={str(e)}")
                results['failed_reports'] += 1
                results['errors'].append(error_msg)
        
        return results
    
    def _is_valid_match_result_file(self, object_key: str) -> bool:
        """
        Check if the S3 object is a valid match result file.
        Uses the pattern from the new code: YYYY-MM-DD/matches/*.json
        
        Args:
            object_key: S3 object key
            
        Returns:
            bool: True if valid match result file
        """
        # Skip if not a JSON file
        if not object_key.lower().endswith('.json'):
            logger.info(f"Skipping non-JSON file: {object_key}")
            return False
        
        # Pattern to match YYYY-MM-DD/matches/ folder structure
        date_matches_pattern = r'^\d{4}-\d{2}-\d{2}/matches/'
        if re.match(date_matches_pattern, object_key):
            logger.info(f"Valid matches path detected: {object_key}")
            return True
        else:
            logger.info(f"Path does not match YYYY-MM-DD/matches/ pattern: {object_key}")
            return False
    
    @handle_aws_error
    def _generate_reports_for_file(self, bucket_name: str, object_key: str) -> None:
        """
        Generate reports for a specific match result file using Bedrock Agent.
        
        Args:
            bucket_name: S3 bucket name
            object_key: S3 object key
        """
        # Download and parse match result JSON
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            match_data = json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            raise RetryableError(f"Failed to download match result file: {str(e)}")
        
        # Extract solicitation ID from the match data
        solicitation_id = match_data.get('solicitationNumber') or match_data.get('solicitation_id')
        if not solicitation_id:
            raise NonRetryableError("Match result missing solicitationNumber or solicitation_id")
        
        logger.info(f"Generating reports for opportunity: solicitation_id={solicitation_id}")
        
        # Generate response template using Bedrock Agent
        response_template = self._generate_response_template(match_data)
        
        # Store reports in the configured formats
        self._save_response_to_s3(response_template, match_data, object_key)
    
    def _call_agent(self, agent_id: str, agent_alias_id: str, prompt: str) -> str:
        """
        Call Bedrock Agent with the given prompt.
        
        Args:
            agent_id: Bedrock Agent ID
            agent_alias_id: Bedrock Agent Alias ID
            prompt: Input prompt for the agent
            
        Returns:
            str: Agent response text
        """
        try:
            resp = self.bedrock_agent.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId="sam-batch",
                inputText=prompt,
                enableTrace=False,
                endSession=False
            )
            
            full_text = ""
            for event in resp.get("completion", []):
                if "chunk" in event:
                    full_text += event["chunk"]["bytes"].decode("utf-8")
            
            return full_text
        except Exception as e:
            logger.error(f"Error calling Bedrock Agent {agent_id}: {str(e)}")
            raise RetryableError(f"Bedrock Agent call failed: {str(e)}")
    
    def _generate_response_template(self, json_data: Dict[str, Any]) -> str:
        """
        Use Amazon Bedrock Agent to generate the response template.
        
        Args:
            json_data: Match result JSON data
            
        Returns:
            str: Generated response template
        """
        # Construct the prompt for Bedrock Agent
        prompt_text = f'''You are a government contracting response assistant. Create exactly two sections based on this JSON data. You MUST fill in all the bullet points with actual data from the JSON.

JSON DATA:
{json.dumps(json_data, indent=2)}

Output exactly this format with ALL data filled in:

**Section 1: Human-Readable Summary (For Sender)**

**Opportunity Overview**
- Solicitation Number: {json_data.get('solicitationNumber', 'Unknown')}
- Title: {json_data.get('title', 'Unknown Title')}
- Agency: {json_data.get('fullParentPathName', 'Unknown Agency')}
- Posted Date: {json_data.get('postedDate', 'Unknown')}
- Response Deadline: {json_data.get('responseDeadLine', 'Unknown')}
- Notice Type: {json_data.get('type', 'Unknown')}
- Notice ID: {json_data.get('noticeId', 'Unknown')}
- SAM.gov Link: {json_data.get('uiLink', 'Not available')}

**What the Government Is Seeking**

{json_data.get('enhanced_description', 'No description available')[:500]}...

**Place of Performance & Point of Contact**
- Location: {json_data.get('placeOfPerformance.city.name', 'Unknown')}, {json_data.get('placeOfPerformance.state.name', 'Unknown')}, {json_data.get('placeOfPerformance.country.name', 'Unknown')}
- Point of Contact: {json_data.get('pointOfContact.fullName', 'Unknown')}
- Email: {json_data.get('pointOfContact.email', 'Unknown')}
- Phone: {json_data.get('pointOfContact.phone', 'Not provided')}

**Match Assessment**
- Match Score: {json_data.get('score', 'N/A')} ({(json_data.get('score', 0) * 100):.1f}%)
- Match Status: {"Matched" if json_data.get('score', 0) >= 0.5 else "Not Matched"}
- Match Rationale: {json_data.get('rationale', 'No rationale provided')}

**Company Data Used in the Match**
- Company Skills: {', '.join(json_data.get('company_skills', []))}
- Opportunity Required Skills: {', '.join(json_data.get('opportunity_required_skills', []))}
- Past Performance: {', '.join(json_data.get('past_performance', []))}
- Knowledge Base Results: {len(json_data.get('kb_retrieval_results', []))} relevant documents found

**Processing Information**
- Input File: {json_data.get('input_key', 'Unknown')}
- Processing Timestamp: {json_data.get('timestamp', 'Unknown')}
- Enhanced Description Length: {len(json_data.get('enhanced_description', ''))} characters
- Citations Count: {len(json_data.get('citations', []))}

**Additional Company Documents**
- Company Capabilities Overview: [Link to PDF document]
- Past Performance Summary: [Link to PDF document]
- Technical Qualifications: [Link to PDF document]

---

**Section 2: Draft Response Template (Formal Email to Government)**

**TO:**
[Extract POC name from JSON]
[Extract agency from JSON]
Email: [Extract email from JSON]

**FROM:**
[Your Name]
[Your Title]
[Your Company Name]
[Your Address]
[Your Phone]
[Your Email]

**DATE:** [Current Date]

**SUBJECT:** Response to Solicitation [Extract solicitation number] - [Extract title]

Dear [Extract POC name],

[Your Company Name] respectfully submits this response to Solicitation [Extract solicitation number], "[Extract title]."

**Company Information**
[Your Company Name] is a qualified contractor with UEI [Your UEI] and CAGE Code [Your CAGE Code]. Our headquarters are located at [Your Company Address]. We maintain all requisite certifications and security clearances necessary for government contracting.

**Statement of Capability**
Our company possesses the technical expertise and experience required for this opportunity. We have demonstrated capabilities in the following areas relevant to your requirements: [Based on company skills from the match, describe your relevant capabilities in paragraph form without bullet points].

**Past Performance and References**
Our track record includes successful completion of similar projects demonstrating our ability to deliver quality results on time and within budget. [Describe relevant past performance based on the match data, or note if establishing initial performance record].

**Technical Approach**
We understand that this opportunity requires [summarize key technical requirements from the enhanced description]. Our approach will leverage our expertise in [relevant company skills] to deliver a comprehensive solution that meets your objectives.

**Conclusion**
[Rewrite the rationale from JSON in formal, confident language]. We are committed to providing exceptional service and look forward to the opportunity to support your mission.

Thank you for your consideration. Please contact me at [Your Phone Number] or [Your Email] for any additional information or clarification.

Respectfully submitted,

[Your Name]
[Your Title]
[Your Company Name]
[Your Phone Number]
[Your Email]

IMPORTANT: Replace ALL bracketed placeholders with actual data from the JSON. Do not leave any [Extract...] or [List...] instructions in the final output. Output must begin directly with "**Section 1:**" and continue with final user-readable text only.'''

        try:
            logger.info(f"Using Bedrock Agent: {self.agent_id}")
            # Call Bedrock Agent
            generated_text = self._call_agent(self.agent_id, self.agent_alias_id, prompt_text)
            
            # Clean up AI thinking traces and meta-commentary
            cleaned_text = self._clean_ai_thinking_traces(generated_text)
            
            logger.info(f"Successfully generated response template using Bedrock Agent {self.agent_id}")
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Error calling Bedrock Agent {self.agent_id}: {str(e)}")
            raise e
    
    def _clean_ai_thinking_traces(self, text: str) -> str:
        """
        Remove AI internal thinking, reasoning, and meta-commentary from the output.
        
        Args:
            text: Raw text from Bedrock Agent
            
        Returns:
            str: Cleaned text
        """
        # Remove common AI thinking patterns
        thinking_patterns = [
            r"Let me think about this.*?\n",
            r"I need to.*?\n",
            r"First, I'll.*?\n",
            r"Now I'll.*?\n",
            r"Looking at this.*?\n",
            r"Based on my analysis.*?\n",
            r"I should.*?\n",
            r"I will.*?\n",
            r"I can see.*?\n",
            r"It appears.*?\n",
            r"I notice.*?\n",
            r"Let me analyze.*?\n",
            r"I'm going to.*?\n",
            r"Here's what I.*?\n",
            r"I understand.*?\n",
            r"From what I can see.*?\n",
            r"Looking at the JSON.*?\n",
            r"Based on the provided information.*?\n",
            r"Let's craft.*?\n",
            r"Here's how.*?\n",
            r"I'll create.*?\n"
        ]
        
        # Remove thinking patterns (case insensitive)
        cleaned_text = text
        for pattern in thinking_patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove text before the first "## Section 1" if it exists
        section_match = re.search(r'## Section 1:', cleaned_text, re.IGNORECASE)
        if section_match:
            cleaned_text = cleaned_text[section_match.start():]
        
        # Remove meta-instructions that look like bullet point lists
        meta_instruction_patterns = [
            r'Section \d+ details?:.*?(?=##|\Z)',
            r'Section \d+ requirements?:.*?(?=##|\Z)',
            r'Here are the details?:.*?(?=##|\Z)',
            r'Details for Section \d+:.*?(?=##|\Z)',
            r'Requirements for Section \d+:.*?(?=##|\Z)',
            r'- [A-Z][^.]*\. [A-Z][^.]*\.[^\n]*\n',
            r'- [A-Z][^:]*:[^\n]*\n'
        ]
        
        for pattern in meta_instruction_patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        # Remove any remaining meta-commentary in parentheses or brackets
        cleaned_text = re.sub(r'\([^)]*thinking[^)]*\)', '', cleaned_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r'\[[^\]]*reasoning[^\]]*\]', '', cleaned_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove standalone instruction lines that start with dashes
        instruction_lines = [
            r'^- [A-Z][^.]*includes.*?\n',
            r'^- [A-Z][^.]*details.*?\n',
            r'^- [A-Z][^.]*provide.*?\n',
            r'^- [A-Z][^.]*list.*?\n',
            r'^- [A-Z][^.]*create.*?\n',
            r'^- [A-Z][^.]*use.*?\n',
            r'^- [A-Z][^.]*write.*?\n',
            r'^- [A-Z][^.]*include.*?\n'
        ]
        
        for pattern in instruction_lines:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove excessive whitespace and clean up formatting
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        # Log if significant cleaning occurred
        original_length = len(text)
        cleaned_length = len(cleaned_text)
        if original_length - cleaned_length > 100:
            logger.info(f"Cleaned AI thinking traces: removed {original_length - cleaned_length} characters")
        
        return cleaned_text
    
    @handle_aws_error
    def _save_response_to_s3(self, response_content: str, json_data: Dict[str, Any], original_key: str) -> None:
        """
        Save the generated response template to S3 in multiple formats with solicitation number prefix.
        
        Args:
            response_content: Generated response template content
            json_data: Original JSON data
            original_key: Original S3 object key
        """
        try:
            solicitation_number = json_data.get('solicitationNumber', 'UNKNOWN')
            
            # Extract prefix (parent folder path) from the original key
            prefix = os.path.dirname(original_key)
            if prefix in ["", "."]:
                prefix = ""
            else:
                prefix = prefix + "/"
            
            # Create output basename with solicitation number prefix
            base_filename = os.path.splitext(os.path.basename(original_key))[0]
            output_basename = f"{solicitation_number}_response_template"
            
            # Metadata
            timestamp = datetime.utcnow().isoformat()
            header = f"""Response Template

Generated: {timestamp}
Source: {solicitation_number}
Match Score: {json_data.get('score', 'N/A')}

---

"""
            
            # Save as TXT (Default)
            if "txt" in self.output_formats:
                txt_filename = f"{prefix}{output_basename}.txt"
                full_content = header + response_content
                
                self.s3_client.put_object(
                    Bucket=self.output_bucket,
                    Key=txt_filename,
                    Body=full_content.encode('utf-8'),
                    ContentType='text/plain',
                    Metadata={
                        'source-file': original_key,
                        'solicitation-number': solicitation_number,
                        'generated-timestamp': timestamp,
                        'match-score': str(json_data.get('score', 'N/A')),
                        'agent-used': self.agent_id
                    }
                )
                logger.info(f"Saved TXT response template: {txt_filename}")
            
            # Save as DOCX
            if "docx" in self.output_formats:
                metadata = {
                    "timestamp": timestamp,
                    "source_file": original_key,
                    "solicitation": solicitation_number,
                    "match_score": str(json_data.get('score', 'N/A')),
                    "agent": self.agent_id,
                }
                
                doc = self.report_generator.generate_docx(response_content, metadata)
                
                # Save DOCX in memory
                byte_stream = BytesIO()
                doc.save(byte_stream)
                byte_stream.seek(0)
                
                docx_filename = f"{prefix}{output_basename}.docx"
                self.s3_client.put_object(
                    Bucket=self.output_bucket,
                    Key=docx_filename,
                    Body=byte_stream.getvalue(),
                    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    Metadata={
                        'source-file': original_key,
                        'solicitation-number': solicitation_number,
                        'generated-timestamp': timestamp,
                        'match-score': str(json_data.get('score', 'N/A')),
                        'agent-used': self.agent_id
                    }
                )
                logger.info(f"Saved DOCX response template with formatting: {docx_filename}")
                
        except Exception as e:
            logger.error(f"Error saving to S3: {str(e)}")
            raise e

# Global handler instance
handler = UserReportHandler()

@handle_lambda_error
def lambda_handler(event, context):
    """
    Lambda handler for user report generation.
    
    Args:
        event: S3 PUT event for match results
        context: Lambda context object
        
    Returns:
        dict: Response with status and processing results
    """
    logger.info(f"Starting user report generation: event={event}")
    
    try:
        # Process the S3 event
        results = handler.process_s3_event(event)
        
        logger.info(f"User report generation completed: results={results}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'User report generation completed successfully',
                'results': results,
                'correlation_id': logger.correlation_id
            })
        }
        
    except Exception as e:
        logger.error(f"User report generation failed: error={str(e)}")
        raise