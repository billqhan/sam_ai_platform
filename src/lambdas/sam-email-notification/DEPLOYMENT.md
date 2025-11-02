# SAM Email Notification Deployment Guide

This guide walks through deploying the email notification system that sends RTF attachments via AWS SES when new response templates are generated.

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Existing SAM infrastructure** (buckets, lambda deployment scripts)
3. **S3 bucket for subscribers CSV** (e.g., `ktest-sam-subscribers`)

## Important Notes

- **SES Sandbox Mode**: By default, AWS SES is in sandbox mode, requiring verification of both sender AND recipient emails
- **Production Access**: For production use, request SES production access to send to unverified emails
- **Bucket Names**: The actual bucket names may differ from documentation (e.g., `ktest-sam-opportunity-responses-dev` vs `m-sam-opportunity-responses`)

## Step 1: Add Lambda to Deployment Script

First, ensure the new lambda function is added to the deployment configuration:

**File: `infrastructure/scripts/update-lambda-code.ps1`**
```powershell
$LambdaFunctions = @{
    "sam-gov-daily-download" = "src/lambdas/sam-gov-daily-download"
    "sam-json-processor" = "src/lambdas/sam-json-processor"
    "sam-sqs-generate-match-reports" = "src/lambdas/sam-sqs-generate-match-reports"
    "sam-produce-user-report" = "src/lambdas/sam-produce-user-report"
    "sam-email-notification" = "src/lambdas/sam-email-notification"  # <- ADD THIS LINE
    "sam-merge-and-archive-result-logs" = "src/lambdas/sam-merge-and-archive-result-logs"
    "sam-produce-web-reports" = "src/lambdas/sam-produce-web-reports"
}
```

## Step 2: Create S3 Bucket for Subscribers

```bash
aws s3 mb s3://ktest-sam-subscribers --region us-east-1
```

## Step 3: Verify SES Email Address

Verify your sender email address in AWS SES:

```bash
# Replace with your actual email
aws ses verify-email-identity --email-address mga.aws2024@gmail.com

# Check verification status
aws ses get-identity-verification-attributes --identities mga.aws2024@gmail.com
```

## Step 4: Create Lambda Function

Since this is a new lambda function, you need to create it first:

```powershell
cd src/lambdas/sam-email-notification
.\create-lambda-final.ps1
```

This script will:
- Create IAM role with proper permissions
- Create the lambda function
- Set up basic configuration

## Step 5: Deploy Lambda Code

Deploy the actual lambda code using the existing deployment infrastructure:

```powershell
.\infrastructure\scripts\update-lambda-code.ps1 -Environment "dev" -TemplatesBucket "m2-sam-templates-bucket" -BucketPrefix "ktest" -LambdaName "sam-email-notification"
```

## Step 6: Configure Environment Variables

Create environment variables configuration file:

**File: `env-vars.json`**
```json
{
  "Variables": {
    "EMAIL_ENABLED": "false",
    "FROM_EMAIL": "mga.aws2024@gmail.com",
    "SUBSCRIBERS_BUCKET": "ktest-sam-subscribers", 
    "SUBSCRIBERS_FILE": "subscribers.csv",
    "SES_REGION": "us-east-1",
    "EMAIL_SUBJECT_TEMPLATE": "AWS AI-Powered RFI/RFP Response for {solicitation_number}",
    "EMAIL_BODY": "Dear Team, here is the latest match for your review."
  }
}
```

Apply the configuration:
```bash
aws lambda update-function-configuration --function-name "ktest-sam-email-notification-dev" --environment file://env-vars.json --region us-east-1
```

## Step 7: Update IAM Permissions

The lambda needs access to the correct S3 buckets. Update the IAM policy:

