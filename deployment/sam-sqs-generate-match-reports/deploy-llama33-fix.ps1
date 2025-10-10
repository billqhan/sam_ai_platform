# Quick fix for Llama 3.3 70B model deployment

Write-Host "🦙 Updating Lambda to use Llama 3.3 70B model..." -ForegroundColor Green

# Update Lambda environment variables with correct model ID
aws lambda update-function-configuration `
  --function-name ktest-sam-sqs-generate-match-reports-dev `
  --environment Variables='{
    "MODEL_ID_DESC":"meta.llama3-3-70b-instruct-v1:0",
    "MODEL_ID_MATCH":"meta.llama3-3-70b-instruct-v1:0",
    "MAX_TOKENS":"8000",
    "TEMPERATURE":"0.1",
    "DEBUG_MODE":"true",
    "OUTPUT_BUCKET_SQS":"ktest-sam-matching-out-sqs-dev",
    "OUTPUT_BUCKET_RUNS":"ktest-sam-matching-out-runs-dev"
  }' `
  --region us-east-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Lambda environment variables updated successfully!" -ForegroundColor Green
    Write-Host "🚀 Model now set to: meta.llama3-3-70b-instruct-v1:0" -ForegroundColor Cyan
} else {
    Write-Host "❌ Failed to update Lambda environment variables" -ForegroundColor Red
}

Write-Host "`n📊 Expected Results:" -ForegroundColor Yellow
Write-Host "- Higher token limit (8K+ tokens)" -ForegroundColor White
Write-Host "- Better quality responses" -ForegroundColor White
Write-Host "- No more 'too many tokens' errors" -ForegroundColor White