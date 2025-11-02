# SAM Daily Email Notification Lambda

This Lambda function sends daily email notifications containing:
1. A link to the daily opportunities website
2. A zip file with high-scoring RTF opportunity matches

## Functionality

- **Trigger**: EventBridge rule (daily at 10am EST)
- **Purpose**: Send daily summary emails to subscribers
- **Data Source**: S3 buckets containing processed opportunities and website files
- **Recipients**: Managed via `subscribers_daily.csv` in S3

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMAIL_ENABLED` | Enable/disable email sending | `true` |
| `SES_REGION` | AWS SES region | `us-east-1` |
| `FROM_EMAIL` | Sender email address | `noreply@example.com` |
| `EMAIL_SUBJECT_TEMPLATE` | Email subject template | `Daily AWS AI-Powered RFI/RFP Response for {date}` |
| `EMAIL_BODY_TEMPLATE` | Email body template | See lambda code |
| `OPPORTUNITY_RESPONSES_BUCKET` | S3 bucket with RTF files | `ktest-sam-opportunity-responses-dev` |
| `WEBSITE_BUCKET` | S3 bucket with website files | `ktest-sam-website-dev` |
| `WEBSITE_BASE_URL` | Base URL for website links | `http://ktest-sam-website-dev.s3-website-us-east-1.amazonaws.com` |
| `SUBSCRIBERS_BUCKET` | S3 bucket with subscriber list | `ktest-sam-subscribers` |
| `SUBSCRIBERS_FILE` | CSV file with daily subscribers | `subscribers_daily.csv` |

## Subscriber CSV Format

The `subscribers_daily.csv` file should have the following format:

```csv
email,name,active,subscription_date
user1@example.com,John Doe,true,2025-10-22
user2@example.com,Jane Smith,true,2025-10-22
user3@example.com,Bob Johnson,false,2025-10-22
```

## Email Content

### Subject
`Daily AWS AI-Powered RFI/RFP Response for YYYY-MM-DD`

### Body
```
Dear Team, here is the Daily Website for your review.

I have attached a zip file containing only the high scoring opportunity matches for YYYY-MM-DD.

Please review the Daily Opportunities Website at the URL below for a summary of all data that was processed.

Daily Opportunities Website: http://ktest-sam-website-dev.s3-website-us-east-1.amazonaws.com/dashboards/Summary_YYYYMMDD.html
```

### Attachment
- Zip file containing all RTF files from `s3://bucket/YYYY-MM-DD/matches/`
- Filename: `high_scoring_matches_YYYYMMDD.zip`

## Data Flow

1. **Find Most Recent Date**: Scans S3 bucket for the most recent date folder with processed data
2. **Generate Website URL**: Creates URL for daily summary page (Summary_YYYYMMDD.html)
3. **Create RTF Zip**: Downloads and zips all RTF files from the matches folder
4. **Load Subscribers**: Reads active subscribers from CSV file
5. **Send Email**: Sends email with website link and zip attachment via SES

## IAM Permissions Required

- `s3:ListBucket` on opportunity responses and subscribers buckets
- `s3:GetObject` on opportunity responses and subscribers buckets
- `ses:SendRawEmail` for email delivery
- Basic Lambda execution permissions for CloudWatch logs

## Deployment

This function is deployed as part of the SAM infrastructure using CloudFormation templates and PowerShell deployment scripts.

## Monitoring

- **CloudWatch Logs**: `/aws/lambda/ktest-sam-daily-email-notification-dev`
- **SES Metrics**: Monitor bounce/complaint rates
- **Lambda Metrics**: Monitor invocation count and errors

## Error Handling

- Graceful handling of missing data (no recent dates, no RTF files)
- Comprehensive logging for troubleshooting
- Email sending continues even if zip creation fails
- Validates SES configuration before sending