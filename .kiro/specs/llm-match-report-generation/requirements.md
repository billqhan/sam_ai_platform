# Requirements Document

## Introduction

The sam-sqs-generate-match-reports Lambda function currently outputs hardcoded "debug" test data instead of using AWS Bedrock LLM to analyze opportunity data and generate real match reports. This feature will update the Lambda function to implement the actual AI-powered opportunity matching logic as specified in the original system design, replacing the placeholder debug output with genuine LLM-based analysis.

## Requirements

### Requirement 1

**User Story:** As a business development professional, I want the system to use real AI analysis instead of debug output, so that I receive accurate match scores and rationale based on actual opportunity content.

#### Acceptance Criteria

1. WHEN the Lambda function processes an SQS message THEN it SHALL read the actual opportunity JSON file from S3 instead of using hardcoded data
2. WHEN processing opportunities THEN it SHALL call the Bedrock LLM "Get Opportunity Info" model to extract key information from the opportunity description and attachments
3. WHEN extracting opportunity info THEN it SHALL respect the MAX_DESCRIPTION_CHARS and MAX_ATTACHMENT_CHARS limits from environment variables
4. WHEN processing attachments THEN it SHALL limit processing to MAX_ATTACHMENT_FILES as specified in environment variables
5. WHEN LLM calls fail THEN it SHALL log detailed error information and continue processing other opportunities

### Requirement 2

**User Story:** As a business analyst, I want the system to calculate real match scores using company knowledge base data, so that I can trust the match recommendations for business decisions.

#### Acceptance Criteria

1. WHEN opportunity information is extracted THEN the system SHALL call the Bedrock LLM "Calculate Company Match" model with the extracted data
2. WHEN calculating matches THEN it SHALL query the Company Information Knowledge Base to retrieve relevant company capabilities and include kb_retrieval_results in the output
3. WHEN generating match scores THEN it SHALL return a float value between 0.0 and 1.0 based on actual analysis and store it in the "score" field
4. WHEN generating rationale THEN it SHALL provide detailed reasoning explaining the match assessment, company strengths, and any capability gaps
5. WHEN extracting opportunity data THEN it SHALL parse and include all SAM.gov fields: solicitationNumber, noticeId, title, fullParentPathName, postedDate, type, responseDeadLine, pointOfContact details, placeOfPerformance details, and generate the uiLink
6. WHEN no knowledge base results are retrieved THEN the system SHALL assign a score of 0.0 and provide a rationale explaining that no company information was found to assess the match
7. WHEN knowledge base retrieval fails or returns empty results THEN the system SHALL NOT generate positive match assessments or claim company capabilities that are not supported by actual data

### Requirement 3

**User Story:** As a system administrator, I want the function to handle LLM processing delays and rate limits, so that the system operates reliably under varying loads.

#### Acceptance Criteria

1. WHEN making Bedrock API calls THEN the system SHALL implement the PROCESS_DELAY_SECONDS environment variable to prevent rate limiting
2. WHEN Bedrock API calls are throttled THEN the system SHALL implement exponential backoff retry logic
3. WHEN processing takes longer than expected THEN the system SHALL log progress updates for monitoring
4. WHEN DEBUG_MODE is enabled THEN the system SHALL log detailed request/response information for troubleshooting
5. WHEN LLM processing fails after retries THEN the system SHALL create an error record in the errors folder

### Requirement 4

**User Story:** As a business development manager, I want the output format to include comprehensive opportunity and match data, so that downstream systems have all necessary information for reporting and analysis.

#### Acceptance Criteria

1. WHEN match results are generated THEN they SHALL include all required fields: solicitationNumber, noticeId, title, fullParentPathName, enhanced_description, score, rationale, opportunity_required_skills, company_skills, past_performance, citations, kb_retrieval_results, input_key, timestamp, postedDate, type, responseDeadLine, pointOfContact fields, placeOfPerformance fields, and uiLink
2. WHEN generating enhanced_description THEN it SHALL include structured sections: Business Summary with Purpose, Information Unique to Project, Overall Description of Work, Technical Capabilities Required, and Non-Technical Summary with Clearances, Technical Proposal Evaluation, Security, and Compliance information
3. WHEN creating citations THEN they SHALL include document_title, section_or_page, and excerpt fields from knowledge base retrieval
4. WHEN including kb_retrieval_results THEN they SHALL contain index, title, snippet, source, metadata, and location information from Bedrock knowledge base queries
5. WHEN writing to S3 buckets THEN the system SHALL use the same file naming conventions and folder structure while including the expanded data format

### Requirement 5

**User Story:** As a system operator, I want comprehensive error handling and logging, so that I can troubleshoot issues and monitor system performance effectively.

#### Acceptance Criteria

1. WHEN LLM calls are made THEN the system SHALL log request parameters and response metadata
2. WHEN errors occur during processing THEN the system SHALL log the opportunity ID, error type, and full stack trace
3. WHEN S3 file reading fails THEN the system SHALL log the bucket name, key, and specific error details
4. WHEN knowledge base queries fail THEN the system SHALL log the query parameters and error response
5. WHEN processing completes successfully THEN the system SHALL log processing time, match score, and key extracted information