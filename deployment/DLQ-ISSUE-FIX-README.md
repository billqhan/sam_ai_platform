# DLQ Issue Fix: Messages Incorrectly Sent to Dead Letter Queue

## Problem Description

The Lambda function `ktest-sam-sqs-generate-match-reports-dev` was sending **ALL messages** to the Dead Letter Queue (`ktest-s3-integration-dlq-dev`), even successfully processed ones. This was causing:

1. ✅ **Successfully processed messages** ending up in DLQ
2. 🔄 **Unnecessary reprocessing** of valid messages
3. 📊 **Incorrect monitoring metrics** and alerts
4. 💰 **Increased AWS costs** due to message retention and reprocessing

## Root Cause Analysis

### 1. **Timeout Race Condition**
- **SQS Visibility Timeout**: 300 seconds (5 minutes)
- **Lambda Timeout**: 300 seconds (5 minutes)
- **Problem**: When Lambda takes close to 5 minutes, the message becomes visible again before Lambda completes, causing the message to be redelivered and eventually sent to DLQ after 3 attempts.

### 2. **Improper Error Handling**
- Lambda function was catching all exceptions and returning HTTP 200 responses
- SQS interprets any non-exception response as successful processing
- Failed messages were not properly signaled to SQS for retry/DLQ behavior

### 3. **Batch Processing Issues**
- When processing multiple messages in a batch, if ANY message failed, the entire batch could be retried
- No partial batch failure reporting was configured

## Solution Implementation

### 1. **Increased SQS Visibility Timeout**
```yaml
# Before
VisibilityTimeoutSeconds: 300  # 5 minutes

# After  
VisibilityTimeoutSeconds: 1800  # 30 minutes (6x Lambda timeout)
```

**Why**: Ensures messages remain invisible long enough for Lambda to complete processing and properly delete them.

### 2. **Fixed Lambda Error Handling**
```python
# Before - Always returned success
return {
    'statusCode': 200,
    'body': json.dumps({...})
}

# After - Proper batch failure reporting
if failed > 0:
    return {
        'batchItemFailures': batch_item_failures
    }
```

**Why**: Properly signals to SQS which specific messages failed and should be retried or sent to DLQ.

### 3. **Enabled Partial Batch Failure Reporting**
```yaml
# Added to Event Source Mapping
FunctionResponseTypes:
  - ReportBatchItemFailures
```

**Why**: Allows Lambda to report individual message failures within a batch, preventing successful messages from being reprocessed.

## Deployment Instructions

### Option 1: Automated Deployment (Recommended)
```powershell
# Run the automated fix script
.\deployment\fix-dlq-issue.ps1 -Environment dev

# For production
.\deployment\fix-dlq-issue.ps1 -Environment prod
```

### Option 2: Manual Deployment

#### Step 1: Update CloudFormation Stack
```powershell
aws cloudformation update-stack \
  --stack-name sam-rfp-agent-dev \
  --template-body file://infrastructure/cloudformation/main-template.yaml \
  --parameters file://infrastructure/cloudformation/parameters-dev.json \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

#### Step 2: Update Lambda Function Code
```powershell
# Package and deploy the updated Lambda function
.\deployment\deploy-web-reports-lambda.ps1 -Environment dev
```

#### Step 3: Update Event Source Mapping
```powershell
# Get the event source mapping UUID
$MappingUuid = aws lambda list-event-source-mappings \
  --function-name sam-sqs-generate-match-reports-dev \
  --query "EventSourceMappings[0].UUID" --output text

# Update to enable partial batch failure reporting
aws lambda update-event-source-mapping \
  --uuid $MappingUuid \
  --function-response-types ReportBatchItemFailures
```

## Verification Steps

### 1. Check DLQ Status
```powershell
# Use the monitoring script
.\deployment\check-dlq-status.ps1 -Environment dev
```

### 2. Monitor CloudWatch Logs
```powershell
# Tail Lambda function logs
aws logs tail /aws/lambda/sam-sqs-generate-match-reports-dev --follow
```

### 3. Test with Sample Messages
1. Place a test file in the S3 input bucket
2. Monitor processing through CloudWatch logs
3. Verify successful messages are NOT sent to DLQ
4. Verify only genuinely failed messages go to DLQ after 3 attempts

## Expected Behavior After Fix

### ✅ **Successful Processing**
1. Message received from SQS
2. Lambda processes successfully
3. Message automatically deleted from SQS
4. **Message does NOT go to DLQ**

### ❌ **Failed Processing**
1. Message received from SQS
2. Lambda processing fails (genuine error)
3. Message returned to SQS for retry
4. After 3 failed attempts, message sent to DLQ
5. **Only failed messages go to DLQ**

## Monitoring and Alerting

### Key Metrics to Monitor
- **DLQ Message Count**: Should be near zero for healthy system
- **Lambda Error Rate**: Should be low (< 5%)
- **Lambda Duration**: Should be well under 300 seconds
- **SQS Message Age**: Should not approach visibility timeout

### CloudWatch Alarms
The system includes alarms for:
- DLQ message count > 0
- Lambda error rate > 10%
- Lambda duration approaching timeout

## Troubleshooting

### If Messages Still Go to DLQ
1. **Check Lambda Logs**: Look for actual processing errors
2. **Verify Timeout Settings**: Ensure visibility timeout > Lambda timeout
3. **Check Event Source Mapping**: Verify partial batch failure is enabled
4. **Monitor Processing Time**: Ensure Lambda completes within timeout

### Common Issues
- **Bedrock API Throttling**: May cause legitimate failures
- **S3 Access Errors**: Check IAM permissions
- **Memory Issues**: Monitor Lambda memory usage
- **Network Timeouts**: Check VPC configuration if applicable

## Performance Impact

### Positive Changes
- ✅ **Reduced DLQ Messages**: Only genuine failures
- ✅ **Improved Processing Efficiency**: No unnecessary reprocessing
- ✅ **Better Monitoring**: Accurate error metrics
- ✅ **Cost Reduction**: Less message retention and processing

### Considerations
- ⚠️ **Longer Visibility Timeout**: Messages locked longer during processing
- ⚠️ **Memory Usage**: Slightly higher due to batch failure tracking

## Rollback Plan

If issues occur after deployment:

### 1. Revert SQS Configuration
```powershell
# Revert to original visibility timeout
aws sqs set-queue-attributes \
  --queue-url $QueueUrl \
  --attributes VisibilityTimeoutSeconds=300
```

### 2. Revert Lambda Function
```powershell
# Deploy previous version
aws lambda update-function-code \
  --function-name sam-sqs-generate-match-reports-dev \
  --zip-file fileb://previous-version.zip
```

### 3. Disable Partial Batch Failure
```powershell
aws lambda update-event-source-mapping \
  --uuid $MappingUuid \
  --function-response-types ""
```

## Additional Resources

- [AWS SQS Dead Letter Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [Lambda SQS Event Source Mapping](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Partial Batch Failure Reporting](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting)

---

**Status**: ✅ Ready for deployment  
**Last Updated**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")  
**Environment**: All (dev, prod)