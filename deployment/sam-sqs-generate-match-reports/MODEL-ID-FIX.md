# 🔧 Model ID Fix - Invalid Model Identifier

## Issue
```
[ERROR] ValidationException: The provided model identifier is invalid.
```

## Root Cause
The model ID `us.meta.llama3-70b-instruct-v1:0` is incorrect or not available in your region.

## Quick Fixes

### ✅ **Option 1: Try Correct Llama Model ID**
```bash
aws lambda update-function-configuration \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --environment Variables='{
    "MODEL_ID_DESC":"meta.llama3-70b-instruct-v1:0",
    "MODEL_ID_MATCH":"meta.llama3-70b-instruct-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' \
  --region us-east-1
```

### ✅ **Option 2: Use Claude 3 Haiku (Recommended)**
High token limit (200K) and proven to work:
```bash
aws lambda update-function-configuration \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --environment Variables='{
    "MODEL_ID_DESC":"anthropic.claude-3-haiku-20240307-v1:0",
    "MODEL_ID_MATCH":"anthropic.claude-3-haiku-20240307-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' \
  --region us-east-1
```

### ✅ **Option 3: Use Claude 3 Sonnet (Highest Quality)**
```bash
aws lambda update-function-configuration \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --environment Variables='{
    "MODEL_ID_DESC":"anthropic.claude-3-sonnet-20240229-v1:0",
    "MODEL_ID_MATCH":"anthropic.claude-3-sonnet-20240229-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' \
  --region us-east-1
```

## Check Available Models

To see what models are available in your account:

```bash
# List all available models
aws bedrock list-foundation-models --region us-east-1

# List only Meta models
aws bedrock list-foundation-models --by-provider meta --region us-east-1

# List only Anthropic models  
aws bedrock list-foundation-models --by-provider anthropic --region us-east-1
```

## Common Bedrock Model IDs

### Meta Llama Models:
- `meta.llama3-8b-instruct-v1:0` (8B parameters)
- `meta.llama3-70b-instruct-v1:0` (70B parameters)
- `meta.llama2-13b-chat-v1` (Llama 2)

### Anthropic Claude Models:
- `anthropic.claude-3-haiku-20240307-v1:0` (Fast, 200K tokens)
- `anthropic.claude-3-sonnet-20240229-v1:0` (Balanced, 200K tokens)
- `anthropic.claude-3-opus-20240229-v1:0` (Best quality, 200K tokens)

### Amazon Titan Models:
- `amazon.titan-text-lite-v1` (4K tokens - too small)
- `amazon.titan-text-express-v1` (8K tokens)

## Recommendation

**Use Claude 3 Haiku** - it's fast, has a 200K token limit, and is widely available:

```bash
aws lambda update-function-configuration \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --environment Variables='{
    "MODEL_ID_DESC":"anthropic.claude-3-haiku-20240307-v1:0",
    "MODEL_ID_MATCH":"anthropic.claude-3-haiku-20240307-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' \
  --region us-east-1
```

## Model Access Issues

If you get access denied errors:
1. Go to AWS Bedrock Console
2. Navigate to "Model access" 
3. Request access to the models you want to use
4. Wait for approval (usually instant for Claude models)

## Status
🔧 **NEEDS FIX** - Update model ID to a valid/available model
💡 **RECOMMENDED** - Use Claude 3 Haiku for reliability and high token limit