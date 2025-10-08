# Implementation Plan

- [x] 1. Set up project structure and core utilities







  - Create directory structure for Lambda functions, shared libraries, and infrastructure code
  - Implement shared utilities for AWS service clients, logging, and error handling
  - Create configuration management for environment variables and constants
  - _Requirements: 9.1, 9.2, 9.3, 10.1_

- [x] 2. Implement SAM.gov data retrieval Lambda function















  - [x] 2.1 Create sam-gov-daily-download Lambda function structure


    - Set up Python project with requirements.txt and handler function
    - Implement environment variable configuration and validation
    - Create basic Lambda handler structure with error handling
    - _Requirements: 1.1, 1.4_
  
  - [x] 2.2 Implement SAM.gov API client


    - Create HTTP client for SAM.gov API with authentication
    - Implement API request formatting with date parameters and limits
    - Add support for custom date overrides (OVERRIDE_POSTED_FROM/TO)
    - Handle API response parsing and validation
    - _Requirements: 1.1, 1.2_
  
  - [x] 2.3 Implement S3 storage and logging


    - Create S3 client for storing SAM opportunities JSON
    - Implement error logging to sam-download-files-logs bucket
    - Add retry logic with exponential backoff (1 retry maximum)
    - _Requirements: 1.2, 1.3_
  
  - [ ]* 2.4 Write unit tests for SAM.gov data retrieval
    - Test API client with mocked responses
    - Test S3 storage operations and error handling
    - Test retry logic and timeout scenarios
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 3. Implement opportunity processing Lambda function





  - [x] 3.1 Create sam-json-processor Lambda function structure


    - Set up Python project with enhanced memory and ephemeral storage configuration
    - Implement S3 event trigger handling and JSON parsing
    - Create SamJsonProcessorRole IAM role integration
    - _Requirements: 2.1, 2.5_
  
  - [x] 3.2 Implement opportunity splitting logic


    - Parse SAM opportunities JSON and extract individual opportunities
    - Create individual opportunity files with opportunity_number prefix
    - Implement concurrent processing for multiple opportunities
    - _Requirements: 2.2, 2.3_
  
  - [x] 3.3 Implement resource file downloading


    - Download associated files from resource_links in opportunities
    - Apply opportunity_number prefix to all downloaded files
    - Handle download failures gracefully and continue processing
    - Store processed files in sam-extracted-json-resources bucket
    - _Requirements: 2.4, 2.5_
  
  - [ ] 3.4 Write unit tests for opportunity processing





    - Test JSON parsing and opportunity extraction
    - Test file downloading with mocked HTTP responses
    - Test error handling for malformed data
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 4. Implement SQS message queuing system






  - [x] 4.1 Create SQS queue configuration and S3 event integration


    - Set up sqs-sam-json-messages queue with dead letter queue
    - Configure S3 event notifications to trigger SQS messages
    - Implement message formatting with S3 object metadata
    - _Requirements: 3.1, 3.2, 3.4_
  

  - [x] 4.2 Implement SQS message processing utilities

    - Create SQS client for message handling in Lambda functions
    - Implement message parsing and validation
    - Add error handling and dead letter queue integration
    - _Requirements: 3.3, 3.4_
  

  - [x]* 4.3 Write unit tests for SQS integration




    - Test message formatting and parsing
    - Test error handling and retry logic
    - Test dead letter queue functionality
    - _Requirements: 3.1, 3.2, 3.4_

