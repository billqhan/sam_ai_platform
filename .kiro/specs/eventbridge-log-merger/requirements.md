# Requirements Document

## Introduction

This feature involves deploying an existing Lambda function that merges and archives result logs from S3 on a scheduled basis. The Lambda function processes files from the `runs/raw/` prefix, merges them into summary files, and moves processed files to an archive location. The function needs to be triggered by EventBridge every 5 minutes to ensure timely processing of log data.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the log merger Lambda function deployed with EventBridge scheduling, so that result logs are automatically processed every 5 minutes without manual intervention.

#### Acceptance Criteria

1. WHEN the EventBridge rule triggers THEN the Lambda function SHALL execute successfully
2. WHEN the Lambda function executes THEN it SHALL process files from the `runs/raw/` S3 prefix
3. WHEN files are processed THEN they SHALL be merged into summary JSON files in the `runs/` prefix
4. WHEN processing is complete THEN processed files SHALL be moved to the `runs/archive/` prefix
5. WHEN the EventBridge rule is configured THEN it SHALL trigger every 5 minutes using a cron expression

### Requirement 2

**User Story:** As a developer, I want the Lambda function properly configured with environment variables, so that it can access the correct S3 bucket and operate in active mode.

#### Acceptance Criteria

1. WHEN the Lambda function is deployed THEN it SHALL have the `S3_OUT_BUCKET` environment variable set to `ktest-sam-matching-out-runs-dev`
2. WHEN the Lambda function is deployed THEN it SHALL have the `active` environment variable set to `true`
3. WHEN the Lambda function executes THEN it SHALL have appropriate IAM permissions to read, write, and delete objects in the S3 bucket
4. WHEN the Lambda function processes files THEN it SHALL only process files modified within the last 5-minute time bucket

### Requirement 3

**User Story:** As a system operator, I want the deployment integrated into the existing infrastructure, so that it follows the same patterns and can be managed consistently.

#### Acceptance Criteria

1. WHEN the deployment is created THEN it SHALL use AWS SAM or CloudFormation templates consistent with the existing infrastructure
2. WHEN the Lambda function is deployed THEN it SHALL be named appropriately to indicate its log merging purpose
3. WHEN the EventBridge rule is created THEN it SHALL be named descriptively and associated with the Lambda function
4. WHEN the deployment completes THEN all resources SHALL be properly tagged for identification and management

### Requirement 4

**User Story:** As a monitoring team member, I want proper logging and error handling, so that I can track the function's performance and troubleshoot issues.

#### Acceptance Criteria

1. WHEN the Lambda function executes THEN it SHALL log the number of records processed and archived
2. WHEN no files are found for processing THEN the function SHALL log this condition appropriately
3. WHEN the function is inactive THEN it SHALL return a status indicating it's not active
4. WHEN errors occur during processing THEN they SHALL be handled gracefully without stopping the entire process
5. WHEN the function completes THEN it SHALL return a structured response with processing statistics