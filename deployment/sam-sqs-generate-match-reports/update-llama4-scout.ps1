# PowerShell script to update Lambda to use Llama 4 Scout model

Write-Host "Updating Lambda to use Llama 4 Scout model..." -ForegroundColor Green

# Update Lambda environment variables
$command = @"
aws lambda update-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --environment "Variables={MODEL_ID_DESC=meta.llama4-scout-17b-instruct-v1:0,MODEL_ID_MATCH=meta.llama4-scout-17b-instruct-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev,BEDROCK_REGION=us-east-1,MATCH_THRESHOLD=0.7,MAX_ATTACHMENT_FILES=4,MAX_DESCRIPTION_CHARS=20000,MAX_ATTACHMENT_CHARS=16000,PROCESS_DELAY_SECONDS=60}" --region us-east-1
"@

Write-Host "Executing command:" -ForegroundColor Yellow
Write-Host $command -ForegroundColor Cyan

# Execute the command
Invoke-Expression $command

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Successfully updated Lambda environment variables!" -ForegroundColor Green
    Write-Host "Model is now set to: meta.llama4-scout-17b-instruct-v1:0" -ForegroundColor Green
    
    Write-Host "`nVerifying configuration..." -ForegroundColor Yellow
    aws lambda get-function-configuration --function-name ktest-sam-sqs-generate-match-reports-dev --query 'Environment.Variables' --region us-east-1
} else {
    Write-Host "`n❌ Failed to update Lambda environment variables" -ForegroundColor Red
    Write-Host "Please check if the model ID is correct and you have access to it" -ForegroundColor Yellow
    
    Write-Host "`nTo check available models:" -ForegroundColor Cyan
    Write-Host "aws bedrock list-foundation-models --by-provider meta --region us-east-1" -ForegroundColor Gray
}