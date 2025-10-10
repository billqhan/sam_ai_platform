# Converse API Fix Deployment - v6

## Overview

This deployment fixes critical API issues in the LLM match report generation system:

1. **ValidationException Fix**: Replaced deprecated `invoke_model` API with modern `converse` API
2. **Return Value Fix**: Fixed unpacking error in `extract_opportunity_info` method call

## Issues Fixed

### 1. ValidationException: Malformed input request
**Error**: `extraneous key [max_tokens] is not permitted`

**Root Cause**: Using old `invoke_model` API format with `max_tokens` parameter

**Fix**: Switched to Bedrock Converse API which uses `maxTokens` in `inferenceConfig`

### 2. ValueError: not enough values to unpack
**Error**: `ValueError: not enough values to unpack (expected 3, got 2)`

**Root Cause**: Lambda function expecting 3 return values from `extract_opportunity_info` but method only returns 2

**Fix**: Updated Lambda function to correctly unpack 2 values and set `llm_success` separately

## Key Changes

### API Migration
- **Before**: `bedrock_runtime.invoke_model()` with old format
- **After**: `bedrock_runtime.converse()` with modern format

### Request Format
```python
# Old format (causing ValidationException)
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 8000,  # ❌ Not allowed
    "temperature": 0.1,
    "messages": [...]
}

# New Converse API format
{
    "modelId": "amazon.nova-pro-v1:0",
    "messages": [...],
    "inferenceConfig": {
        "maxTokens": 8000,  # ✅ Correct format
        "temperature": 0.1
    }
}
```

### Response Parsing
- **Before**: `json.loads(response['body'].read())`
- **After**: Direct access to `response['output']['message']['content'][0]['text']`

## Files Updated

- `shared/llm_data_extraction.py`:
  - Updated `invoke_model()` to use Converse API
  - Added `_extract_converse_response()` method
  - Updated `_prepare_converse_request()` method
- `lambda_function.py`:
  - Fixed return value unpacking for `extract_opportunity_info()`

## Benefits

1. **Modern API**: Uses latest Bedrock Converse API for better model compatibility
2. **Model Flexibility**: Easier to switch between different models (Claude, Nova Pro, etc.)
3. **Error Resolution**: Eliminates ValidationException and unpacking errors
4. **Future-Proof**: Converse API is the recommended approach for Bedrock

## Deployment

### Automatic Deployment
```powershell
.\deploy-converse-api-fix.ps1
```

### Manual Deployment
```powershell
aws lambda update-function-code --function-name ktest-sam-sqs-generate-match-reports-dev --zip-file fileb://lambda-deployment-package-v6-converse-api-fix.zip --region us-east-1
```

## Testing

Test with the same opportunity that was causing errors:
```bash
aws s3 cp s3://m-sam-extracted-json-resources-test/2025-10-08/36C24526Q0057.json s3://ktest-sam-extracted-json-resources-dev/36C24526Q0057/36C24526Q0057.json
```

Expected behavior:
- No ValidationException errors
- No unpacking errors
- Successful LLM processing with Converse API
- Proper hallucination prevention (from v5 fix)

## Version History

- **v6**: Converse API migration + unpacking fix
- **v5**: Hallucination prevention fix
- **v4**: Attachments processing fix
- **v3**: Final LLM integration
- **v2**: Model ID fixes
- **v1**: Initial LLM implementation

This deployment ensures compatibility with modern Bedrock APIs and resolves the critical runtime errors.