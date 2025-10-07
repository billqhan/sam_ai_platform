# Requirements Document

## Introduction

The AI-powered RFP Response Agent is a comprehensive data processing pipeline that automatically retrieves government contracting opportunities from SAM.gov, processes and analyzes them against company capabilities, and generates match reports to identify relevant business opportunities. The system leverages AWS services including Lambda, S3, SQS, Bedrock AI, and EventBridge to create an end-to-end automated solution that runs daily and provides real-time matching capabilities.

## Requirements

### Requirement 1

**User Story:** As a business development professional, I want the system to automatically retrieve opportunity data from SAM.gov daily, so that I never miss new contracting opportunities.

#### Acceptance Criteria

1. WHEN the daily cron job triggers THEN the system SHALL call the SAM.gov API at 'https://api.sam.gov/prod/opportunities/v2/search'
2. WHEN the API call completes successfully THEN the system SHALL store the complete response as "SAM Opportunities.json" in the "sam-data-in" S3 bucket
3. WHEN the API call fails THEN the system SHALL log the error to "sam-download-files-logs" and retry up to 1 time
4. WHEN the Lambda function "sam-gov-daily-download" executes THEN it SHALL complete within 15 minutes or timeout gracefully

### Requirement 2

**User Story:** As a system administrator, I want individual opportunity records to be processed separately, so that the system can handle large datasets efficiently and process opportunities in parallel.

#### Acceptance Criteria

1. WHEN a new file is added to "sam-data-in" bucket THEN the system SHALL trigger the "sam-json-processor" Lambda function
2. WHEN the "sam-json-processor" processes the SAM Opportunities.json THEN it SHALL split the file into individual opportunity files using the opportunity_number as the filename prefix
3. WHEN individual opportunity files are created THEN they SHALL be stored in the "sam-extracted-json-resources" S3 bucket
4. WHEN an opportunity contains resource links THEN the system SHALL download all associated files and prefix them with the opportunity_number
5. WHEN file processing fails for any opportunity THEN the system SHALL log the error and continue processing remaining opportunities

### Requirement 3

**User Story:** As a system architect, I want processed opportunities to be queued for AI analysis, so that the system can handle varying loads and process opportunities asynchronously.

#### Acceptance Criteria

1. WHEN a new JSON file is added to "sam-extracted-json-resources" bucket THEN the system SHALL add a message to the "sqs-sam-json-messages" SQS queue
2. WHEN messages are added to the SQS queue THEN they SHALL contain the S3 object key and metadata for the opportunity file
3. WHEN the SQS queue receives messages THEN it SHALL maintain FIFO ordering for processing
4. WHEN SQS message processing fails THEN the system SHALL implement dead letter queue handling after 3 retry attempts

### Requirement 4

**User Story:** As a business analyst, I want the system to maintain a knowledge base of company information, so that opportunities can be matched against our capabilities and expertise.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL create a Bedrock Knowledge Base named "Company Information KB" using S3 as a vector store
2. WHEN company information files are added to "sam-company-info" S3 bucket THEN the knowledge base SHALL automatically index the content using S3 vectors
3. WHEN the knowledge base is queried THEN it SHALL return relevant company capabilities and expertise information from the vector store
4. WHEN knowledge base content is updated THEN the system SHALL re-index within 24 hours

### Requirement 5

**User Story:** As a business development manager, I want the system to extract key information from opportunities and calculate match scores, so that I can focus on the most relevant opportunities.

#### Acceptance Criteria

1. WHEN the "sam-sqs-generate-match-reports" Lambda function processes an SQS message THEN it SHALL read the opportunity JSON and associated files
2. WHEN processing opportunities THEN the system SHALL use batch size of 1 with configurable maximum concurrency between 1 and N
3. WHEN calling the "Get Opportunity Info" Bedrock LLM THEN it SHALL extract key information including requirements, scope, and technical specifications
4. WHEN calling the "Calculate Company Match" Bedrock LLM THEN it SHALL generate a match score using company information from the knowledge base
5. WHEN match processing completes THEN results SHALL be written to "sam-matching-out-sqs" S3 bucket and run summaries to "s3://sam-matching-out-runs/runs/"

### Requirement 6

**User Story:** As a business development professional, I want match results to be categorized by score threshold, so that I can prioritize high-value opportunities.

#### Acceptance Criteria

