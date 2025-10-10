# PowerShell script to fix the model ID issue on Windows

Write-Host "Fixing Lambda model configuration..." -ForegroundColor Green

# Option 1: Try correct Llama model ID
Write-Host "`n=== Option 1: Llama Model ===" -ForegroundColor Yellow
Write-Host "aws lambda update-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --environment `"Variables={MODEL_ID_DESC=meta.llama3-70b-instruct-v1:0,MODEL_ID_MATCH=meta.llama3-70b-instruct-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev}`" --region us-east-1"

Write-Host "`n=== Option 2: Claude 3 Haiku (Recommended) ===" -ForegroundColor Yellow  
Write-Host "aws lambda update-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --environment `"Variables={MODEL_ID_DESC=anthropic.claude-3-haiku-20240307-v1:0,MODEL_ID_MATCH=anthropic.claude-3-haiku-20240307-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev}`" --region us-east-1"

Write-Host "`n=== Option 3: Claude 3 Sonnet ===" -ForegroundColor Yellow
Write-Host "aws lambda update-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --environment `"Variables={MODEL_ID_DESC=anthropic.claude-3-sonnet-20240229-v1:0,MODEL_ID_MATCH=anthropic.claude-3-sonnet-20240229-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev}`" --region us-east-1"

Write-Host "`n=== Check Available Models ===" -ForegroundColor Cyan
Write-Host "aws bedrock list-foundation-models --region us-east-1"
Write-Host "aws bedrock list-foundation-models --by-provider anthropic --region us-east-1"

Write-Host "`nCopy and paste one of the commands above into your terminal." -ForegroundColor Green
Write-Host "Recommended: Use Option 2 (Claude 3 Haiku)" -ForegroundColor Green