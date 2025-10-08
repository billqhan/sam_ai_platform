# Lambda Function Dependency Issue - Troubleshooting Session

## Issue Summary

**Problem**: AWS Lambda function `ktest-sam-gov-daily-download-dev` was failing with import errors when invoked.

**Error**: `"Unable to import module 'lambda_function': No module named 'requests'"`

**Root Cause**: Lambda functions were deployed with placeholder code instead of properly packaged Python code with dependencies.

## Initial Error Investigation

### Command Executed
```bash
aws lambda invoke --function-name ktest-sam-gov-daily-download-dev --payload '{}' response.json
```

### Error Response
```json
{
  "StatusCode": 200,
  "FunctionError": "Unhandled",
  "ExecutedVersion": "$LATEST"
}
```

### Error Details (from response.json)
```json
{
  "errorMessage": "Unable to import module 'lambda_function': No module named 'requests'",
  "errorType": "Runtime.ImportModuleError",
  "requestId": "",
  "stackTrace": []
}
```

## Root Cause Analysis

### CloudFormation Template Issue

The Lambda functions were deployed using CloudFormation with placeholder code:

```yaml
Code:
  ZipFile: |
    def lambda_handler(event, context):
        return {'statusCode': 200, 'body': 'Function placeholder'}
```

This meant:
- No actual Python code was deployed
- No dependencies (requests, boto3, etc.) were included
- Functions had minimal code size (~few KB instead of ~13MB with dependencies)

### Missing Packaging Process

The deployment process was missing:
1. **Dependency installation** from `requirements.txt`
2. **Code packaging** with dependencies
3. **S3 upload** of packaged code
4. **Lambda code update** with proper package

## Solution Implementation

### 1. Created Lambda Packaging Script

**File**: `infrastructure/scripts/package-lambda.ps1`

Key features:
- Installs dependencies from `requirements.txt`
- Packages code with all transitive dependencies
- Uploads packaged ZIP to S3
- Handles Linux-compatible packaging for Lambda runtime

```powershell
# Install dependencies to package directory
& python -m pip install -r $RequirementsFile -t $PackageDir --platform linux_x86_64 --only-binary=:all:
```

### 2. Created Lambda Update Script

**File**: `infrastructure/scripts/update-lambda-code.ps1`

Key features:
- Packages individual or all Lambda functions
- Updates existing Lambda function code via AWS CLI
- Waits for deployment completion
- Handles function naming with prefixes and environments

### 3. Fixed Dependency Installation

**Initial Issue**: Used `--no-deps` flag which excluded transitive dependencies

**Fix**: Removed `--no-deps` to include all required dependencies like `charset_normalizer`

## Resolution Steps

### Step 1: Package and Deploy Lambda Function
```powershell
.\infrastructure\scripts\update-lambda-code.ps1 `
  -Environment "dev" `
  -TemplatesBucket "m2-sam-templates-bucket" `
  -BucketPrefix "ktest" `
  -LambdaName "sam-gov-daily-download"
```

### Step 2: Verify Code Size Increase
- **Before**: 276KB (placeholder code)
- **After**: 13.5MB (full code with dependencies)

### Step 3: Test Function
```bash
aws lambda invoke --function-name ktest-sam-gov-daily-download-dev --payload '{}' response.json
```

## Final Success

### Successful Response
```json
{
  "StatusCode": 200,
  "ExecutedVersion": "$LATEST"
}
```

### Function Output
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"SAM.gov daily download completed successfully\", \"requestId\": \"33579dd2-b0e7-48fc-9903-b0777b550e46\", \"opportunitiesCount\": 178, \"s3ObjectKey\": \"SAM_Opportunities_20251008_173738.json\"}"
}
```

## Key Learnings

### Lambda Dependency Packaging Methods

**Method 1: Direct Packaging (Used)**
- Dependencies packaged directly into Lambda ZIP file
- Single deployment package contains code + all libraries
- No separate layers needed
- Code size reflects total package size

**Method 2: Lambda Layers (Alternative)**
- Dependencies in separate layer
- Code references layer
- Visible as separate "Layers" section in AWS console

### Where Dependencies Appear

**In AWS Console:**
- **Code size**: Increases significantly (KB → MB)
- **No separate layers section**: Dependencies are embedded
- **Package contents**: If downloaded, shows library folders

**Package Structure:**
```
lambda-deployment-package.zip
├── lambda_function.py          # Your code
├── handler.py                  # Your code  
├── requests/                   # requests library
├── urllib3/                    # requests dependency
├── charset_normalizer/         # requests dependency
├── boto3/                      # AWS SDK
├── botocore/                   # boto3 dependency
└── ... (other dependencies)
```

## Prevention for Future Deployments

### 1. Update CloudFormation Templates
Replace placeholder `ZipFile` with proper S3 references:

```yaml
Code:
  S3Bucket: !Ref TemplatesBucket
  S3Key: !Sub 'lambda-packages/${FunctionName}.zip'
```

### 2. Integrate Packaging into Deployment Pipeline
Add packaging step to deployment scripts:

```powershell
# Package all Lambda functions before CloudFormation deployment
foreach ($Function in $LambdaFunctions) {
    & .\package-lambda.ps1 -LambdaName $Function.Key -SourcePath $Function.Value
}
```

### 3. Automated Testing
Add post-deployment verification:

```bash
# Test each Lambda function after deployment
aws lambda invoke --function-name $FunctionName --payload '{}' test-response.json
```

## Files Created/Modified

### New Files
- `infrastructure/scripts/package-lambda.ps1` - Lambda packaging script (PowerShell)
- `infrastructure/scripts/update-lambda-code.ps1` - Lambda update script (PowerShell)
- `infrastructure/scripts/update-lambda-code.sh` - Lambda update script (Linux/macOS)
- `docs/troubleshooting/03-deployment-troubleshooting-session.md` - This documentation

### Modified Files
- `infrastructure/scripts/package-lambda.ps1` - Fixed `--no-deps` issue in PowerShell packaging script
- `infrastructure/scripts/package-lambdas.sh` - Fixed `--only-binary=:all:` issue in Linux packaging script

## Environment Details

- **Environment**: dev
- **Bucket Prefix**: ktest
- **Templates Bucket**: m2-sam-templates-bucket
- **Function Name**: ktest-sam-gov-daily-download-dev
- **Region**: us-east-1
- **Python Runtime**: 3.11

## Success Metrics

✅ **Import errors resolved**: No more "No module named 'requests'"  
✅ **Function executes successfully**: StatusCode 200  
✅ **Data retrieval working**: 178 opportunities downloaded from SAM.gov  
✅ **S3 storage working**: Data successfully stored as JSON file  
✅ **Code size appropriate**: 13.5MB indicates all dependencies included