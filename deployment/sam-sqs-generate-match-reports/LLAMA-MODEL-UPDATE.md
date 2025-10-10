# 🦙 Llama Model Update - Fix Token Limit Issue

## Issue Resolved
**Problem:** Titan model has 4096 token limit, causing "Too many input tokens" errors
**Solution:** Switch to Llama 3 70B model with higher token capacity (8192+ tokens)

## Changes Made

### ✅ 1. CloudFormation Template Updated
**File:** `infrastructure/cloudformation/lambda-functions.yaml`

```yaml
# BEFORE (Titan - 4096 token limit)
MODEL_ID_DESC: 'amazon.titan-text-lite-v1'
MODEL_ID_MATCH: 'amazon.titan-text-lite-v1'

# AFTER (Llama - 8192+ token limit)
MODEL_ID_DESC: 'us.meta.llama3-70b-instruct-v1:0'
MODEL_ID_MATCH: 'us.meta.llama3-70b-instruct-v1:0'
MAX_TOKENS: '8000'
TEMPERATURE: '0.1'
```

### ✅ 2. Lambda Function Code Updated
**File:** `deployment/sam-sqs-generate-match-reports/shared/llm_data_extraction.py`

Added Llama model support with proper API format:

```python
# Request Format
elif 'llama' in self.model_id_desc.lower():
    request_body = {
        "prompt": prompt,
        "max_gen_len": self.max_tokens,
        "temperature": self.temperature,
        "top_p": 0.9
    }

# Response Format  
elif 'llama' in self.model_id_desc.lower():
    response_text = response_body['generation']
```

## Deployment Options

### 🚀 **Option 1: Quick Fix (Environment Variables Only)**
Update just the Lambda environment variables:

```bash
aws lambda update-function-configuration \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --environment Variables='{
    "MODEL_ID_DESC":"us.meta.llama3-70b-instruct-v1:0",
    "MODEL_ID_MATCH":"us.meta.llama3-70b-instruct-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' \
  --region us-east-1
```

Then deploy the updated Lambda code:
```bash
aws lambda update-function-code \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --zip-file fileb://lambda-deployment-llama-support.zip \
  --region us-east-1
```

### 🏗️ **Option 2: Complete Update (CloudFormation + Lambda)**
1. **Update CloudFormation Stack:**
```bash
aws cloudformation update-stack \
  --stack-name ai-rfp-response-agent-phase2-dev \
  --template-body file://infrastructure/cloudformation/lambda-functions.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

2. **Deploy Updated Lambda Code:**
```bash
aws lambda update-function-code \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --zip-file fileb://lambda-deployment-llama-support.zip \
  --region us-east-1
```

## Model Comparison

| Model | Token Limit | Performance | Cost |
|-------|-------------|-------------|------|
| **Titan Text Lite** | 4,096 | Fast | Low |
| **Llama 3 70B** | 8,192+ | High Quality | Medium |
| **Claude 3 Sonnet** | 200,000 | Highest Quality | High |

## Expected Results

### ❌ **Before (Titan Error):**
```
[ERROR] Failed to extract opportunity info: ValidationException: 
Too many input tokens. Max input tokens: 4096, request input token count: 5651
```

### ✅ **After (Llama Success):**
```
[INFO] 🤖 LLM REQUEST: us.meta.llama3-70b-instruct-v1:0 (prompt: 5651 chars)
[INFO] ✅ LLM RESPONSE: us.meta.llama3-70b-instruct-v1:0 (2340 chars, 3.2s)
[INFO] ✅ LLM opportunity extraction successful
[INFO] ✅ Company match calculation successful: score=0.75
```

## Token Usage Optimization

The Llama model can handle larger inputs, but you can also optimize token usage:

### Current Limits (Updated):
- `MAX_DESCRIPTION_CHARS: 20000` (≈ 5000 tokens)
- `MAX_ATTACHMENT_CHARS: 16000` (≈ 4000 tokens)
- `MAX_TOKENS: 8000` (response limit)

### If Still Getting Token Errors:
Reduce input limits in CloudFormation:
```yaml
MAX_DESCRIPTION_CHARS: '15000'  # Reduce from 20000
MAX_ATTACHMENT_CHARS: '12000'   # Reduce from 16000
```

## Bedrock Model Access

Ensure your AWS account has access to Llama models:

1. **Check Model Access:**
```bash
aws bedrock list-foundation-models \
  --by-provider meta \
  --region us-east-1
```

2. **Request Access (if needed):**
   - Go to AWS Bedrock Console
   - Navigate to "Model access"
   - Request access to "Llama 3 70B Instruct"

## Alternative Models

If Llama 3 70B is not available, alternatives:

1. **Llama 3 8B:** `us.meta.llama3-8b-instruct-v1:0` (smaller, faster)
2. **Claude 3 Haiku:** `anthropic.claude-3-haiku-20240307-v1:0` (fast, high limit)
3. **Claude 3 Sonnet:** `anthropic.claude-3-sonnet-20240229-v1:0` (highest quality)

## Files Updated
- ✅ `infrastructure/cloudformation/lambda-functions.yaml`
- ✅ `deployment/sam-sqs-generate-match-reports/shared/llm_data_extraction.py`
- ✅ `deployment/sam-sqs-generate-match-reports/lambda-deployment-llama-support.zip`

## Status
🚀 **READY FOR DEPLOYMENT** - Llama model support added to resolve token limit issues