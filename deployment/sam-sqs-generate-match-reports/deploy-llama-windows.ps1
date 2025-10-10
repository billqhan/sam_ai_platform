# PowerShell script to deploy Llama model update on Windows

Write-Host "🦙 Deploying Llama Model Update..." -ForegroundColor Green

# Step 1: Update Lambda Environment Variables
Write-Host "Step 1: Updating Lambda environment variables..." -ForegroundColor Blue

aws lambda update-function-configuration `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --environment "Variables={MODEL_ID_DESC=us.meta.llama3-70b-instruct-v1:0,MODEL_ID_MATCH=us.meta.llama3-70b-instruct-v1:0,MAX_TOKENS=8000,TEMPERATURE=0.1,DEBUG_MODE=true,OUTPUT_BUCKET_SQS=ktest-sam-matching-out-sqs-dev,OUTPUT_BUCKET_RUNS=ktest-sam-matching-out-runs-dev}" `
  --region us-east-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Environment variables updated successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to update environment variables" -ForegroundColor Red
    exit 1
}

# Step 2: Deploy Updated Lambda Code
Write-Host "Step 2: Deploying updated Lambda code..." -ForegroundColor Blue

aws lambda update-function-code `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --zip-file fileb://lambda-deployment-llama-support.zip `
  --region us-east-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Lambda code deployed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to deploy Lambda code" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Llama model deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Expected results:" -ForegroundColor Yellow
Write-Host "- Higher token limit (8000 vs 4096)" -ForegroundColor White
Write-Host "- Better quality LLM analysis" -ForegroundColor White
Write-Host "- No more 'Too many input tokens' errors" -ForegroundColor White
Write-Host ""
Write-Host "Monitor logs with:" -ForegroundColor Yellow
Write-Host "aws logs tail /aws/lambda/ktest-sam-sqs-generate-match-reports-dev --follow" -ForegroundColor Gray