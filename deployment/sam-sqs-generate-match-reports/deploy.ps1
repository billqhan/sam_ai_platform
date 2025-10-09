# PowerShell deployment script for sam-sqs-generate-match-reports Lambda function

Write-Host "Starting Lambda deployment preparation..." -ForegroundColor Green

# Set variables
$FUNCTION_NAME = "ktest-sam-sqs-generate-match-reports-dev"
$DEPLOYMENT_PACKAGE = "lambda-deployment-package.zip"
$REGION = "us-east-1"

# Clean up any existing deployment package
if (Test-Path $DEPLOYMENT_PACKAGE) {
    Remove-Item $DEPLOYMENT_PACKAGE
    Write-Host "Cleaned up existing deployment package" -ForegroundColor Yellow
}

# Create deployment package
Write-Host "Creating deployment package..." -ForegroundColor Blue

# Add all files to zip
$compress = @{
    Path = "lambda_function.py", "requirements.txt", "shared"
    CompressionLevel = "Optimal"
    DestinationPath = $DEPLOYMENT_PACKAGE
}
Compress-Archive @compress

Write-Host "Created deployment package: $DEPLOYMENT_PACKAGE" -ForegroundColor Green

# Get package size
$packageSize = (Get-Item $DEPLOYMENT_PACKAGE).Length / 1MB
Write-Host "Package size: $([math]::Round($packageSize, 2)) MB" -ForegroundColor Cyan

# Display deployment instructions
Write-Host ""
Write-Host "DEPLOYMENT INSTRUCTIONS:" -ForegroundColor Magenta
Write-Host "1. Upload the deployment package to AWS Lambda:" -ForegroundColor White
Write-Host "   aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb://$DEPLOYMENT_PACKAGE --region $REGION" -ForegroundColor Gray

Write-Host ""
Write-Host "2. Or use AWS Console:" -ForegroundColor White
Write-Host "   - Go to AWS Lambda Console" -ForegroundColor Gray
Write-Host "   - Find function: $FUNCTION_NAME" -ForegroundColor Gray
Write-Host "   - Upload $DEPLOYMENT_PACKAGE" -ForegroundColor Gray

Write-Host ""
Write-Host "3. Verify environment variables are set:" -ForegroundColor White
Write-Host "   - OUTPUT_BUCKET_SQS" -ForegroundColor Gray
Write-Host "   - OUTPUT_BUCKET_RUNS" -ForegroundColor Gray
Write-Host "   - MODEL_ID_DESC" -ForegroundColor Gray
Write-Host "   - MODEL_ID_MATCH" -ForegroundColor Gray
Write-Host "   - DEBUG_MODE" -ForegroundColor Gray

Write-Host ""
Write-Host "Deployment package ready!" -ForegroundColor Green