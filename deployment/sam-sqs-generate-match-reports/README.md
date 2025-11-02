# SAM SQS Generate Match Reports Lambda Deployment

This directory contains the deployment package for the `sam-sqs-generate-match-reports` Lambda function with full LLM integration.

## Files Included

### Core Lambda Files
- `lambda_function.py` - Main Lambda handler with LLM integration
- `requirements.txt` - Python dependencies

### Shared Modules
- `shared/__init__.py` - Shared module initialization
- `shared/config.py` - Configuration management
- `shared/aws_clients.py` - AWS service clients
- `shared/error_handling.py` - Error handling utilities
- `shared/logging_config.py` - Structured logging
- `shared/tracing.py` - X-Ray tracing utilities
- `shared/llm_data_extraction.py` - LLM and data extraction utilities

### Deployment Scripts
- `deploy.ps1` - PowerShell deployment script
- `README.md` - This file

## Features

This Lambda function provides:

✅ **Full LLM Integration** - Uses Amazon Bedrock for AI-powered opportunity matching
✅ **Comprehensive Error Handling** - Graceful degradation and detailed error logging
✅ **S3 Data Processing** - Reads opportunities and attachments from S3
✅ **Structured Output** - Creates properly formatted match results
✅ **Environment Configuration** - Configurable via environment variables
✅ **X-Ray Tracing** - Full observability support

## Deployment Instructions

### Option 1: Using PowerShell Script (Recommended)

1. Open PowerShell in this directory
2. Run the deployment script:
   ```powershell
   .\deploy.ps1
   ```
3. Follow the instructions provided by the script

### Option 2: Manual Deployment

1. **Create deployment package:**
   ```powershell
   Compress-Archive -Path lambda_function.py,requirements.txt,shared -DestinationPath lambda-deployment-package.zip
   ```

2. **Upload to AWS Lambda:**
   ```bash
   aws lambda update-function-code \
     --function-name ktest-sam-sqs-generate-match-reports-dev \
     --zip-file fileb://lambda-deployment-package.zip \
     --region us-east-1
   ```

3. **Or use AWS Console:**
   - Go to AWS Lambda Console
   - Find your function: `ktest-sam-sqs-generate-match-reports-dev`
   - Upload the `lambda-deployment-package.zip` file

## Required Environment Variables

Ensure these environment variables are configured in your Lambda function:

### S3 Configuration
- `OUTPUT_BUCKET_SQS` - S3 bucket for match results (e.g., `ktest-sam-matching-out-sqs-dev`)
- `OUTPUT_BUCKET_RUNS` - S3 bucket for run summaries (e.g., `ktest-sam-matching-out-runs-dev`)

### Bedrock Configuration
- `MODEL_ID_DESC` - Model for opportunity description enhancement (default: `anthropic.claude-3-sonnet-20240229-v1:0`)
- `MODEL_ID_MATCH` - Model for company matching (default: `anthropic.claude-3-sonnet-20240229-v1:0`)
- `BEDROCK_REGION` - Bedrock region (default: `us-east-1`)
- `KNOWLEDGE_BASE_ID` - Optional knowledge base ID
- `MAX_TOKENS` - Maximum tokens per request (default: `4000`)
- `TEMPERATURE` - Model temperature (default: `0.1`)

### Processing Configuration
- `MATCH_THRESHOLD` - Match score threshold (default: `0.7`)
- `MAX_ATTACHMENT_FILES` - Maximum attachment files to process (default: `4`)
- `MAX_DESCRIPTION_CHARS` - Maximum description characters (default: `20000`)
- `MAX_ATTACHMENT_CHARS` - Maximum attachment characters (default: `16000`)
- `PROCESS_DELAY_SECONDS` - Processing delay for rate limiting (default: `60`)

### Debug Configuration
- `DEBUG_MODE` - Enable debug logging (default: `true`)

## Lambda Configuration Requirements

### Runtime Settings
- **Runtime:** Python 3.11
- **Handler:** `lambda_function.lambda_handler`
- **Memory:** 2048 MB (recommended)
- **Timeout:** 30 seconds (must be less than SQS visibility timeout)

### IAM Permissions Required
Your Lambda execution role needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-input-bucket/*",
                "arn:aws:s3:::your-output-bucket/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:Retrieve"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes"
            ],
            "Resource": "arn:aws:sqs:*:*:your-queue-name"
        }
    ]
}
```

## Testing

After deployment, you can test the function by:

1. **SQS Message Test:** Send a test SQS message with S3 event data
2. **CloudWatch Logs:** Monitor logs for processing details
3. **S3 Output:** Check output buckets for generated match results

## Troubleshooting

### Common Issues

1. **Import Errors:** Ensure all shared modules are included in the deployment package
2. **Permission Errors:** Verify IAM role has required permissions
3. **Timeout Errors:** Increase Lambda timeout if processing takes longer
4. **Memory Errors:** Increase Lambda memory allocation
5. **Bedrock Errors:** Ensure Bedrock models are available in your region

### Debug Mode

Enable debug mode by setting `DEBUG_MODE=true` for detailed logging:
- LLM request/response details
- S3 operation details
- Processing stage information
- Error stack traces

## Architecture

```
SQS Message → Lambda Function → Bedrock LLM → S3 Output
     ↓              ↓              ↓           ↓
S3 Event      Process Opportunity  AI Analysis  Match Results
```

The function processes opportunities through these stages:
1. Parse SQS message for S3 event
2. Read opportunity data and attachments from S3
3. Enhance description using Bedrock LLM
4. Calculate company match score using LLM
5. Write structured results to output S3 buckets

## Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Verify environment variables are set correctly
3. Ensure IAM permissions are configured
4. Test with debug mode enabled