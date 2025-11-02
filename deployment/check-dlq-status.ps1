#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check DLQ status and analyze message patterns

.DESCRIPTION
    This script checks the dead letter queue status and provides insights into:
    1. Number of messages in DLQ
    2. Recent message patterns
    3. Lambda function error rates
    4. SQS queue metrics

.PARAMETER Environment
    Environment to check (dev, prod)

.PARAMETER BucketPrefix
    Optional bucket prefix for resource naming

.EXAMPLE
    .\check-dlq-status.ps1 -Environment dev
    .\check-dlq-status.ps1 -Environment prod -BucketPrefix mycompany
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

Write-Host "Checking DLQ Status for Environment: $Environment" -ForegroundColor Green

# Determine resource names
$DlqName = if ($BucketPrefix) { "$BucketPrefix-sqs-sam-json-messages-dlq-$Environment" } else { "sqs-sam-json-messages-dlq-$Environment" }
$QueueName = if ($BucketPrefix) { "$BucketPrefix-sqs-sam-json-messages-$Environment" } else { "sqs-sam-json-messages-$Environment" }
$LambdaFunctionName = if ($BucketPrefix) { "$BucketPrefix-sam-sqs-generate-match-reports-$Environment" } else { "sam-sqs-generate-match-reports-$Environment" }

Write-Host "Checking Resources:" -ForegroundColor Yellow
Write-Host "  DLQ Name: $DlqName"
Write-Host "  Main Queue: $QueueName"
Write-Host "  Lambda Function: $LambdaFunctionName"
Write-Host ""