**File: `updated-lambda-policy.json`**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::m-sam-opportunity-responses/*",
        "arn:aws:s3:::ktest-sam-opportunity-responses-dev/*",
        "arn:aws:s3:::ktest-sam-subscribers/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

Apply the policy:
```bash
aws iam put-role-policy --role-name "ktest-sam-email-notification-dev-role" --policy-name "EmailPolicy" --policy-document file://updated-lambda-policy.json --region us-east-1
```

## Step 8: Create Subscribers CSV

Create and upload the subscribers CSV file:

```bash
python create-sample-subscribers.py --bucket ktest-sam-subscribers --file subscribers.csv
```

**Important for SES Sandbox Mode**: If you're in SES sandbox mode, you must verify recipient email addresses:

```bash
# Verify each subscriber email
aws ses verify-email-identity --email-address subscriber@example.com --region us-east-1
```

## Step 9: Add S3 Permission for Lambda

Allow S3 to invoke the lambda function:

```bash
aws lambda add-permission \
  --function-name ktest-sam-email-notification-dev \
  --principal s3.amazonaws.com \
  --action lambda:InvokeFunction \
  --source-arn arn:aws:s3:::ktest-sam-opportunity-responses-dev \
  --statement-id s3-email-trigger-permission \
  --region us-east-1
```

## Step 10: Configure S3 Event Trigger

**⚠️ Manual Step Required**: Due to permission restrictions, S3 event notifications must be configured manually:

### Using AWS Console (Recommended):

1. Go to S3 Console → `ktest-sam-opportunity-responses-dev` bucket
2. Go to "Properties" tab
3. Scroll to "Event notifications"
4. Click "Create event notification"
5. Configure:
   - **Name**: RTFEmailNotification
   - **Event types**: All object create events
   - **Suffix**: .rtf
   - **Destination**: Lambda function
   - **Lambda function**: ktest-sam-email-notification-dev

### Using AWS CLI (if permissions allow):

**File: `s3-notification-config.json`**
```json
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "RTFEmailNotification",
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:302585542747:function:ktest-sam-email-notification-dev",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "suffix",
              "Value": ".rtf"
            }
          ]
        }
      }
    }
  ]
}
```

```bash
aws s3api put-bucket-notification-configuration \
  --bucket ktest-sam-opportunity-responses-dev \
  --notification-configuration file://s3-notification-config.json \
  --region us-east-1
```

## Step 11: Test the System

Test the complete workflow:

1. **Check CloudWatch logs** for the email lambda:
```bash
aws logs tail /aws/lambda/ktest-sam-email-notification-dev --follow
```

2. **Upload a test RTF file** to trigger the system:
```bash
# The system should automatically trigger when RTF files are uploaded to:
# s3://ktest-sam-opportunity-responses-dev/YYYY-MM-DD/matches/*.rtf
```

3. **Verify email delivery** - check that subscribers received the email with RTF attachment

## SES Sandbox Mode Considerations

**If you're in SES Sandbox Mode** (default for new accounts):

1. **Check your status**:
```bash
aws sesv2 get-account --region us-east-1
# Look for "ProductionAccessEnabled": false
```

2. **Verify recipient emails** (temporary solution):
```bash
aws ses verify-email-identity --email-address recipient@example.com --region us-east-1
```

3. **Request Production Access** (recommended):
   - Go to AWS SES Console → Account dashboard
   - Click "Request production access"
   - Fill out the form explaining your use case
   - AWS typically approves within 24-48 hours

## Quick Deployment Script

For convenience, you can use the simplified deployment script:

```powershell
cd src/lambdas/sam-email-notification
.\deploy-simple.ps1
```

This handles steps 5-8 automatically (though you'll still need to configure S3 events manually).

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_ENABLED` | No | false | Enable/disable email notifications (set to "true" to enable) |
| `FROM_EMAIL` | Yes | - | Verified SES sender email |
| `SUBSCRIBERS_BUCKET` | Yes | - | S3 bucket with CSV file |
| `SUBSCRIBERS_FILE` | No | subscribers.csv | CSV filename |
| `SES_REGION` | No | us-east-1 | AWS region for SES |
| `EMAIL_SUBJECT_TEMPLATE` | No | AWS AI-Powered RFI/RFP Response for {solicitation_number} | Email subject |
| `EMAIL_BODY` | No | Dear Team, here is the latest match for your review. | Email body |

## Troubleshooting

### Common Issues

1. **Lambda function not found during deployment**
   - **Solution**: Run `create-lambda-final.ps1` first to create the function
   - **Cause**: New lambda functions must be created before code can be deployed

2. **Access Denied on S3 GetObject**
   - **Solution**: Update IAM policy with correct bucket names
   - **Cause**: Bucket names may differ (e.g., `ktest-sam-opportunity-responses-dev` vs `m-sam-opportunity-responses`)

3. **Email address not verified (MessageRejected)**
   - **Solution**: Verify recipient emails in SES or request production access
   - **Cause**: SES sandbox mode requires verification of both sender and recipients

4. **Environment variables configuration failed**
   - **Solution**: Use proper JSON format with `Variables` wrapper
   - **Cause**: AWS CLI requires specific JSON structure for environment variables

5. **S3 event notification access denied**
   - **Solution**: Configure manually in AWS Console
   - **Cause**: Insufficient permissions for S3 bucket notification configuration

6. **Lambda not triggered by S3**
   - Check S3 event configuration in console
   - Verify lambda permissions for S3 invocation
   - Ensure correct bucket name is configured

### Logs to Check

```bash
# Email lambda logs (most important)
aws logs tail /aws/lambda/ktest-sam-email-notification-dev --follow

# Check lambda function status
aws lambda get-function --function-name ktest-sam-email-notification-dev

# SES sending statistics
aws ses get-send-statistics

# Verify SES account status
aws sesv2 get-account --region us-east-1
```

### Verification Commands

```bash
# Check if lambda exists
aws lambda get-function --function-name ktest-sam-email-notification-dev

# Check environment variables
aws lambda get-function-configuration --function-name ktest-sam-email-notification-dev

# Check SES verification status
aws ses get-identity-verification-attributes --identities your-email@example.com

# List S3 bucket contents
aws s3 ls s3://ktest-sam-subscribers/
aws s3 ls s3://ktest-sam-opportunity-responses-dev/2025-10-21/matches/
```

## Managing Subscribers

To add/remove email subscribers:

1. **Download current CSV**:
```bash
aws s3 cp s3://your-config-bucket/subscribers.csv ./
```

2. **Edit the file** (add rows or set active=false)

3. **Upload updated CSV**:
```bash
aws s3 cp subscribers.csv s3://your-config-bucket/
```

Changes take effect immediately on the next email notification.