1. WHEN a match score is above the configured threshold THEN the opportunity SHALL be stored in "s3://sam-matching-out-sqs/YYYY-MM-DD/matches/" folder with filename "<solicitation_id>.json"
2. WHEN a match score is below the configured threshold THEN the opportunity SHALL be stored in "s3://sam-matching-out-sqs/YYYY-MM-DD/no_matches/" folder with filename "<solicitation_id>.json"
3. WHEN processing errors occur THEN error details SHALL be stored in "s3://sam-matching-out-sqs/YYYY-MM-DD/errors/" folder
4. WHEN processing completes for any opportunity THEN an individual summary SHALL be written to "s3://sam-matching-out-runs/runs/" folder
5. WHEN storing results THEN each file SHALL include timestamp, opportunity number, match score, and key extracted information

### Requirement 7

**User Story:** As a system administrator, I want daily run results to be aggregated and archived, so that I can track system performance and maintain historical data.

#### Acceptance Criteria

1. WHEN the EventBridge event "sam-lambda-every-5min-summarizer" triggers THEN it SHALL run every 5 minutes
2. WHEN the "sam-merge-and-archive-result-logs" Lambda function executes THEN it SHALL read all result files from "s3://sam-matching-out-runs/runs/" generated in the last 5 minutes
3. WHEN generating summaries THEN the system SHALL aggregate all runs into a single file in "s3://sam-matching-out-runs/runs/" with format "YYYYMMDDtHHMMZ.json"
4. WHEN archiving THEN individual result files SHALL be moved to the "archive/" folder after summary generation
5. WHEN archiving fails THEN the system SHALL log errors and retain original files

### Requirement 8

**User Story:** As a business development professional, I want readable reports generated for matched opportunities, so that I can quickly review opportunity details and have templates for outreach.

#### Acceptance Criteria

1. WHEN a new "<solicitation_id>.json" file appears in "s3://sam-matching-out-sqs/YYYY-MM-DD/" THEN the "sam-produce-user-report" Lambda function SHALL be triggered
2. WHEN the Lambda function processes an opportunity THEN it SHALL generate both a simple text file and a Microsoft .docx file
3. WHEN generating reports THEN they SHALL contain a summary of the match results and reasoning
4. WHEN generating reports THEN they SHALL include a potential email template to the SAM solicitation POC expressing company interest
5. WHEN reports are generated THEN they SHALL be stored in "s3://sam-opportunity-responses" bucket

### Requirement 9

**User Story:** As a business stakeholder, I want a web-based summary of daily results, so that I can quickly review opportunity matches and system performance.

#### Acceptance Criteria

1. WHEN a new run results file matching format "s3://sam-matching-out-runs/runs/2*.json" is created THEN the "sam-produce-web-reports" Lambda function SHALL be triggered
2. WHEN generating the webpage THEN it SHALL look for all runs with the same date prefix (YYYYMMDD) in "s3://sam-matching-out-runs/runs/"
3. WHEN aggregating data THEN it SHALL combine all previous run results for that day
4. WHEN the webpage is created THEN it SHALL be stored in "s3://sam-website/dashboards/" with filename "Summary_YYYYMMDD.html"
5. WHEN the webpage loads THEN it SHALL display match statistics, top opportunities, and system performance metrics
6. WHEN webpage generation fails THEN the system SHALL log errors and use a default template

### Requirement 10

**User Story:** As a system administrator, I want comprehensive logging and monitoring, so that I can troubleshoot issues and ensure system reliability.

#### Acceptance Criteria

1. WHEN any Lambda function executes THEN it SHALL log start time, end time, and execution status
2. WHEN errors occur THEN the system SHALL log detailed error messages with context and stack traces
3. WHEN API calls are made THEN the system SHALL log request/response details for debugging
4. WHEN S3 operations occur THEN the system SHALL log bucket names, object keys, and operation results
5. WHEN SQS messages are processed THEN the system SHALL log message IDs and processing outcomes

### Requirement 11

**User Story:** As a security administrator, I want the system to follow AWS security best practices, so that sensitive data is protected and access is properly controlled.

#### Acceptance Criteria

1. WHEN Lambda functions access AWS services THEN they SHALL use IAM roles with least privilege permissions
2. WHEN data is stored in S3 THEN it SHALL be encrypted at rest using AWS KMS
3. WHEN API calls are made to SAM.gov THEN they SHALL use secure HTTPS connections
4. WHEN SQS messages are processed THEN they SHALL be encrypted in transit and at rest
5. WHEN Bedrock AI services are used THEN they SHALL not log or store sensitive company information