- [x] 5. Set up Bedrock Knowledge Base and AI integration





  - [x] 5.1 Create Company Information Knowledge Base


    - Set up Bedrock Knowledge Base with S3 vector store configuration
    - Configure sam-company-info bucket as data source
    - Implement knowledge base indexing and sync scheduling
    - _Requirements: 4.1, 4.2, 4.4_
  
  - [x] 5.2 Implement Bedrock AI client utilities


    - Create Bedrock client for LLM model invocations
    - Implement separate model configurations for description extraction and matching
    - Add token limiting and request throttling (PROCESS_DELAY_SECONDS)
    - Implement knowledge base query functionality
    - _Requirements: 5.3, 5.4_
  
  - [ ]* 5.3 Write unit tests for Bedrock integration

    - Test knowledge base queries with mocked responses
    - Test LLM model invocations and response parsing
    - Test token limiting and throttling mechanisms
    - _Requirements: 4.3, 5.3, 5.4_








- [ ] 6. Implement AI-powered opportunity matching Lambda function

  - [x] 6.1 Create sam-sqs-generate-match-reports Lambda function structure


    - Set up Lambda function with SQS trigger and batch processing
    - Implement environment variable configuration for limits and models
    - Create debug mode logging and processing delay functionality
    - _Requirements: 5.1, 5.2_
  


  - [x] 6.2 Implement opportunity information extraction


    - Create "Get Opportunity Info" LLM processing using MODEL_ID_DESC
    - Extract key requirements, scope, and technical specifications
    - Implement character limits for descriptions (MAX_DESCRIPTION_CHARS)
    - Handle attachment processing with file limits (MAX_ATTACHMENT_FILES, MAX_ATTACHMENT_CHARS)


    - _Requirements: 5.3_

  
  - [-] 6.3 Implement company matching logic

    - Create "Calculate Company Match" LLM processing using MODEL_ID_MATCH
    - Query Company Information Knowledge Base for relevant capabilities
    - Generate match score and detailed rationale with citations
    - Extract opportunity required skills and company skills

    - _Requirements: 5.4_
  
  - [ ] 6.4 Implement result storage and categorization
    - Store match results in date-based folder structure (YYYY-MM-DD)
    - Categorize results into matches/, no_matches/, and errors/ folders
    - Generate run summaries for sam-matching-out-runs bucket
    - Implement the updated Match Result JSON structure with citations
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ]* 6.5 Write unit tests for AI matching

    - Test opportunity information extraction with sample data
    - Test company matching logic and score calculation
    - Test result categorization and storage
    - Test error handling for AI processing failures
    - _Requirements: 5.3, 5.4, 6.1, 6.2_

- [x] 7. Implement user report generation Lambda function









  - [x] 7.1 Create sam-produce-user-report Lambda function structure




    - Set up Lambda function with S3 trigger for match results
    - Implement document generation dependencies (python-docx)
    - Create template management for text and Word documents
    - _Requirements: 8.1, 8.2_
  
  - [x] 7.2 Implement report generation logic




    - Parse match result JSON and extract key information
    - Generate readable text summary with match reasoning and details
    - Create Microsoft Word document with formatted content
    - Generate email template for SAM solicitation POC outreach
    - _Requirements: 8.3, 8.4_
  
  - [x] 7.3 Implement report storage




    - Store generated reports in sam-opportunity-responses bucket
    - Organize files by solicitation ID with proper naming conventions
    - Handle file generation errors and logging
    - _Requirements: 8.5_
  
  - [ ]* 7.4 Write unit tests for report generation
    - Test text and Word document generation
    - Test email template creation
    - Test file storage and error handling
    - _Requirements: 8.2, 8.3, 8.4_

- [x] 8. Implement result aggregation and archiving Lambda function



  - [x] 8.1 Create sam-merge-and-archive-result-logs Lambda function structure


    - Set up Lambda function with EventBridge trigger (5-minute schedule)
    - Configure optimized memory (128 MB) and ephemeral storage (512 MB)
    - Implement time-based file processing logic
    - _Requirements: 7.1, 7.2_

  
  - [x] 8.2 Implement run result aggregation

    - Read individual run files from sam-matching-out-runs/runs/ folder
    - Aggregate results from the last 5 minutes into consolidated report
    - Generate summary statistics and top matches
    - Create timestamped aggregate file (YYYYMMDDtHHMMZ.json format)
    - _Requirements: 7.2, 7.3_
  
  - [x] 8.3 Implement archiving functionality


    - Move processed individual run files to archive/ folder
    - Handle file operations with error logging and rollback
    - Implement cleanup for failed operations
    - _Requirements: 7.4, 7.5_
  
  - [ ]* 8.4 Write unit tests for aggregation and archiving
    - Test run result parsing and aggregation logic
    - Test file archiving and cleanup operations
    - Test error handling and rollback scenarios
    - _Requirements: 7.2, 7.3, 7.4_

