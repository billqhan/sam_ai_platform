# Deployment Troubleshooting Session 02

**Date**: October 8, 2025  
**Session**: Lambda Parameter Review and Configuration Updates  
**Environment**: Development (dev)

## Session Overview

This session focused on reviewing the `sam-gov-daily-download-dev` lambda function parameters and implementing configuration changes to disable the daily trigger and modify retry behavior.

## Initial Request

**User Request**: Review parameters for lambda function `sam-gov-daily-download-dev`

## Parameter Review Results

### Core Function Configuration
- **Function Name**: `sam-gov-daily-download-dev` (with bucket prefix: `ktest`)
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`
- **Memory**: 512 MB
- **Timeout**: 900 seconds (15 minutes)
- **Tracing**: X-Ray Active tracing enabled

### Environment Variables
| Variable | Value | Purpose |
|----------|-------|---------|
| `SAM_API_URL` | `https://api.sam.gov/prod/opportunities/v2/search` | SAM.gov API endpoint |
| `SAM_API_KEY` | Parameter reference | API authentication key |
| `OUTPUT_BUCKET` | `sam-data-in-{environment}` | S3 bucket for storing opportunities |
| `LOG_BUCKET` | `sam-download-files-logs-{environment}` | S3 bucket for error logs |
| `API_LIMIT` | `1000` | Max records per API call |
| `OVERRIDE_DATE_FORMAT` | `MM/DD/YYYY` | Date format for API requests |
| `OVERRIDE_POSTED_FROM` | Empty | Optional date override |
| `OVERRIDE_POSTED_TO` | Empty | Optional date override |
| `X_AMZN_TRACE_ID` | Stack-based trace ID | X-Ray tracing identifier |

### IAM Permissions
- **S3 Operations**: PutObject, PutObjectAcl on data and log buckets
- **CloudWatch**: PutMetricData for custom metrics
- **X-Ray**: Daemon write access for tracing
- **CloudWatch Logs**: Basic execution role permissions

### Scheduling & Triggers
- **EventBridge Rule**: `cron(0 6 * * ? *)` - Daily at 6 AM UTC
- **Rule State**: ENABLED (initially)
- **Target**: Direct Lambda invocation

### Monitoring & Alerting
- **Log Retention**: 30 days in CloudWatch Logs
- **Error Alarm**: Triggers on ≥1 error within 5 minutes
- **Duration Alarm**: Triggers if execution exceeds 10 minutes (600,000ms)
- **SNS Notifications**: Configured for alarm states

## Configuration Change Requests

**User Request**: 
1. Disable the daily trigger
2. Change API retry logic to 0 retries

## Implementation

### Changes Made

#### 1. Disabled Daily Trigger
**File**: `infrastructure/cloudformation/eventbridge-rules.yaml`
```yaml
# Changed from:
State: ENABLED
# To:
State: DISABLED
```

#### 2. Updated API Retry Logic
**File**: `src/lambdas/sam-gov-daily-download/lambda_function.py`
```python
# Changed from:
max_retries = 1
# To:
max_retries = 0
```

**File**: `src/shared/config.py`
```python
# Changed default value from:
max_retries=int(self._get_required_env('SAM_API_MAX_RETRIES', '1'))
# To:
max_retries=int(self._get_required_env('SAM_API_MAX_RETRIES', '0'))
```

## Deployment Process

### Initial Deployment Attempt

**Command Used**:
```powershell
.\infrastructure\scripts\deploy-all-phases.ps1 `
  -Phase 2 `
  -Environment "dev" `
  -TemplatesBucket "m2-sam-templates-bucket" `
  -SamApiKey "DZeUYfjw6vmnDbNTiX0YyFPMmUCt5Ne6RpuUzzq1" `
  -CompanyName "L3Harris" `
  -CompanyContact "contact@L3Harris.com" `
  -BucketPrefix "ktest"
```

**Result**: 
```
ValidationError: No updates are to be performed.
```

**Root Cause**: CloudFormation doesn't detect changes in inline lambda code (`ZipFile`) or shared configuration files that don't directly affect the CloudFormation template.

### Successful Deployment Approach

#### Step 1: Direct Lambda Function Update

**Package Lambda Code**:
```powershell
Compress-Archive -Path "src/lambdas/sam-gov-daily-download/*.py" -DestinationPath "lambda-package.zip" -Force
```

**Update Lambda Function**:
```powershell
aws lambda update-function-code --function-name "ktest-sam-gov-daily-download-dev" --zip-file fileb://lambda-package.zip
```

**Result**: Successfully updated lambda function with timestamp `2025-10-08T16:59:49.000+0000`

#### Step 2: Deploy EventBridge Rules

**Get Required ARNs**:
```powershell
# Get Lambda ARN
aws cloudformation describe-stacks --stack-name "ai-rfp-response-agent-phase2-dev" --query "Stacks[0].Outputs[?OutputKey=='SamGovDailyDownloadFunctionArn'].OutputValue" --output text

