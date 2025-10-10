# 🪟 Windows Deployment Commands - Llama Model Update

## Quick Deployment Script

**Run the automated script:**
```powershell
cd deployment\sam-sqs-generate-match-reports
.\deploy-llama-windows.ps1
```

## Manual Commands (Windows PowerShell)

### Step 1: Update Lambda Environment Variables
```powershell
aws lambda update-function-configuration `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --environment "Variables={MODEL_ID_DESC=us.meta.llama3-70b-instruct-v1:0,MODEL_ID_MATCH=us.meta.llama3-70b-instruct-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev}" `
  --region us-east-1
```

### Step 2: Deploy Updated Lambda Code
```powershell
cd deployment\sam-sqs-generate-match-reports
aws lambda update-function-code `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --zip-file fileb://lambda-deployment-llama-support.zip `
  --region us-east-1
```

## Alternative: Update CloudFormation Stack (Windows)
```powershell
aws cloudformation update-stack `
  --stack-name ai-rfp-response-agent-phase2-dev `
  --template-body file://infrastructure/cloudformation/lambda-functions.yaml `
  --capabilities CAPABILITY_IAM `
  --region us-east-1
```

## Verify Deployment
```powershell
# Check environment variables
aws lambda get-function-configuration `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --query 'Environment.Variables' `
  --region us-east-1

# Monitor logs
aws logs tail /aws/lambda/ktest-sam-sqs-generate-match-reports-dev --follow
```

## Expected Output
```
✅ Environment variables updated successfully
✅ Lambda code deployed successfully
🎉 Llama model deployment complete!
```

## Troubleshooting

### If AWS CLI not found:
```powershell
# Install AWS CLI v2 for Windows
winget install Amazon.AWSCLI
```

### If permission errors:
```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### If deployment fails:
```powershell
# Check AWS credentials
aws sts get-caller-identity

# Check function exists
aws lambda get-function --function-name ktest-sam-sqs-generate-match-reports-dev
```