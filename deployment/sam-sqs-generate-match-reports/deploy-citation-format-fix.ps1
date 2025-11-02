# PowerShell script to deploy the Citation Format fix
Write-Host "Deploying Citation Format Fix..." -ForegroundColor Green

$FUNCTION_NAME = "ktest-sam-sqs-generate-match-reports-dev"
$REGION = "us-east-1"
$PACKAGE_NAME = "lambda-deployment-package-v9-citation-format-fix.zip"

Write-Host "Creating deployment package: $PACKAGE_NAME" -ForegroundColor Yellow

# Remove existing package
if (Test-Path $PACKAGE_NAME) {
    Remove-Item $PACKAGE_NAME -Force
}

# Create package directory
$TEMP_DIR = "temp_package"
if (Test-Path $TEMP_DIR) {
    Remove-Item $TEMP_DIR -Recurse -Force
}
New-Item -ItemType Directory -Path $TEMP_DIR | Out-Null

# Copy files
Write-Host "Copying Lambda function and shared modules..." -ForegroundColor Yellow
Copy-Item "lambda_function.py" "$TEMP_DIR/" -Force
Copy-Item "shared" "$TEMP_DIR/" -Recurse -Force

# Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Set-Location $TEMP_DIR
pip install -r "../requirements.txt" -t . --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install dependencies" -ForegroundColor Red
    Set-Location ..
    Remove-Item $TEMP_DIR -Recurse -Force
    exit 1
}

Set-Location ..

# Create ZIP
Write-Host "Creating ZIP package..." -ForegroundColor Yellow
Compress-Archive -Path "$TEMP_DIR\*" -DestinationPath $PACKAGE_NAME -Force

# Cleanup
Remove-Item $TEMP_DIR -Recurse -Force

if (Test-Path $PACKAGE_NAME) {
    $packageSize = (Get-Item $PACKAGE_NAME).Length / 1MB
    $sizeText = "$([math]::Round($packageSize, 2)) MB"
    Write-Host "Package created successfully: $PACKAGE_NAME ($sizeText)" -ForegroundColor Green
} else {
    Write-Host "Failed to create package" -ForegroundColor Red
    exit 1
}

# Deploy to AWS
Write-Host "Updating Lambda function..." -ForegroundColor Yellow
Write-Host "Function: $FUNCTION_NAME" -ForegroundColor Gray
Write-Host "Region: $REGION" -ForegroundColor Gray

aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file "fileb://$PACKAGE_NAME" --region $REGION

if ($LASTEXITCODE -eq 0) {
    Write-Host "Lambda function updated successfully!" -ForegroundColor Green
    
    Write-Host "`nDeployment Summary:" -ForegroundColor Cyan
    Write-Host "Package: $PACKAGE_NAME" -ForegroundColor Gray
    Write-Host "Function: $FUNCTION_NAME" -ForegroundColor Gray
    Write-Host "Region: $REGION" -ForegroundColor Gray
    Write-Host "Fix: Removed legacy citation formatting that was overriding enhanced citations" -ForegroundColor Gray
    
    Write-Host "`nKey Fix:" -ForegroundColor Yellow
    Write-Host "- Removed validate_and_format_citations call that was converting enhanced citations back to old format" -ForegroundColor Gray
    Write-Host "- Citations now use proper document_title, section_or_page, excerpt format" -ForegroundColor Gray
    Write-Host "- Source filenames properly extracted from KB results" -ForegroundColor Gray
    
    Write-Host "`nTest the fix with:" -ForegroundColor Yellow
    Write-Host "aws s3 cp s3://m-sam-extracted-json-resources-test/2025-10-08/SP330025R5002.json s3://ktest-sam-extracted-json-resources-dev/SP330025R5002/SP330025R5002.json" -ForegroundColor Gray
    
    Write-Host "`nDeployment completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Failed to update Lambda function" -ForegroundColor Red
    Write-Host "Check AWS CLI configuration and permissions" -ForegroundColor Gray
    exit 1
}