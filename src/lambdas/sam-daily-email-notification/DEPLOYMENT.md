# Daily Email Notification Lambda - Deployment Guide

This guide provides step-by-step instructions for deploying the daily email notification system.

## Overview

The daily email notification system sends automated emails at 10am EST containing:
- A link to the daily opportunities website
- A zip file with high-scoring RTF opportunity matches
- Uses `subscribers_daily.csv` for recipient management

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **PowerShell** for running deployment scripts
3. **SES email verification** for the sender email address
4. **Existing SAM infrastructure** deployed

## Deployment Steps

### Step 1: Create Lambda Function

Run the creation script to set up the Lambda function and IAM role:

```powershell
cd src/lambdas/sam-daily-email-notification
.\create-lambda.ps1 -Environment dev -BucketPrefix ktest
```

This creates:
- Lambda function: `ktest-sam-daily-email-notification-dev`
- IAM role with S3 and SES permissions
- Environment variables configuration

### Step 2: Upload Subscribers File

Upload the daily subscribers CSV to S3:

```powershell
.\upload-subscribers.ps1 -BucketPrefix ktest
```

This creates the S3 bucket (if needed) and uploads `subscribers_daily.csv`.

### Step 3: Deploy Lambda Code

Use the existing deployment infrastructure to deploy the actual code:

```powershell
cd ../../../infrastructure/scripts
.\update-lambda-code.ps1 -LambdaName sam-daily-email-notification -TemplatesBucket your-templates-bucket -BucketPrefix ktest -Environment dev
```

### Step 4: Verify SES Configuration

Ensure the sender email is verified in SES:

```powershell
aws ses verify-email-identity --email-address mga.aws2024@gmail.com --region us-east-1
```

Check verification status:

```powershell
aws ses get-identity-verification-attributes --identities mga.aws2024@gmail.com --region us-east-1
```

### Step 5: Update CloudFormation Templates

The CloudFormation templates have been updated to include:
- New Lambda function definition
- IAM role with appropriate permissions
- EventBridge rule for daily 10am EST execution
- Lambda permission for EventBridge invocation

Deploy the updated infrastructure:

```powershell
# Update the CloudFormation stack with new templates
aws cloudformation update-stack --stack-name your-stack-name --template-url https://your-bucket.s3.amazonaws.com/master-template.yaml --parameters file://parameters.json --capabilities CAPABILITY_IAM --region us-east-1
```

### Step 6: Test the Function

Test the Lambda function manually:

```powershell
aws lambda invoke --function-name ktest-sam-daily-email-notification-dev --region us-east-1 response.json
```

Check the response:

```powershell
Get-Content response.json
```

## Configuration

### Environment Variables

The function uses these environment variables (automatically set during deployment):

| Variable | Value | Description |
|----------|-------|-------------|
| `EMAIL_ENABLED` | `true` | Enable/disable email sending |
| `SES_REGION` | `us-east-1` | AWS SES region |
| `FROM_EMAIL` | `mga.aws2024@gmail.com` | Sender email address |
| `EMAIL_SUBJECT_TEMPLATE` | `Daily AWS AI-Powered RFI/RFP Response for {date}` | Email subject template |
| `EMAIL_BODY_TEMPLATE` | See lambda code | Email body template |
| `OPPORTUNITY_RESPONSES_BUCKET` | `ktest-sam-opportunity-responses-dev` | S3 bucket with RTF files |
| `WEBSITE_BUCKET` | `ktest-sam-website-dev` | S3 bucket with website files |
| `WEBSITE_BASE_URL` | `http://ktest-sam-website-dev.s3-website-us-east-1.amazonaws.com` | Website base URL |
| `SUBSCRIBERS_BUCKET` | `ktest-sam-subscribers` | S3 bucket with subscriber list |
| `SUBSCRIBERS_FILE` | `subscribers_daily.csv` | CSV file with daily subscribers |

### EventBridge Schedule