# Result: arn:aws:lambda:us-east-1:302585542747:function:ktest-sam-gov-daily-download-dev
```

**Upload Updated Template**:
```powershell
aws s3 cp infrastructure/cloudformation/eventbridge-rules.yaml s3://m2-sam-templates-bucket/ai-rfp-response-agent/eventbridge-rules.yaml
```

**Deploy EventBridge Stack**:
```powershell
aws cloudformation deploy --template-file infrastructure/cloudformation/eventbridge-rules.yaml --stack-name "ai-rfp-response-agent-eventbridge-dev" --parameter-overrides Environment=dev SamGovDailyDownloadFunctionArn="arn:aws:lambda:us-east-1:302585542747:function:ktest-sam-gov-daily-download-dev" SamMergeAndArchiveResultLogsFunctionArn="arn:aws:lambda:us-east-1:302585542747:function:ktest-sam-merge-and-archive-result-logs-dev" BucketPrefix=ktest
```

**Result**: `Successfully created/updated stack - ai-rfp-response-agent-eventbridge-dev`

## Verification

### EventBridge Rule Status
```powershell
aws events describe-rule --name "sam-gov-daily-download-dev"
```

**Result**:
```json
{
    "Name": "sam-gov-daily-download-dev",
    "Arn": "arn:aws:events:us-east-1:302585542747:rule/sam-gov-daily-download-dev",
    "ScheduleExpression": "cron(0 6 * * ? *)",
    "State": "DISABLED",
    "Description": "Trigger SAM.gov daily download Lambda function",
    "EventBusName": "default",
    "CreatedBy": "302585542747"
}
```

### Lambda Function Update Verification
```powershell
aws lambda get-function-configuration --function-name "ktest-sam-gov-daily-download-dev" --query "LastModified"
```

**Result**: `"2025-10-08T16:59:49.000+0000"`

## Final Status

### ✅ Successfully Applied Changes

1. **Lambda Function Updated**
   - API retry logic changed from 1 to 0 retries
   - Code updated with timestamp: `2025-10-08T16:59:49.000+0000`

2. **Daily Trigger Disabled**
   - EventBridge rule `sam-gov-daily-download-dev` is now **DISABLED**
   - The function will no longer run automatically at 6 AM UTC

### Current Behavior

- **Automatic Execution**: Disabled (no daily trigger)
- **API Failures**: Fail immediately without retry
- **S3 Retry Logic**: Still active (1 retry for S3 operations)
- **Manual Invocation**: Still possible via AWS console/CLI

## Additional Discovery

### S3 Retry Logic (Unchanged)

**Location**: Line 226 in `_store_with_retry` method  
**Current Value**: `max_retries = 1`  
**Purpose**: Retries failed S3 upload operations  
**Recommendation**: Keep unchanged as S3 operations benefit from retry logic

### Two Separate Retry Mechanisms

1. **API Retry Logic** (Changed to 0):
   - **Location**: Lines 275-295 in `lambda_handler`
   - **Purpose**: Retries failed SAM.gov API calls
   - **Status**: ✅ Changed from 1 → 0 retries

2. **S3 Retry Logic** (Unchanged):
   - **Location**: `_store_with_retry` method (line 226)
   - **Purpose**: Retries failed S3 upload operations
   - **Status**: 🔄 Still 1 retry (recommended to keep)

## Lessons Learned

1. **CloudFormation Limitations**: Inline lambda code changes aren't detected by CloudFormation
2. **Direct Updates**: Use `aws lambda update-function-code` for code changes
3. **Separate Deployments**: EventBridge rules may need separate stack deployment
4. **Multiple Retry Mechanisms**: Different retry logic exists for API calls vs S3 operations
5. **Verification Important**: Always verify changes with AWS CLI commands

## Commands Reference

### Package and Update Lambda
```powershell
# Package
Compress-Archive -Path "src/lambdas/sam-gov-daily-download/*.py" -DestinationPath "lambda-package.zip" -Force

# Update
aws lambda update-function-code --function-name "ktest-sam-gov-daily-download-dev" --zip-file fileb://lambda-package.zip

# Cleanup
Remove-Item lambda-package.zip
```

### Deploy EventBridge Rules
```powershell
# Upload template
aws s3 cp infrastructure/cloudformation/eventbridge-rules.yaml s3://m2-sam-templates-bucket/ai-rfp-response-agent/

# Deploy
aws cloudformation deploy --template-file infrastructure/cloudformation/eventbridge-rules.yaml --stack-name "ai-rfp-response-agent-eventbridge-dev" --parameter-overrides Environment=dev SamGovDailyDownloadFunctionArn="<ARN>" SamMergeAndArchiveResultLogsFunctionArn="<ARN>" BucketPrefix=ktest
```

### Verification Commands
```powershell
# Check EventBridge rule
aws events describe-rule --name "sam-gov-daily-download-dev"

# Check lambda function
aws lambda get-function-configuration --function-name "ktest-sam-gov-daily-download-dev"
```

---

**Session Completed**: October 8, 2025  
**Status**: ✅ All requested changes successfully implemented and verified