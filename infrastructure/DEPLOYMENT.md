# Deployment Guide - AI-powered RFP Response Agent

This guide provides comprehensive instructions for deploying the AI-powered RFP Response Agent infrastructure.

## Prerequisites

### Required Tools

- **AWS CLI** v2.0+ configured with appropriate permissions
- **Python** 3.11+ for Lambda function packaging
- **Git** for version control
- **Bash** or **PowerShell** for running deployment scripts

### AWS Permissions

Your AWS credentials must have the following permissions:
- CloudFormation full access
- IAM role creation and management
- S3 bucket creation and management
- Lambda function management
- SQS queue management
- EventBridge rule management
- Bedrock service access
- CloudWatch logs and metrics

### Required Information

Before deployment, gather:
- **SAM.gov API Key** - Register at https://api.sam.gov/
- **Company Name** - For report templates
- **Company Contact Email** - For alerts and templates
- **S3 Bucket Name** - For storing CloudFormation templates
- **Bucket Prefix** (Optional) - Prefix for S3 bucket names to avoid conflicts

## Deployment Methods

### Method 1: Phased Deployment (Recommended for development and troubleshooting)

The phased deployment approach breaks the infrastructure into logical groups, making it faster to test and debug issues:

- **Phase 1**: Core Infrastructure (S3 buckets, SQS queues) - ~2-3 minutes
- **Phase 2**: Lambda Functions (simplified versions) - ~3-5 minutes  
- **Phase 3**: Security & Monitoring (IAM policies, KMS keys) - ~2-3 minutes

**Deploy All Phases:**
```powershell
.\infrastructure\scripts\deploy-all-phases.ps1 `
  -Environment "dev" `
  -TemplatesBucket "your-templates-bucket-name" `
  -SamApiKey "your-sam-api-key" `
  -CompanyName "Your Company Name" `
  -CompanyContact "contact@yourcompany.com" `
  -BucketPrefix "your-prefix"
```

**Deploy Individual Phases:**
```powershell
# Phase 1 only
.\infrastructure\scripts\deploy-all-phases.ps1 -Phase 1 -TemplatesBucket "bucket" -SamApiKey "key" -CompanyName "Company" -CompanyContact "email"

# Phase 2 only (requires Phase 1 to be completed)
.\infrastructure\scripts\deploy-all-phases.ps1 -Phase 2 -TemplatesBucket "bucket" -SamApiKey "key" -CompanyName "Company" -CompanyContact "email"

# Phase 3 only (requires Phase 1 and 2 to be completed)
.\infrastructure\scripts\deploy-all-phases.ps1 -Phase 3 -TemplatesBucket "bucket" -CompanyContact "email"
```

### Method 2: Single Stack Deployment (For production deployments)

#### Step 1: Prepare Templates Bucket

```bash
# Create S3 bucket for CloudFormation templates
aws s3 mb s3://your-templates-bucket-name

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket your-templates-bucket-name \
  --versioning-configuration Status=Enabled
```

#### Step 2: Deploy Infrastructure

**Note:** Use the `-p` (Linux/macOS) or `-BucketPrefix` (Windows) parameter to add a prefix to all S3 bucket and SQS queue names. This helps avoid naming conflicts if you have multiple deployments or existing resources with similar names.

**Linux/macOS:**
```bash
chmod +x infrastructure/scripts/deploy.sh
./infrastructure/scripts/deploy.sh \
  -e dev \
  -b your-templates-bucket-name \
  -k "your-sam-api-key" \
  -n "Your Company Name" \
  -c "contact@yourcompany.com" \
  -p "your-prefix"
```

**Windows PowerShell:**
```powershell
.\infrastructure\scripts\deploy.ps1 `
  -Environment "dev" `
  -TemplatesBucket "your-templates-bucket-name" `
  -SamApiKey "your-sam-api-key" `
  -CompanyName "Your Company Name" `
  -CompanyContact "contact@yourcompany.com" `
  -BucketPrefix "your-prefix"
```

#### Step 3: Post-Deployment Configuration

1. **Upload Company Information:**
   ```bash
   aws s3 cp company-docs/ s3://sam-company-info-dev/ --recursive
   ```

2. **Configure Bedrock Knowledge Base:**
   - Note the Knowledge Base ID from Bedrock console
   - Update Lambda environment variables with the KB ID

3. **Test the Pipeline:**
   ```bash
   aws lambda invoke \
     --function-name sam-gov-daily-download-dev \
     --payload '{}' \
     response.json
   ```

### Method 2: CI/CD Pipeline (GitHub Actions)

#### Step 1: Configure Repository Secrets

In your GitHub repository, add these secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `TEMPLATES_BUCKET`
- `SAM_API_KEY`
- `COMPANY_NAME`
- `COMPANY_CONTACT`

#### Step 2: Trigger Deployment

- **Development:** Push to `develop` branch
- **Staging:** Push to `main` branch
- **Production:** Use workflow dispatch with `prod` environment

#### Step 3: Monitor Deployment

Check the Actions tab in GitHub for deployment status and logs.

## Environment-Specific Configurations

### Development Environment

