# Implementation Plan

- [x] 1. Set up LLM service integration and data extraction utilities





  - Create Bedrock client initialization with proper error handling
  - Implement S3 data reader for opportunity JSON and attachment files
  - Add content truncation logic based on MAX_DESCRIPTION_CHARS and MAX_ATTACHMENT_CHARS environment variables
  - Implement attachment file limiting based on MAX_ATTACHMENT_FILES environment variable
  - _Requirements: 1.1, 1.3, 1.4_

- [x] 2. Implement opportunity information extraction using Bedrock LLM





  - Create LLM prompt template for opportunity enhancement with structured Business Summary and Non-Technical Summary sections
  - Implement Bedrock API call for "Get Opportunity Info" using MODEL_ID_DESC environment variable
  - Add response parsing to extract enhanced_description and opportunity_required_skills
  - Implement retry logic with exponential backoff for LLM API calls
  - Add PROCESS_DELAY_SECONDS rate limiting between API calls
  - _Requirements: 1.2, 3.1, 3.2, 4.2_

- [x] 3. Implement Knowledge Base integration and company matching









  - Create Knowledge Base query service using KNOWLEDGE_BASE_ID environment variable
  - Implement company capability retrieval with proper kb_retrieval_results formatting
  - Create LLM prompt template for company matching analysis
  - Implement Bedrock API call for "Calculate Company Match" using MODEL_ID_MATCH environment variable
  - Add response parsing for match score, rationale, company_skills, and citations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.3, 4.4_
-

- [x] 4. Parse and extract SAM.gov opportunity metadata




  - Implement extraction of solicitationNumber, noticeId, title, fullParentPathName from opportunity JSON
  - Add parsing for postedDate, type, responseDeadLine fields
  - Extract pointOfContact details (fullName, email, phone)
  - Extract placeOfPerformance details (city.name, state.name, country.name)
  - Generate uiLink using SAM.gov URL pattern with noticeId
  - _Requirements: 2.5, 4.1_

- [x] 5. Update output format to match comprehensive requirements











  - Modify match result JSON structure to include all required fields from examples
  - Ensure enhanced_description includes structured Business Summary and Non-Technical Summary
  - Add kb_retrieval_results with index, title, snippet, source, metadata, and location fields
  - Include input_key, timestamp, and all SAM.gov metadata fields
  - Maintain backward compatibility with existing S3 bucket structure and file naming
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 6. Implement comprehensive error handling and logging







  - Add detailed logging for LLM request/response when DEBUG_MODE is enabled
  - Implement error categorization (data_access, llm_processing, knowledge_base)
  - Create error record format for failed processing with opportunity ID and error details
  - Add progress logging for monitoring long-running processes
  - Implement graceful degradation when partial data is available
  - _Requirements: 1.5, 3.3, 3.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 7. Add unit tests for LLM integration components












  - Write unit tests for Bedrock client initialization and error handling
  - Create unit tests for opportunity data extraction with various file formats
  - Test LLM prompt generation and response parsing
  - Write unit tests for Knowledge Base query formatting and response handling
  - Test error handling scenarios and retry logic
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2_

- [x] 8. Fix hallucination issue when no knowledge base data is available
  - Implement validation to check if kb_retrieval_results is empty before generating match rationale
  - Add logic to set score to 0.0 when no company information is retrieved from knowledge base
  - Update LLM prompts to explicitly instruct against making up company capabilities
  - Add fallback rationale explaining lack of company data when kb_retrieval_results is empty
  - Implement validation in company match calculation to prevent positive assessments without supporting data
  - _Requirements: 2.6, 2.7_

- [ ]* 9. Add integration tests for end-to-end processing
  - Create integration tests with mock Bedrock responses
  - Test complete SQS message processing workflow
  - Validate output format matches required JSON structure
  - Test error scenarios with malformed data and API failures
  - Verify S3 output compatibility with downstream systems
  - _Requirements: 4.1, 4.5, 5.1, 5.2_