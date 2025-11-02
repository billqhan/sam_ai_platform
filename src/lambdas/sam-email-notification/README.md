# SAM Email Notification Lambda

This lambda function sends email notifications via AWS SES when new response templates (RTF files) are created by the `sam-produce-user-report` lambda.

## Features

- Triggered by S3 events when RTF files are uploaded to the response bucket
- Extracts solicitation number from filename or file content
- Sends emails with RTF file as attachment
- Configurable email subject and body via environment variables
- Supports multiple recipients

## Environment Variables

### Required
- `FROM_EMAIL`: The verified SES sender email address
- `SUBSCRIBERS_BUCKET`: S3 bucket containing the subscribers CSV file
- `SUBSCRIBERS_FILE`: CSV filename (default: "subscribers.csv")

### Optional
- `EMAIL_ENABLED`: Enable/disable email notifications (default: "false"). Set to "true" to enable email sending
- `SES_REGION`: AWS region for SES (default: "us-east-1")
- `EMAIL_SUBJECT_TEMPLATE`: Email subject template with {solicitation_number} placeholder (default: "AWS AI-Powered RFI/RFP Response for {solicitation_number}")
- `EMAIL_BODY`: Email body text (default: "Dear Team, here is the latest match for your review.")

## Subscription Management

The lambda uses a CSV file stored in S3 to manage email subscriptions. This provides a simple, manageable way to control who receives notifications.

### CSV Format

The subscribers CSV file should have these columns:
- `email`: Email address (required)
- `name`: Subscriber name (optional)
- `active`: true/false to enable/disable notifications (required)
- `subscription_date`: When they subscribed (optional)

### Sample CSV Content

```csv
email,name,active,subscription_date
john.doe@company.com,John Doe,true,2024-01-15
jane.smith@company.com,Jane Smith,true,2024-01-20
manager@company.com,Team Manager,true,2024-01-10
old.user@company.com,Old User,false,2023-12-01
```

### Managing Subscriptions

To add/remove subscribers:
1. Download the CSV file from S3
2. Edit the file (add new rows or set `active=false` to disable)
3. Upload the updated CSV back to S3

## Example Environment Variables

```bash
EMAIL_ENABLED=false
FROM_EMAIL=noreply@yourcompany.com
SUBSCRIBERS_BUCKET=my-company-config
SUBSCRIBERS_FILE=email-subscribers.csv
SES_REGION=us-east-1
EMAIL_SUBJECT_TEMPLATE=AWS AI-Powered RFI/RFP Response for {solicitation_number}
EMAIL_BODY=Dear Team, here is the latest match for your review.
```

## Setup Requirements

1. **SES Configuration**: The FROM_EMAIL must be verified in AWS SES
2. **Subscribers CSV**: Upload a CSV file with subscriber information to S3
3. **S3 Event Trigger**: Configure S3 bucket to trigger this lambda on RTF file creation
4. **IAM Permissions**: Lambda needs permissions for:
   - S3: GetObject (to read RTF files and subscribers CSV)
   - SES: SendRawEmail (to send emails)

## Solicitation Number Extraction

The function extracts solicitation numbers using these methods (in order):

1. **Filename Pattern**: Extracts prefix before `_response_template.rtf`
   - Example: `ABC123_response_template.rtf` → `ABC123`

2. **File Content**: Searches RTF content for patterns like:
   - `Solicitation: ABC123`
   - `Solicitation Number: ABC123`
   - `Response to Solicitation ABC123`

3. **Fallback**: Uses filename without extension

## Deployment

Use the standard lambda deployment script:

```powershell
.\infrastructure\scripts\update-lambda-code.ps1 -Environment "dev" -TemplatesBucket "m2-sam-templates-bucket" -BucketPrefix "ktest" -LambdaName "sam-email-notification"
```

## S3 Event Configuration

Configure the response bucket to trigger this lambda when RTF files are created:

```json
{
  "Rules": [
    {
      "Id": "RTFEmailNotification",
      "Status": "Enabled",
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "suffix",
              "Value": ".rtf"
            }
          ]
        }
      },
      "CloudWatchConfiguration": {
        "LambdaConfiguration": {
          "Id": "RTFEmailNotificationLambda",
          "LambdaFunctionArn": "arn:aws:lambda:region:account:function:lambda-name",
          "Events": ["s3:ObjectCreated:*"]
        }
      }
    }
  ]
}
```

## Testing

You can test the function by uploading an RTF file with `response_template` in the name to the configured S3 bucket. The lambda will:

1. Extract the solicitation number
2. Download the RTF file
3. Send an email with the file attached to all configured recipients