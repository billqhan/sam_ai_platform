# AI-powered RFP Response Agent - CloudFormation Infrastructure

This directory contains AWS CloudFormation templates for deploying the AI-powered RFP Response Agent infrastructure.

## Architecture Overview

The infrastructure is organized into multiple nested CloudFormation stacks:

1. **Main Infrastructure Stack** (`main-template.yaml`) - S3 buckets and SQS queue
2. **DynamoDB Tables Stack** (`dynamodb-tables.yaml`) - Opportunities, Matches, Reports tables + GSIs
3. **Lambda Functions Stack** (`lambda-functions.yaml`) - All Lambda functions and IAM roles
4. **EventBridge Rules Stack** (`eventbridge-rules.yaml`) - Scheduled triggers
5. **S3 Bucket Policies Stack** (`s3-bucket-policies.yaml`) - Security policies and permissions
6. **S3 Event Notifications Stack** (`s3-event-notifications.yaml`) - S3 event triggers
7. **Master Template** (`master-template.yaml`) - Orchestrates all nested stacks

## Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **SAM.gov API Key** - Register at https://api.sam.gov/
3. **S3 Bucket** for storing CloudFormation templates
4. **Bedrock Access** - Ensure your AWS account has access to Amazon Bedrock in us-east-1

## Deployment Steps

### 1. Upload Templates to S3

First, create an S3 bucket for your CloudFormation templates and upload all template files:

```bash
# Create S3 bucket for templates (replace with your bucket name)
aws s3 mb s3://your-cloudformation-templates-bucket

# Upload all templates
aws s3 cp . s3://your-cloudformation-templates-bucket/ai-rfp-response-agent/ --recursive --exclude "*.md" --exclude "*.json"
```

### 2. Update Parameters

Edit the parameter files for your environment:

- `parameters-dev.json` - Development environment
- `parameters-prod.json` - Production environment

Update the following values:
- `SamApiKey` - Your SAM.gov API key
- `CompanyName` - Your company name for reports
- `CompanyContact` - Your contact information
- `TemplatesBucketName` - The S3 bucket containing your templates

### 3. Deploy the Stack

Deploy using the AWS CLI:

```bash
# Deploy development environment
aws cloudformation create-stack \
  --stack-name ai-rfp-response-agent-dev \
  --template-url https://your-cloudformation-templates-bucket.s3.amazonaws.com/ai-rfp-response-agent/master-template.yaml \
  --parameters file://parameters-dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Deploy production environment
aws cloudformation create-stack \
  --stack-name ai-rfp-response-agent-prod \
  --template-url https://your-cloudformation-templates-bucket.s3.amazonaws.com/ai-rfp-response-agent/master-template.yaml \
  --parameters file://parameters-prod.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### 4. Monitor Deployment

Monitor the deployment progress:

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name ai-rfp-response-agent-dev --region us-east-1

# Watch stack events
aws cloudformation describe-stack-events --stack-name ai-rfp-response-agent-dev --region us-east-1
```

### 5. Post-Deployment Configuration

After successful deployment:

1. **Upload Company Information** - Add your company documents to the `sam-company-info-{environment}` S3 bucket
2. **Configure Bedrock Knowledge Base** - The Knowledge Base ID will need to be updated in the Lambda function environment variables
3. **Test the Pipeline** - Trigger the daily download Lambda function manually to test the pipeline

## Stack Outputs

The master stack provides the following outputs:

- `SamDataInBucketName` - Name of the SAM data input bucket
- `SamExtractedJsonResourcesBucketName` - Name of the extracted JSON resources bucket
- `SqsSamJsonMessagesQueueUrl` - URL of the SQS queue for JSON messages
- `SamGovDailyDownloadFunctionArn` - ARN of the daily download Lambda function
- `SamJsonProcessorFunctionArn` - ARN of the JSON processor Lambda function

## Resource Naming Convention

All resources are named with the pattern: `{resource-name}-{environment}`

For example:
- Development: `sam-data-in-dev`, `sam-json-processor-dev`
- Production: `sam-data-in-prod`, `sam-json-processor-prod`

## Security Considerations

- All S3 buckets use AES-256 encryption
- Lambda functions use least-privilege IAM roles
- SQS queues are encrypted with AWS managed keys
- API keys are stored as NoEcho parameters

## Troubleshooting

### Common Issues

1. **Template Upload Errors** - Ensure your S3 bucket allows public read access for CloudFormation
2. **IAM Permission Errors** - Ensure your AWS credentials have CloudFormation and service creation permissions
3. **Bedrock Access** - Ensure your account has Bedrock access in us-east-1 region
4. **Circular Dependencies** - The templates are designed to avoid circular dependencies through proper stack ordering

### Stack Deletion

To delete the entire infrastructure:

```bash
aws cloudformation delete-stack --stack-name ai-rfp-response-agent-dev --region us-east-1
```

**Note**: Some resources like S3 buckets with content may need to be emptied manually before deletion.

## Cost Optimization

- S3 buckets include lifecycle policies to reduce storage costs
- Lambda functions are right-sized for their workloads
- SQS queues use standard queues (not FIFO) for cost efficiency
- EventBridge rules are optimized for minimal triggers

## Monitoring and Logging

All Lambda functions include:
- CloudWatch Logs integration
- Structured logging for debugging
- Error handling and retry logic
- Performance metrics collection

## Support

For issues with the infrastructure deployment, check:
1. CloudFormation stack events for detailed error messages
2. CloudWatch Logs for Lambda function execution logs
3. AWS Service Health Dashboard for service availability