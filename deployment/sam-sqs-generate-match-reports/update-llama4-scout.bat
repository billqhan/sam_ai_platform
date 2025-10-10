@echo off
echo Updating Lambda to use Llama 4 Scout model...

aws lambda update-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --environment "Variables={MODEL_ID_DESC=meta.llama4-scout-17b-instruct-v1:0,MODEL_ID_MATCH=meta.llama4-scout-17b-instruct-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev,BEDROCK_REGION=us-east-1,MATCH_THRESHOLD=0.7,MAX_ATTACHMENT_FILES=4,MAX_DESCRIPTION_CHARS=20000,MAX_ATTACHMENT_CHARS=16000,PROCESS_DELAY_SECONDS=60}" --region us-east-1

if %errorlevel% equ 0 (
    echo.
    echo ✅ Successfully updated Lambda environment variables!
    echo Model is now set to: meta.llama4-scout-17b-instruct-v1:0
    echo.
    echo Verifying configuration...
    aws lambda get-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --query "Environment.Variables" --region us-east-1
) else (
    echo.
    echo ❌ Failed to update Lambda environment variables
    echo Please check if the model ID is correct and you have access to it
    echo.
    echo To check available models:
    echo aws bedrock list-foundation-models --by-provider meta --region us-east-1
)

pause