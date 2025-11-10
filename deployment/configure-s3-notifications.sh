#!/bin/bash
# Configure S3 Event Notifications Manually
# This script configures S3 buckets to send notifications to Lambda functions and SQS queues
# Use this when CloudFormation fails due to AWS propagation timing issues

set -e

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$PROJECT_ROOT/.env.dev"

REGION=${REGION:-us-east-1}
ENV=${ENVIRONMENT:-dev}
PREFIX=${BUCKET_PREFIX:-dev}

echo "=== Configuring S3 Event Notifications ==="
echo "Environment: $ENV"
echo "Region: $REGION"
echo "Bucket Prefix: $PREFIX"
echo ""

# Notification 1: dev-sam-data-in-dev -> Lambda (JSON Processor)
echo "1. Configuring: $PREFIX-sam-data-in-$ENV -> dev-sam-json-processor-$ENV"
aws s3api put-bucket-notification-configuration \
  --bucket "$PREFIX-sam-data-in-$ENV" \
  --region "$REGION" \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:'$REGION':160936122037:function:dev-sam-json-processor-'$ENV'",
        "Events": ["s3:ObjectCreated:*"]
      }
    ]
  }'
echo "✓ Configured successfully"
echo ""

# Wait a bit between configurations
sleep 2

# Notification 2: dev-sam-extracted-json-resources-dev -> SQS
# Note: Ensure SQS queue uses SQS-managed encryption, not KMS encryption
# KMS-encrypted queues (alias/aws/sqs) are incompatible with S3 notifications
echo "2. Configuring: $PREFIX-sam-extracted-json-resources-$ENV -> SQS"

# First, ensure the queue encryption is compatible (SQS-managed, not KMS)
echo "   Updating queue encryption settings..."
aws sqs set-queue-attributes \
  --queue-url "https://sqs.$REGION.amazonaws.com/160936122037/$PREFIX-sqs-sam-json-messages-$ENV" \
  --region "$REGION" \
  --attributes '{
    "KmsMasterKeyId": "",
    "SqsManagedSseEnabled": "true"
  }' > /dev/null 2>&1

# Wait for encryption change to propagate
sleep 5

# Configure the S3 notification
aws s3api put-bucket-notification-configuration \
  --bucket "$PREFIX-sam-extracted-json-resources-$ENV" \
  --region "$REGION" \
  --notification-configuration '{
    "QueueConfigurations": [
      {
        "QueueArn": "arn:aws:sqs:'$REGION':160936122037:'$PREFIX'-sqs-sam-json-messages-'$ENV'",
        "Events": ["s3:ObjectCreated:*"]
      }
    ]
  }'
echo "✓ Configured successfully"
echo ""

sleep 2

# Notification 3: dev-sam-matching-out-sqs-dev -> Lambda (User Reports)
echo "3. Configuring: $PREFIX-sam-matching-out-sqs-$ENV -> dev-sam-produce-user-report-$ENV"
aws s3api put-bucket-notification-configuration \
  --bucket "$PREFIX-sam-matching-out-sqs-$ENV" \
  --region "$REGION" \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:'$REGION':160936122037:function:dev-sam-produce-user-report-'$ENV'",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {
                "Name": "prefix",
                "Value": "matches_"
              }
            ]
          }
        }
      }
    ]
  }'
echo "✓ Configured successfully"
echo ""

sleep 2

# Notification 4: dev-sam-matching-out-runs-dev -> Lambda (Web Reports)
echo "4. Configuring: $PREFIX-sam-matching-out-runs-$ENV -> dev-sam-produce-web-reports-$ENV"
aws s3api put-bucket-notification-configuration \
  --bucket "$PREFIX-sam-matching-out-runs-$ENV" \
  --region "$REGION" \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:'$REGION':160936122037:function:dev-sam-produce-web-reports-'$ENV'",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {
                "Name": "prefix",
                "Value": "runs/2"
              }
            ]
          }
        }
      }
    ]
  }'
echo "✓ Configured successfully"
echo ""

echo "=== All S3 Event Notifications Configured Successfully ==="
echo ""
echo "To verify the configurations:"
echo "  aws s3api get-bucket-notification-configuration --bucket $PREFIX-sam-data-in-$ENV --region $REGION"
echo "  aws s3api get-bucket-notification-configuration --bucket $PREFIX-sam-extracted-json-resources-$ENV --region $REGION"
echo "  aws s3api get-bucket-notification-configuration --bucket $PREFIX-sam-matching-out-sqs-$ENV --region $REGION"
echo "  aws s3api get-bucket-notification-configuration --bucket $PREFIX-sam-matching-out-runs-$ENV --region $REGION"
echo ""
echo "To test the workflow:"
echo "  1. Upload a file to $PREFIX-sam-data-in-$ENV"
echo "  2. Check CloudWatch Logs for dev-sam-json-processor-$ENV"
echo "  3. Verify JSON files appear in $PREFIX-sam-extracted-json-resources-$ENV"
echo "  4. Check SQS messages in $PREFIX-sqs-sam-json-messages-$ENV"
