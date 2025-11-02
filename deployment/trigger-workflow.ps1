#!/usr/bin/env pwsh

# Manual Workflow Trigger
# Triggers the complete SAM opportunity analysis workflow with Bedrock AI

param(
    [string]$Region = "us-east-1",
    [string]$BucketPrefix = "l3harris-qhan",
    [string]$Environment = "dev"
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  SAM.GOV OPPORTUNITY ANALYSIS WORKFLOW" -ForegroundColor Cyan  
Write-Host "  (Manual Trigger - Bedrock AI)" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$DataInBucket = "$BucketPrefix-sam-data-in-$Environment"
$JsonProcessorFunction = "$BucketPrefix-sam-json-processor-$Environment"

# Step 1: Find the latest SAM opportunities file
Write-Host "Step 1: Finding latest SAM opportunities file..." -ForegroundColor Yellow
$latestFile = aws s3 ls "s3://$DataInBucket/" --region $Region | 
    Where-Object { $_ -match 'SAM_Opportunities.*\.json' } | 
    Select-Object -Last 1

if (!$latestFile) {
    Write-Host "ERROR: No SAM opportunities files found in $DataInBucket" -ForegroundColor Red
    exit 1
}

$fileName = ($latestFile -split '\s+')[-1]
Write-Host "   Found: $fileName" -ForegroundColor Green

# Step 2: Trigger JSON Processor
Write-Host "`nStep 2: Triggering JSON Processor to extract opportunities..." -ForegroundColor Yellow

$event = @{
    Records = @(
        @{
            s3 = @{
                bucket = @{ name = $DataInBucket }
                object = @{ key = $fileName }
            }
        }
    )
} | ConvertTo-Json -Depth 10 -Compress

# Use ASCII encoding to avoid AWS CLI issues
$event | Out-File -FilePath "trigger-event.json" -Encoding ascii -NoNewline

aws lambda invoke `
    --function-name $JsonProcessorFunction `
    --region $Region `
    --cli-binary-format raw-in-base64-out `
    --payload file://trigger-event.json `
    processor-response.json

if ($LASTEXITCODE -eq 0) {
    Write-Host "   JSON Processor triggered successfully" -ForegroundColor Green
    $response = Get-Content processor-response.json | ConvertFrom-Json
    Write-Host "   Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Gray
} else {
    Write-Host "   ERROR: Failed to trigger JSON Processor" -ForegroundColor Red
    exit 1
}

# Step 3: Wait for processing
Write-Host "`nStep 3: Waiting for opportunities to be extracted..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Step 4: Check SQS queue for messages
Write-Host "`nStep 4: Checking SQS queue for extracted opportunities..." -ForegroundColor Yellow
$queueUrl = "https://sqs.$Region.amazonaws.com/160936122037/$BucketPrefix-sqs-sam-json-messages-$Environment"

$queueAttrs = aws sqs get-queue-attributes `
    --queue-url $queueUrl `
    --attribute-names ApproximateNumberOfMessages `
    --region $Region `
    --query 'Attributes.ApproximateNumberOfMessages' `
    --output text

Write-Host "   Messages in queue: $queueAttrs" -ForegroundColor Green

if ([int]$queueAttrs -gt 0) {
    Write-Host "`nStep 5: Processing messages with Bedrock AI..." -ForegroundColor Yellow
    Write-Host "   The sam-sqs-generate-match-reports Lambda is configured to:" -ForegroundColor Gray
    Write-Host "   - Read opportunities from SQS" -ForegroundColor Gray
    Write-Host "   - Use Bedrock AI to analyze each opportunity" -ForegroundColor Gray
    Write-Host "   - Match against company capabilities" -ForegroundColor Gray
    Write-Host "   - Generate match reports with recommendations" -ForegroundColor Gray
    
    # The Lambda is triggered automatically by SQS, but we can also trigger it manually
    Write-Host "`n   Note: SQS will automatically trigger the match reports Lambda" -ForegroundColor Cyan
    Write-Host "   Or you can trigger it manually with:" -ForegroundColor Cyan
    Write-Host "   aws lambda invoke --function-name $BucketPrefix-sam-sqs-generate-match-reports-$Environment ..." -ForegroundColor Gray
} else {
    Write-Host "`n   WARNING: No messages in SQS queue. JSON processor may still be running." -ForegroundColor Yellow
    Write-Host "   Check CloudWatch Logs for the json-processor Lambda function" -ForegroundColor Yellow
}

# Clean up
Remove-Item -Force trigger-event.json, processor-response.json -ErrorAction SilentlyContinue

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  WORKFLOW TRIGGER COMPLETE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Monitor CloudWatch Logs for each Lambda function" -ForegroundColor White
Write-Host "2. Check S3 buckets for generated reports:" -ForegroundColor White
Write-Host "   - $BucketPrefix-sam-matching-out-sqs-$Environment (match reports)" -ForegroundColor Gray
Write-Host "   - $BucketPrefix-sam-matching-out-runs-$Environment (run summaries)" -ForegroundColor Gray
Write-Host "   - $BucketPrefix-sam-website-$Environment (HTML reports)" -ForegroundColor Gray
Write-Host "3. Enable S3 event notifications for automatic workflow" -ForegroundColor White

