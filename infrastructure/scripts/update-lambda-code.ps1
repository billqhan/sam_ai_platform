# Update Lambda Function Code Script
# This script packages and updates Lambda function code with dependencies

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$true)]
    [string]$TemplatesBucket,
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "",
    
    [Parameter(Mandatory=$false)]
    [string]$LambdaName = "sam-gov-daily-download",
    
    [Parameter(Mandatory=$false)]
    [switch]$AllFunctions
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

# Define Lambda functions and their source paths
$LambdaFunctions = @{
    "sam-gov-daily-download" = "src/lambdas/sam-gov-daily-download"
    "sam-json-processor" = "src/lambdas/sam-json-processor"
    "sam-sqs-generate-match-reports" = "src/lambdas/sam-sqs-generate-match-reports"
    "sam-produce-user-report" = "src/lambdas/sam-produce-user-report"
    "sam-email-notification" = "src/lambdas/sam-email-notification"
    "sam-daily-email-notification" = "src/lambdas/sam-daily-email-notification"
    "sam-merge-and-archive-result-logs" = "src/lambdas/sam-merge-and-archive-result-logs"
    "sam-produce-web-reports" = "src/lambdas/sam-produce-web-reports"
}

function Update-LambdaFunction {
    param(
        [string]$FunctionName,
        [string]$SourcePath
    )
    
    Write-Host "[INFO] Processing Lambda function: $FunctionName" -ForegroundColor Blue
    
    # Construct full function name with prefix and environment
    $FullFunctionName = if ($BucketPrefix) {
        "$BucketPrefix-$FunctionName-$Environment"
    } else {
        "$FunctionName-$Environment"
    }
    
    # Check if function exists
    try {
        aws lambda get-function --function-name $FullFunctionName --region us-east-1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARNING] Function $FullFunctionName not found, skipping..." -ForegroundColor Yellow
            return
        }
    } catch {
        Write-Host "[WARNING] Function $FullFunctionName not found, skipping..." -ForegroundColor Yellow
        return
    }
    
    # Package the Lambda function
    $PackageResult = & "$ScriptDir\package-lambda.ps1" -LambdaName $FunctionName -SourcePath $SourcePath -S3Bucket $TemplatesBucket
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to package $FunctionName" -ForegroundColor Red
        return
    }
    
    # Update Lambda function code
    Write-Host "[INFO] Updating Lambda function code: $FullFunctionName" -ForegroundColor Blue
    
    aws lambda update-function-code `
        --function-name $FullFunctionName `
        --s3-bucket $TemplatesBucket `
        --s3-key $PackageResult.S3Key `
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
    } else {
        Write-Host "[ERROR] Failed to update $FullFunctionName" -ForegroundColor Red
    }
}

Write-Host "=== Lambda Function Code Update ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor White
Write-Host "Bucket Prefix: $BucketPrefix" -ForegroundColor White
Write-Host "Templates Bucket: $TemplatesBucket" -ForegroundColor White
Write-Host ""

if ($AllFunctions) {
    Write-Host "[INFO] Updating all Lambda functions..." -ForegroundColor Blue
    
    foreach ($Function in $LambdaFunctions.GetEnumerator()) {
        $SourcePath = Join-Path $ProjectRoot $Function.Value
        if (Test-Path $SourcePath) {
            Update-LambdaFunction -FunctionName $Function.Key -SourcePath $SourcePath
            Write-Host ""
        } else {
            Write-Host "[WARNING] Source path not found: $SourcePath" -ForegroundColor Yellow
        }
    }
} else {
    if ($LambdaFunctions.ContainsKey($LambdaName)) {
        $SourcePath = Join-Path $ProjectRoot $LambdaFunctions[$LambdaName]
        if (Test-Path $SourcePath) {
            Update-LambdaFunction -FunctionName $LambdaName -SourcePath $SourcePath
        } else {
            Write-Host "[ERROR] Source path not found: $SourcePath" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[ERROR] Unknown Lambda function: $LambdaName" -ForegroundColor Red
        Write-Host "Available functions: $($LambdaFunctions.Keys -join ', ')" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "[SUCCESS] Lambda function update process completed!" -ForegroundColor Green