#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fix DLQ issue where all messages end up in dead letter queue

.DESCRIPTION
    This script deploys fixes for the SQS DLQ issue:
    1. Increases SQS visibility timeout to 30 minutes (6x Lambda timeout)
    2. Updates Lambda function to properly handle batch failures
    3. Enables partial batch failure reporting for SQS event source mapping

.PARAMETER Environment
    Environment to deploy to (dev, prod)

.PARAMETER BucketPrefix
    Optional bucket prefix for resource naming

.EXAMPLE
    .\fix-dlq-issue.ps1 -Environment dev
    .\fix-dlq-issue.ps1 -Environment prod -BucketPrefix mycompany
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "prod")]
    [string]$Environment,
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = ""
)

# Set error handling
$ErrorActionPreference = "Stop"

Write-Host "Starting DLQ Issue Fix Deployment for Environment: $Environment" -ForegroundColor Green

# Determine stack name
$StackName = if ($BucketPrefix) { "$BucketPrefix-sam-rfp-agent-$Environment" } else { "sam-rfp-agent-$Environment" }
$LambdaFunctionName = if ($BucketPrefix) { "$BucketPrefix-sam-sqs-generate-match-reports-$Environment" } else { "sam-sqs-generate-match-reports-$Environment" }

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Stack Name: $StackName"
Write-Host "  Lambda Function: $LambdaFunctionName"
Write-Host "  Environment: $Environment"

try {
    # Step 1: Update CloudFormation stack with new SQS configuration
    Write-Host "Step 1: Updating CloudFormation stack with SQS visibility timeout fix..." -ForegroundColor Blue
    
    $ParametersFile = "infrastructure/cloudformation/parameters-$Environment.json"
    
    if (Test-Path $ParametersFile) {
        aws cloudformation update-stack `
            --stack-name $StackName `
            --template-body file://infrastructure/cloudformation/main-template.yaml `
            --parameters file://$ParametersFile `
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
        
        Write-Host "Waiting for CloudFormation stack update to complete..."
        aws cloudformation wait stack-update-complete --stack-name $StackName
        Write-Host "CloudFormation stack updated successfully" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Parameters file not found: $ParametersFile" -ForegroundColor Yellow
        Write-Host "   Please update the stack manually or create the parameters file"
    }
    
    # Step 2: Update Lambda function code
    Write-Host "Step 2: Updating Lambda function code..." -ForegroundColor Blue
    
    # Package Lambda function
    $TempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
    $ZipPath = Join-Path $TempDir "lambda-function.zip"
    
    # Copy Lambda function files
    Copy-Item "deployment/sam-sqs-generate-match-reports/lambda_function.py" $TempDir
    Copy-Item "deployment/sam-sqs-generate-match-reports/requirements.txt" $TempDir
    Copy-Item -Recurse "deployment/sam-sqs-generate-match-reports/shared" $TempDir
    
    # Create zip file
    Push-Location $TempDir
    try {
        if (Get-Command "7z" -ErrorAction SilentlyContinue) {
            7z a -tzip $ZipPath * -r
        } elseif (Get-Command "zip" -ErrorAction SilentlyContinue) {
            zip -r $ZipPath *
        } else {
            # Use PowerShell compression as fallback
            Compress-Archive -Path * -DestinationPath $ZipPath -Force
        }
    } finally {
        Pop-Location
    }
    
    # Update Lambda function
    aws lambda update-function-code `
        --function-name $LambdaFunctionName `
        --zip-file fileb://$ZipPath
    
    Write-Host "Lambda function code updated successfully" -ForegroundColor Green
    
    # Step 3: Update Event Source Mapping for partial batch failure support
    Write-Host "Step 3: Updating Event Source Mapping for partial batch failure support..." -ForegroundColor Blue
    
    # Get current event source mappings
    $EventSourceMappings = aws lambda list-event-source-mappings --function-name $LambdaFunctionName --query "EventSourceMappings[?contains(EventSourceArn, 'sqs-sam-json-messages')]" --output json | ConvertFrom-Json
    
    if ($EventSourceMappings.Count -gt 0) {
        $MappingUuid = $EventSourceMappings[0].UUID
        
        aws lambda update-event-source-mapping `
            --uuid $MappingUuid `
            --function-response-types ReportBatchItemFailures
        
        Write-Host "Event Source Mapping updated successfully" -ForegroundColor Green
    } else {
        Write-Host "WARNING: No SQS Event Source Mapping found for function $LambdaFunctionName" -ForegroundColor Yellow
    }
    
    # Cleanup
    Remove-Item -Recurse -Force $TempDir
    
    Write-Host "DLQ Issue Fix Deployment Completed Successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Changes Applied:" -ForegroundColor Yellow
    Write-Host "  - SQS visibility timeout increased to 30 minutes"
    Write-Host "  - Lambda function updated with proper error handling"
    Write-Host "  - Partial batch failure reporting enabled"
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. Monitor the DLQ to verify messages are no longer incorrectly sent there"
    Write-Host "  2. Check CloudWatch logs for proper error handling"
    Write-Host "  3. Test with a few sample messages to verify the fix"
    
} catch {
    Write-Host "ERROR: Deployment failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check the error details above and try again" -ForegroundColor Yellow
    exit 1
}