try {
    # Get DLQ URL
    $DlqUrl = aws sqs get-queue-url --queue-name $DlqName --query "QueueUrl" --output text 2>$null
    $MainQueueUrl = aws sqs get-queue-url --queue-name $QueueName --query "QueueUrl" --output text 2>$null
    
    if (-not $DlqUrl) {
        Write-Host "ERROR: DLQ not found: $DlqName" -ForegroundColor Red
        exit 1
    }
    
    if (-not $MainQueueUrl) {
        Write-Host "ERROR: Main queue not found: $QueueName" -ForegroundColor Red
        exit 1
    }
    
    # Check DLQ attributes
    Write-Host "Dead Letter Queue Status:" -ForegroundColor Blue
    $DlqAttributes = aws sqs get-queue-attributes --queue-url $DlqUrl --attribute-names All --output json | ConvertFrom-Json
    
    $DlqMessageCount = [int]$DlqAttributes.Attributes.ApproximateNumberOfMessages
    $DlqVisibilityTimeout = [int]$DlqAttributes.Attributes.VisibilityTimeoutSeconds
    $DlqRetentionPeriod = [int]$DlqAttributes.Attributes.MessageRetentionPeriod
    
    Write-Host "  Messages in DLQ: $DlqMessageCount" -ForegroundColor $(if ($DlqMessageCount -gt 0) { "Red" } else { "Green" })
    Write-Host "  Visibility Timeout: $DlqVisibilityTimeout seconds"
    Write-Host "  Message Retention: $($DlqRetentionPeriod / 86400) days"
    
    # Check main queue attributes
    Write-Host ""
    Write-Host "Main Queue Status:" -ForegroundColor Blue
    $MainQueueAttributes = aws sqs get-queue-attributes --queue-url $MainQueueUrl --attribute-names All --output json | ConvertFrom-Json
    
    $MainMessageCount = [int]$MainQueueAttributes.Attributes.ApproximateNumberOfMessages
    $MainVisibilityTimeout = [int]$MainQueueAttributes.Attributes.VisibilityTimeoutSeconds
    $MaxReceiveCount = $MainQueueAttributes.Attributes.RedrivePolicy | ConvertFrom-Json | Select-Object -ExpandProperty maxReceiveCount
    
    Write-Host "  Messages in Main Queue: $MainMessageCount"
    Write-Host "  Visibility Timeout: $MainVisibilityTimeout seconds" -ForegroundColor $(if ($MainVisibilityTimeout -ge 1800) { "Green" } else { "Yellow" })
    Write-Host "  Max Receive Count: $MaxReceiveCount"
    
    # Check Lambda function status
    Write-Host ""
    Write-Host "Lambda Function Status:" -ForegroundColor Blue
    
    try {
        $LambdaConfig = aws lambda get-function-configuration --function-name $LambdaFunctionName --output json | ConvertFrom-Json
        Write-Host "  Function State: $($LambdaConfig.State)" -ForegroundColor $(if ($LambdaConfig.State -eq "Active") { "Green" } else { "Red" })
        Write-Host "  Timeout: $($LambdaConfig.Timeout) seconds"
        Write-Host "  Memory: $($LambdaConfig.MemorySize) MB"
        Write-Host "  Last Modified: $($LambdaConfig.LastModified)"
        
        # Check event source mapping
        $EventSourceMappings = aws lambda list-event-source-mappings --function-name $LambdaFunctionName --output json | ConvertFrom-Json
        $SqsMapping = $EventSourceMappings.EventSourceMappings | Where-Object { $_.EventSourceArn -like "*sqs-sam-json-messages*" }
        
        if ($SqsMapping) {
            Write-Host "  Event Source Mapping State: $($SqsMapping.State)" -ForegroundColor $(if ($SqsMapping.State -eq "Enabled") { "Green" } else { "Red" })
            Write-Host "  Batch Size: $($SqsMapping.BatchSize)"
            Write-Host "  Function Response Types: $($SqsMapping.FunctionResponseTypes -join ', ')"
        }
        
    } catch {
        Write-Host "  ERROR: Could not retrieve Lambda function details" -ForegroundColor Red
    }
    
    # Get recent CloudWatch metrics
    Write-Host ""
    Write-Host "Recent Metrics (Last 24 hours):" -ForegroundColor Blue
    
    $EndTime = Get-Date
    $StartTime = $EndTime.AddDays(-1)
    
    try {
        # Lambda errors
        $LambdaErrors = aws cloudwatch get-metric-statistics `
            --namespace "AWS/Lambda" `
            --metric-name "Errors" `
            --dimensions Name=FunctionName,Value=$LambdaFunctionName `
            --start-time $StartTime.ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --end-time $EndTime.ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --period 3600 `
            --statistics Sum `
            --output json | ConvertFrom-Json
        
        $TotalErrors = ($LambdaErrors.Datapoints | Measure-Object -Property Sum -Sum).Sum
        Write-Host "  Lambda Errors (24h): $TotalErrors" -ForegroundColor $(if ($TotalErrors -gt 0) { "Red" } else { "Green" })
        
        # Lambda invocations
        $LambdaInvocations = aws cloudwatch get-metric-statistics `
            --namespace "AWS/Lambda" `
            --metric-name "Invocations" `
            --dimensions Name=FunctionName,Value=$LambdaFunctionName `
            --start-time $StartTime.ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --end-time $EndTime.ToString("yyyy-MM-ddTHH:mm:ssZ") `
            --period 3600 `
            --statistics Sum `
            --output json | ConvertFrom-Json
        
        $TotalInvocations = ($LambdaInvocations.Datapoints | Measure-Object -Property Sum -Sum).Sum
        Write-Host "  Lambda Invocations (24h): $TotalInvocations"
        
        if ($TotalInvocations -gt 0 -and $TotalErrors -gt 0) {
            $ErrorRate = [math]::Round(($TotalErrors / $TotalInvocations) * 100, 2)
            Write-Host "  Error Rate: $ErrorRate%" -ForegroundColor $(if ($ErrorRate -gt 10) { "Red" } elseif ($ErrorRate -gt 5) { "Yellow" } else { "Green" })
        }
        
    } catch {
        Write-Host "  WARNING: Could not retrieve CloudWatch metrics" -ForegroundColor Yellow
    }
    
    # Sample DLQ messages if any exist
    if ($DlqMessageCount -gt 0) {
        Write-Host ""
        Write-Host "Sample DLQ Messages:" -ForegroundColor Blue
        
        try {
            $SampleMessages = aws sqs receive-message --queue-url $DlqUrl --max-number-of-messages 3 --output json | ConvertFrom-Json
            
            if ($SampleMessages.Messages) {
                foreach ($Message in $SampleMessages.Messages) {
                    Write-Host "  Message ID: $($Message.MessageId)"
                    Write-Host "  Receive Count: $($Message.Attributes.ApproximateReceiveCount)"
                    
                    # Try to parse the message body
                    try {
                        $Body = $Message.Body | ConvertFrom-Json
                        if ($Body.Records -and $Body.Records[0].s3) {
                            $S3Info = $Body.Records[0].s3
                            Write-Host "  S3 Bucket: $($S3Info.bucket.name)"
                            Write-Host "  S3 Key: $($S3Info.object.key)"
                        }
                    } catch {
                        Write-Host "  Body Preview: $($Message.Body.Substring(0, [Math]::Min(100, $Message.Body.Length)))..."
                    }
                    Write-Host "  ---"
                }
            }
        } catch {
            Write-Host "  WARNING: Could not retrieve sample messages" -ForegroundColor Yellow
        }
    }
    
    # Recommendations
    Write-Host ""
    Write-Host "Recommendations:" -ForegroundColor Cyan
    
    if ($DlqMessageCount -gt 0) {
        Write-Host "  - DLQ contains $DlqMessageCount messages - investigate root cause" -ForegroundColor Red
        Write-Host "  - Check Lambda function logs for detailed error information"
        Write-Host "  - Consider reprocessing messages after fixing issues"
    } else {
        Write-Host "  - DLQ is empty - system appears healthy" -ForegroundColor Green
    }
    
    if ($MainVisibilityTimeout -lt 1800) {
        Write-Host "  - Main queue visibility timeout ($MainVisibilityTimeout s) may be too low" -ForegroundColor Yellow
        Write-Host "  - Consider increasing to 1800s (30 minutes) or 6x Lambda timeout"
    }
    
    if ($TotalErrors -gt 0) {
        Write-Host "  - Lambda function has $TotalErrors errors in the last 24 hours" -ForegroundColor Red
        Write-Host "  - Check CloudWatch logs: aws logs tail /aws/lambda/$LambdaFunctionName --follow"
    }
    
} catch {
    Write-Host "ERROR: Error checking DLQ status: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "DLQ Status Check Complete" -ForegroundColor Green