- [x] 9. Implement web dashboard generation Lambda function







  - [x] 9.1 Create sam-produce-web-reports Lambda function structure



    - Set up Lambda function with S3 trigger for run result files
    - Implement pattern matching for "2*.json" files in runs/ folder
    - Create HTML template management and generation utilities
    - _Requirements: 9.1, 9.2_
  
  - [x] 9.2 Implement daily dashboard aggregation


    - Parse run result files and extract daily statistics
    - Aggregate all runs with matching date prefix (YYYYMMDD)
    - Generate comprehensive daily performance metrics
    - Create top opportunities and match score distributions
    - _Requirements: 9.2, 9.3_
  
  - [x] 9.3 Implement HTML dashboard generation


    - Create responsive HTML dashboard with CSS styling
    - Display match statistics, top opportunities, and system performance
    - Generate Summary_YYYYMMDD.html files for static website hosting
    - Store dashboards in sam-website/dashboards/ folder
    - _Requirements: 9.4, 9.5_
  
  - [ ]* 9.4 Write unit tests for web dashboard generation
    - Test daily data aggregation and statistics calculation
    - Test HTML generation and template rendering
    - Test file storage and website integration
    - _Requirements: 9.2, 9.3, 9.4_

- [x] 10. Implement infrastructure as code and deployment




  - [x] 10.1 Create AWS CloudFormation or CDK templates


    - Define all S3 buckets with proper configurations and lifecycle policies
    - Create Lambda functions with correct memory, timeout, and environment variables
    - Set up SQS queue with dead letter queue configuration
    - Configure EventBridge rules for scheduled triggers
    - _Requirements: All infrastructure requirements_
  
  - [x] 10.2 Implement IAM roles and security policies


    - Create SamJsonProcessorRole and other function-specific IAM roles
    - Implement least privilege access policies for all services
    - Configure S3 bucket policies and encryption settings
    - Set up CloudWatch logging and monitoring permissions
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [x] 10.3 Create deployment scripts and CI/CD pipeline


    - Implement automated deployment scripts for Lambda functions
    - Create package management for Python dependencies
    - Set up environment-specific configuration management
    - Implement rollback and monitoring capabilities
    - _Requirements: 9.1, 9.2_
  
  - [ ]* 10.4 Write integration tests for full system
    - Test end-to-end workflow from SAM.gov retrieval to report generation
    - Test error handling and recovery scenarios
    - Test performance under load and concurrent processing
    - _Requirements: All system requirements_
-

- [x] 11. Implement monitoring and alerting




  - [x] 11.1 Create CloudWatch metrics and alarms


    - Set up custom metrics for processing rates, error rates, and match scores
    - Create alarms for high error rates and processing delays
    - Implement cost monitoring and resource utilization tracking
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  


  - [ ] 11.2 Implement structured logging and tracing
    - Add structured JSON logging to all Lambda functions
    - Implement correlation IDs for request tracing
    - Set up X-Ray tracing for end-to-end debugging
    - Create log aggregation and search capabilities
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [ ]* 11.3 Write monitoring and alerting tests
    - Test metric collection and alarm triggering
    - Test log aggregation and correlation ID tracking
    - Test X-Ray tracing and performance monitoring
    - _Requirements: 9.1, 9.2, 9.3, 9.4_