The function is triggered daily at 10am EST (3pm UTC) using this cron expression:
```
cron(0 15 * * ? *)
```

### Subscriber Management

Add/remove subscribers by editing `subscribers_daily.csv`:

```csv
email,name,active,subscription_date
user1@example.com,John Doe,true,2025-10-22
user2@example.com,Jane Smith,true,2025-10-22
user3@example.com,Bob Johnson,false,2025-10-22
```

Upload changes:

```powershell
.\upload-subscribers.ps1 -BucketPrefix ktest
```

## Monitoring

### CloudWatch Logs

Monitor function execution:
- Log Group: `/aws/lambda/ktest-sam-daily-email-notification-dev`
- View logs in AWS Console or CLI

### SES Metrics

Monitor email delivery:
- SES Console → Sending Statistics
- Watch for bounces and complaints

### Lambda Metrics

Monitor function performance:
- Lambda Console → Monitoring tab
- CloudWatch metrics for invocations, errors, duration

## Troubleshooting

### Common Issues

1. **Email not sending**
   - Check SES verification status
   - Verify sender email in SES console
   - Check CloudWatch logs for errors

2. **No recent data found**
   - Verify S3 bucket structure: `YYYY-MM-DD/matches/*.rtf`
   - Check if opportunity processing is working
   - Review function logs for date detection

3. **Zip file creation fails**
   - Check S3 permissions for opportunity responses bucket
   - Verify RTF files exist in matches folder
   - Review CloudWatch logs for S3 errors

4. **Subscribers not loaded**
   - Verify `subscribers_daily.csv` exists in S3
   - Check CSV format and encoding
   - Ensure S3 permissions for subscribers bucket

### Debug Mode

Enable debug logging by updating the Lambda function:

```python
logger.setLevel(logging.DEBUG)
```

### Manual Testing

Test individual components:

```python
# Test finding recent date
most_recent_date = find_most_recent_processed_date()
print(f"Most recent date: {most_recent_date}")

# Test subscriber loading
subscribers = load_daily_subscribers()
print(f"Loaded {len(subscribers)} subscribers")

# Test zip creation
zip_content = create_rtf_zip("2025-10-22")
print(f"Zip size: {len(zip_content) if zip_content else 0} bytes")
```

## Security Considerations

1. **SES Sandbox Mode**
   - Request production access for unrestricted sending
   - Current limit: 200 emails/day, 1 email/second

2. **IAM Permissions**
   - Function has minimal required permissions
   - S3 access limited to specific buckets
   - SES access for sending emails only

3. **Email Content**
   - No sensitive data in email body
   - Attachments contain only RTF files
   - Website links are public S3 URLs

## Maintenance

### Regular Tasks

1. **Monitor subscriber list**
   - Review bounce/complaint rates
   - Update CSV file as needed
   - Remove inactive subscribers

2. **Check SES limits**
   - Monitor sending quotas
   - Request limit increases if needed

3. **Review logs**
   - Check for errors or warnings
   - Monitor function performance
   - Verify email delivery success

### Updates

To update the function code:

1. Modify `lambda_function.py`
2. Run deployment script:
   ```powershell
   .\update-lambda-code.ps1 -LambdaName sam-daily-email-notification -TemplatesBucket your-bucket -BucketPrefix ktest -Environment dev
   ```

## Success Criteria

✅ **Lambda Function**: Created and deployed successfully  
✅ **IAM Permissions**: S3 and SES access configured  
✅ **EventBridge Rule**: Daily 10am EST trigger active  
✅ **Subscribers CSV**: Uploaded and accessible  
✅ **SES Configuration**: Sender email verified  
✅ **Email Delivery**: Test emails sent successfully  
✅ **Website Links**: URLs generated correctly  
✅ **RTF Attachments**: Zip files created and attached  

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review this deployment guide
3. Test individual components
4. Verify AWS service configurations (SES, S3, Lambda)