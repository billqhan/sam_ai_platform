# Deploy Merge and Archive Lambda Function
# This script packages and deploys the merge and archive lambda function

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "ktest",
    
    [Parameter(Mandatory=$false)]
    [string]$TemplatesBucket = "m2-sam-templates-bucket"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Deploying Merge and Archive Lambda Function ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor White
Write-Host "Bucket Prefix: $BucketPrefix" -ForegroundColor White
Write-Host "Templates Bucket: $TemplatesBucket" -ForegroundColor White
Write-Host ""

# Function name
$LambdaName = "sam-merge-and-archive-result-logs"
$FullFunctionName = "$BucketPrefix-$LambdaName-$Environment"
$SourcePath = "src\lambdas\$LambdaName"

Write-Host "[INFO] Packaging Lambda function..." -ForegroundColor Blue

# Create temporary directory for packaging
$TempDir = Join-Path $env:TEMP "lambda-package-$(Get-Random)"
$PackageDir = Join-Path $TempDir "package"
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

try {
    # Copy source files to package directory
    Write-Host "[INFO] Copying source files..." -ForegroundColor Blue
    Copy-Item -Path "$SourcePath\*" -Destination $PackageDir -Recurse -Force
    
    # Check if requirements.txt exists and install dependencies
    $RequirementsFile = Join-Path $PackageDir "requirements.txt"
    if (Test-Path $RequirementsFile) {
        Write-Host "[INFO] Installing dependencies from requirements.txt..." -ForegroundColor Blue
        
        # Install dependencies to package directory
        & python -m pip install -r $RequirementsFile -t $PackageDir --platform linux_x86_64 --only-binary=:all:
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
        
        # Remove unnecessary files
        Get-ChildItem -Path $PackageDir -Recurse -Include "*.pyc", "__pycache__", "*.dist-info", "*.egg-info" | Remove-Item -Recurse -Force
        Remove-Item -Path $RequirementsFile -Force -ErrorAction SilentlyContinue
    }
    
    # Create ZIP file
    $ZipFile = Join-Path $TempDir "$LambdaName.zip"
    Write-Host "[INFO] Creating ZIP package..." -ForegroundColor Blue
    
    Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipFile -Force
    
    # Upload to S3
    $S3Key = "lambda-packages/$LambdaName.zip"
    Write-Host "[INFO] Uploading to S3: s3://$TemplatesBucket/$S3Key" -ForegroundColor Blue
    
    aws s3 cp $ZipFile "s3://$TemplatesBucket/$S3Key"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to upload to S3" -ForegroundColor Red
        exit 1
    }
    
    # Update Lambda function code
    Write-Host "[INFO] Updating Lambda function code: $FullFunctionName" -ForegroundColor Blue
    
    aws lambda update-function-code `
        --function-name $FullFunctionName `
        --s3-bucket $TemplatesBucket `
        --s3-key $S3Key `
        --region us-east-1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Updated $FullFunctionName successfully!" -ForegroundColor Green
        
        # Wait for update to complete
        Write-Host "[INFO] Waiting for function update to complete..." -ForegroundColor Blue
        aws lambda wait function-updated --function-name $FullFunctionName --region us-east-1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Function update completed!" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Function update may still be in progress" -ForegroundColor Yellow
        }
        
        # Test the function
        Write-Host "[INFO] Testing the function..." -ForegroundColor Blue
        $TestResult = aws lambda invoke --function-name $FullFunctionName --region us-east-1 --payload '{}' response.json
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Function test completed!" -ForegroundColor Green
            if (Test-Path "response.json") {
                $Response = Get-Content "response.json" | ConvertFrom-Json
                Write-Host "Response: $($Response | ConvertTo-Json -Compress)" -ForegroundColor White
                Remove-Item "response.json" -Force
            }
        } else {
            Write-Host "[WARNING] Function test failed" -ForegroundColor Yellow
        }
        
    } else {
        Write-Host "[ERROR] Failed to update $FullFunctionName" -ForegroundColor Red
        exit 1
    }
    
} finally {
    # Clean up temporary directory
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "[SUCCESS] Merge and Archive Lambda deployment completed!" -ForegroundColor Green
Write-Host "The EventBridge rule 'sam-lambda-every-5min-summarizer-dev' should already be configured to trigger this function every 5 minutes." -ForegroundColor Green
Write-Host "The function will process files in: s3://$BucketPrefix-sam-matching-out-runs-$Environment/runs/" -ForegroundColor Green