- **Purpose:** Testing and development
- **Resources:** Minimal configuration for cost optimization
- **Monitoring:** Basic CloudWatch logs
- **Data Retention:** 30 days

### Staging Environment

- **Purpose:** Pre-production testing
- **Resources:** Production-like configuration
- **Monitoring:** Full monitoring and alerting
- **Data Retention:** 90 days

### Production Environment

- **Purpose:** Live system
- **Resources:** Optimized for performance and reliability
- **Monitoring:** Comprehensive monitoring, alerting, and dashboards
- **Data Retention:** 1 year

## Deployment Verification

### 1. Infrastructure Verification

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name ai-rfp-response-agent-dev \
  --query 'Stacks[0].StackStatus'

# List created resources
aws cloudformation list-stack-resources \
  --stack-name ai-rfp-response-agent-dev
```

### 2. Lambda Function Verification

```bash
# List Lambda functions
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `sam-`)].FunctionName'

# Test function invocation
aws lambda invoke \
  --function-name sam-gov-daily-download-dev \
  --payload '{}' \
  response.json && cat response.json
```

### 3. S3 Bucket Verification

```bash
# List created buckets
aws s3 ls | grep sam-

# Check bucket policies
aws s3api get-bucket-policy \
  --bucket sam-data-in-dev
```

### 4. SQS Queue Verification

```bash
# List SQS queues
aws sqs list-queues \
  --query 'QueueUrls[?contains(@, `sam-`)]'

# Check queue attributes
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/sqs-sam-json-messages-dev \
  --attribute-names All
```

## Troubleshooting

### Common Issues

#### 1. CloudFormation Stack Creation Failed

**Symptoms:** Stack creation fails with permission errors
**Solution:**
```bash
# Check IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:user/USERNAME \
  --action-names cloudformation:CreateStack \
  --resource-arns "*"
```

#### 2. Lambda Function Timeout

**Symptoms:** Lambda functions timing out during execution
**Solution:**
- Increase timeout in CloudFormation template
- Check memory allocation
- Review function logs in CloudWatch

#### 3. S3 Event Notifications Not Working

**Symptoms:** Lambda functions not triggered by S3 events
**Solution:**
```bash
# Check bucket notification configuration
aws s3api get-bucket-notification-configuration \
  --bucket sam-data-in-dev

# Verify Lambda permissions
aws lambda get-policy \
  --function-name sam-json-processor-dev
```

#### 4. Bedrock Access Denied

**Symptoms:** Bedrock API calls failing with access denied
**Solution:**
- Ensure Bedrock is enabled in your AWS account
- Check IAM permissions for Bedrock service
- Verify model access in Bedrock console

### Rollback Procedures

#### Automatic Rollback

The deployment script includes automatic rollback on failure:
```bash
./infrastructure/scripts/rollback.sh -e dev -f
```

#### Manual Rollback

```bash
# List stack events to identify issues
aws cloudformation describe-stack-events \
  --stack-name ai-rfp-response-agent-dev

# Continue update rollback if needed
aws cloudformation continue-update-rollback \
  --stack-name ai-rfp-response-agent-dev
```

## Monitoring and Maintenance

### CloudWatch Dashboard

Access the monitoring dashboard:
```
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AI-RFP-Response-Agent-dev
```

### Log Analysis

```bash
# View recent Lambda logs
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/sam-"

# Get recent error logs
aws logs filter-log-events \
  --log-group-name "/aws/lambda/sam-gov-daily-download-dev" \
  --filter-pattern "ERROR"
```

### Cost Monitoring

```bash
# Check estimated monthly costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Security Considerations

### Data Protection

- All S3 buckets use AES-256 encryption
- SQS queues are encrypted with AWS managed keys
- Lambda functions use least-privilege IAM roles
- API keys are stored securely in parameter files

### Access Control

- IAM roles follow principle of least privilege
- S3 bucket policies restrict cross-service access
- CloudWatch logs have appropriate retention policies

### Monitoring

- CloudWatch alarms for error rates and costs
- SNS notifications for critical issues
- Structured logging for security analysis

## Performance Optimization

### Lambda Functions

- Right-sized memory allocation based on workload
- Optimized timeout settings
- Concurrent execution limits to prevent throttling

### S3 Storage

- Lifecycle policies for cost optimization
- Intelligent tiering for frequently accessed data
- Cross-region replication for disaster recovery (if needed)

### Cost Management

- Regular review of resource utilization
- Automated cleanup of temporary resources
- Cost allocation tags for tracking

## Support and Maintenance

### Regular Tasks

- **Weekly:** Review CloudWatch dashboards and alerts
- **Monthly:** Analyze costs and optimize resources
- **Quarterly:** Security review and dependency updates
- **Annually:** Disaster recovery testing

### Getting Help

- **AWS Support:** Use your AWS support plan for infrastructure issues
- **Documentation:** Refer to AWS service documentation
- **Community:** AWS forums and Stack Overflow for common issues

### Updates and Patches

- **Lambda Runtime:** Automatic updates managed by AWS
- **Dependencies:** Regular updates via requirements.txt
- **Infrastructure:** Version-controlled CloudFormation templates