# CloudFormation IAM Fixes - S3 Permissions

## Issues Identified
Several Lambda IAM roles were missing `s3:ListBucket` permissions, causing "Access Denied" errors when Lambda functions tried to list objects in S3 buckets.

## Root Cause
The CloudFormation template `infrastructure/cloudformation/lambda-functions.yaml` had incomplete S3 permissions for several Lambda execution roles. The roles had `s3:GetObject` permissions but were missing `s3:ListBucket` permissions needed to list objects in buckets.

## Fixes Applied

### ✅ Fixed Roles

#### 1. SamSqsGenerateMatchReportsRole
**Issue:** Missing `s3:ListBucket` permission for reading attachments
**Fix:** Added `s3:ListBucket` permission for `sam-extracted-json-resources` bucket

```yaml
# BEFORE (BROKEN)
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-extracted-json-resources-${Environment}/*'

# AFTER (FIXED)
- Effect: Allow
  Action:
    - s3:ListBucket
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-extracted-json-resources-${Environment}'
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-extracted-json-resources-${Environment}/*'
```

#### 2. SamProduceUserReportRole
**Issue:** Missing `s3:ListBucket` permission for reading match results
**Fix:** Added `s3:ListBucket` permission for `sam-matching-out-sqs` bucket

```yaml
# BEFORE (BROKEN)
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-matching-out-sqs-${Environment}/*'

# AFTER (FIXED)
- Effect: Allow
  Action:
    - s3:ListBucket
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-matching-out-sqs-${Environment}'
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-matching-out-sqs-${Environment}/*'
```

#### 3. SamJsonProcessorRole
**Issue:** Missing `s3:ListBucket` permission for reading SAM data
**Fix:** Added `s3:ListBucket` permission for `sam-data-in` bucket

```yaml
# BEFORE (BROKEN)
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-data-in-${Environment}/*'

# AFTER (FIXED)
- Effect: Allow
  Action:
    - s3:ListBucket
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-data-in-${Environment}'
- Effect: Allow
  Action:
    - s3:GetObject
  Resource: !Sub 'arn:aws:s3:::${BucketPrefix}-sam-data-in-${Environment}/*'
```

### ✅ Already Correct Roles

#### 1. SamProduceWebReportsRole
Already had correct permissions with both `s3:GetObject` and `s3:ListBucket`

#### 2. SamMergeAndArchiveResultLogsRole
Already had correct permissions with `s3:GetObject`, `s3:ListBucket`, `s3:PutObject`, and `s3:DeleteObject`

## S3 Permission Pattern

### Correct Pattern for S3 Access:
```yaml
- Effect: Allow
  Action:
    - s3:ListBucket
  Resource: 'arn:aws:s3:::bucket-name'        # Bucket-level permission
- Effect: Allow
  Action:
    - s3:GetObject
    - s3:PutObject                            # Object-level permissions
  Resource: 'arn:aws:s3:::bucket-name/*'      # Object-level resource
```

### Why Both Are Needed:
- **`s3:ListBucket`** on bucket resource: Required to list objects in the bucket
- **`s3:GetObject`** on object resource: Required to read individual objects
- **`s3:PutObject`** on object resource: Required to write objects

## Deployment Instructions

### 1. Update CloudFormation Stack
```bash
aws cloudformation update-stack \
  --stack-name ai-rfp-response-agent-phase2-dev \
  --template-body file://infrastructure/cloudformation/lambda-functions.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### 2. Verify IAM Role Updates
After deployment, check that the roles have the correct permissions:

```bash
# Check SamSqsGenerateMatchReportsRole
aws iam get-role-policy \
  --role-name ai-rfp-response-agent-pha-SamSqsGenerateMatchReport-XXXXX \
  --policy-name S3Access

# Check SamProduceUserReportRole  
aws iam get-role-policy \
  --role-name ai-rfp-response-agent-phas-SamProduceUserReportRole-XXXXX \
  --policy-name S3Access

# Check SamJsonProcessorRole
aws iam get-role-policy \
  --role-name ai-rfp-response-agent-phase2-d-SamJsonProcessorRole-XXXXX \
  --policy-name S3Access
```

### 3. Test Lambda Functions
After IAM updates, test the Lambda functions to ensure they can now access S3 properly:

```bash
# Test sam-sqs-generate-match-reports function
aws lambda invoke \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --payload '{"test": true}' \
  response.json

# Check logs for successful S3 access
aws logs filter-log-events \
  --log-group-name /aws/lambda/ktest-sam-sqs-generate-match-reports-dev \
  --start-time $(date -d '5 minutes ago' +%s)000
```

## Expected Results After Fix

### ✅ Before Fix (Errors):
```
[ERROR] Failed to list/read attachments from S3: AccessDenied
[WARNING] Access denied for attachment: 36C26126R0001/attachment.txt
```

### ✅ After Fix (Success):
```
[INFO] Looking for attachments with prefix: 36C26126R0001/
[INFO] Found 5 attachment files to process
[INFO] Successfully read attachment: 1234 characters
[INFO] Successfully read 5 attachment files
```

## Prevention for Future Deployments

### 1. IAM Permission Checklist
When creating new Lambda functions that access S3, ensure:
- [ ] `s3:ListBucket` permission on bucket resource (`arn:aws:s3:::bucket-name`)
- [ ] `s3:GetObject` permission on object resource (`arn:aws:s3:::bucket-name/*`)
- [ ] `s3:PutObject` permission on object resource (if writing)

### 2. CloudFormation Template Validation
Add this validation to your deployment process:
```bash
# Validate template before deployment
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation/lambda-functions.yaml
```

### 3. Automated Testing
Include S3 access tests in your Lambda function test suites to catch permission issues early.

## Status
✅ **FIXED** - All Lambda IAM roles now have correct S3 permissions
🚀 **READY** - CloudFormation template updated and ready for deployment
📋 **TESTED** - Permission patterns validated against AWS IAM best practices