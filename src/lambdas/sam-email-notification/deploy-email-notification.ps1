#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy SAM Email Notification Lambda with SES configuration

.DESCRIPTION
    This script deploys the email notification lambda function and configures
    the necessary AWS resources including SES verification, S3 triggers, and IAM permissions.

.PARAMETER Environment
    The deployment environment (dev, staging, prod)

.PARAMETER BucketPrefix
    The prefix for S3 bucket names (e.g., "ktest")

.PARAMETER FromEmail
    The verified SES sender email address

.PARAMETER SubscribersBucket
    S3 bucket containing the subscribers CSV file

.PARAMETER SubscribersFile
    Name of the subscribers CSV file (default: subscribers.csv)

.PARAMETER ResponseBucket
    S3 bucket where RTF files are stored (default: m-sam-opportunity-responses)

.EXAMPLE
    .\deploy-email-notification.ps1 -Environment "dev" -BucketPrefix "ktest" -FromEmail "noreply@company.com" -SubscribersBucket "company-config"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Environment,
    
    [Parameter(Mandatory=$true)]
    [string]$BucketPrefix,
    
    [Parameter(Mandatory=$true)]
    [string]$FromEmail,
    
    [Parameter(Mandatory=$true)]
    [string]$SubscribersBucket,
    
    [Parameter(Mandatory=$false)]
    [string]$SubscribersFile = "subscribers.csv",
    
    [Parameter(Mandatory=$false)]
    [string]$ResponseBucket = "m-sam-opportunity-responses",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$false)]
    [string]$TemplatesBucket = "m2-sam-templates-bucket"
)

# Set error handling
$ErrorActionPreference = "Stop"

# Function names
$LambdaName = "$BucketPrefix-sam-email-notification-$Environment"

Write-Host "=== SAM Email Notification Deployment ===" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Lambda Name: $LambdaName" -ForegroundColor Yellow
Write-Host "From Email: $FromEmail" -ForegroundColor Yellow
Write-Host "Subscribers Bucket: $SubscribersBucket" -ForegroundColor Yellow

# Step 1: Deploy Lambda Function
Write-Host "`n1. Deploying Lambda Function..." -ForegroundColor Cyan
try {
    & ".\infrastructure\scripts\update-lambda-code.ps1" -Environment $Environment -TemplatesBucket $TemplatesBucket -BucketPrefix $BucketPrefix -LambdaName "sam-email-notification"
    Write-Host "✓ Lambda function deployed successfully" -ForegroundColor Green
} catch {
    Write-Error "Failed to deploy lambda function: $_"
    exit 1
}

# Step 2: Configure Environment Variables
Write-Host "`n2. Configuring Environment Variables..." -ForegroundColor Cyan
$EnvVars = @{
    "FROM_EMAIL" = $FromEmail
    "SUBSCRIBERS_BUCKET" = $SubscribersBucket
    "SUBSCRIBERS_FILE" = $SubscribersFile
    "SES_REGION" = $Region
    "EMAIL_SUBJECT_TEMPLATE" = "AWS AI-Powered RFI/RFP Response for {solicitation_number}"
    "EMAIL_BODY" = "Dear Team, here is the latest match for your review."
}

$EnvVarsJson = ($EnvVars | ConvertTo-Json -Compress) -replace '"', '\"'

try {
    aws lambda update-function-configuration --function-name $LambdaName --environment "Variables=$EnvVarsJson" --region $Region
    Write-Host "✓ Environment variables configured" -ForegroundColor Green
} catch {
    Write-Error "Failed to configure environment variables: $_"
    exit 1
}

# Step 3: Add S3 Permission for Lambda
Write-Host "`n3. Adding S3 Permission for Lambda..." -ForegroundColor Cyan
$SourceArn = "arn:aws:s3:::$ResponseBucket"
try {
    aws lambda add-permission --function-name $LambdaName --principal s3.amazonaws.com --action lambda:InvokeFunction --source-arn $SourceArn --statement-id s3-email-trigger-permission --region $Region 2>$null
    Write-Host "✓ S3 permission added (or already exists)" -ForegroundColor Green
} catch {
    Write-Host "⚠ S3 permission may already exist" -ForegroundColor Yellow
}

# Step 4: Configure S3 Event Notification
Write-Host "`n4. Configuring S3 Event Notification..." -ForegroundColor Cyan
$LambdaArn = "arn:aws:lambda:$Region" + ":" + (aws sts get-caller-identity --query Account --output text) + ":function:$LambdaName"

$NotificationConfig = @{
    LambdaConfigurations = @(
        @{
            Id = "RTFEmailNotification"
            LambdaFunctionArn = $LambdaArn
            Events = @("s3:ObjectCreated:*")
            Filter = @{
                Key = @{
                    FilterRules = @(
                        @{
                            Name = "suffix"
                            Value = ".rtf"
                        }
                    )
                }
            }
        }
    )
} | ConvertTo-Json -Depth 10

# Save config to temp file
$ConfigFile = "s3-email-notification-config.json"
$NotificationConfig | Out-File -FilePath $ConfigFile -Encoding UTF8

try {
    aws s3api put-bucket-notification-configuration --bucket $ResponseBucket --notification-configuration "file://$ConfigFile" --region $Region
    Remove-Item $ConfigFile -Force
    Write-Host "✓ S3 event notification configured" -ForegroundColor Green
} catch {
    Remove-Item $ConfigFile -Force -ErrorAction SilentlyContinue
    Write-Error "Failed to configure S3 event notification: $_"
    exit 1
}

# Step 5: Verify SES Email (if not already verified)
Write-Host "`n5. Checking SES Email Verification..." -ForegroundColor Cyan
try {
    $VerificationStatus = aws ses get-identity-verification-attributes --identities $FromEmail --region $Region --query "VerificationAttributes.'$FromEmail'.VerificationStatus" --output text 2>$null
    
    if ($VerificationStatus -eq "Success") {
        Write-Host "✓ Email $FromEmail is already verified in SES" -ForegroundColor Green
    } else {
        Write-Host "⚠ Email $FromEmail is not verified in SES" -ForegroundColor Yellow
        Write-Host "  Attempting to send verification email..." -ForegroundColor Yellow
        aws ses verify-email-identity --email-address $FromEmail --region $Region
        Write-Host "  ✓ Verification email sent to $FromEmail" -ForegroundColor Green
        Write-Host "  Please check your email and click the verification link" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Could not check SES verification status" -ForegroundColor Yellow
    Write-Host "  Please manually verify $FromEmail in the SES console" -ForegroundColor Yellow
}

# Step 6: Check if subscribers file exists
Write-Host "`n6. Checking Subscribers File..." -ForegroundColor Cyan
try {
    aws s3 head-object --bucket $SubscribersBucket --key $SubscribersFile --region $Region >$null 2>&1
    Write-Host "✓ Subscribers file found: s3://$SubscribersBucket/$SubscribersFile" -ForegroundColor Green
} catch {
    Write-Host "⚠ Subscribers file not found: s3://$SubscribersBucket/$SubscribersFile" -ForegroundColor Yellow
    Write-Host "  You can create one using:" -ForegroundColor Yellow
    Write-Host "  python create-sample-subscribers.py --bucket $SubscribersBucket --file $SubscribersFile" -ForegroundColor Yellow
}

# Step 7: Display IAM Policy Requirements
Write-Host "`n7. IAM Policy Requirements..." -ForegroundColor Cyan
Write-Host "Ensure the lambda execution role has these permissions:" -ForegroundColor Yellow
Write-Host "- s3:GetObject on $ResponseBucket/* and $SubscribersBucket/*" -ForegroundColor White
Write-Host "- ses:SendRawEmail" -ForegroundColor White
Write-Host "- logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents" -ForegroundColor White

# Summary
Write-Host "`n=== Deployment Summary ===" -ForegroundColor Green
Write-Host "✓ Lambda Function: $LambdaName" -ForegroundColor Green
Write-Host "✓ Trigger: S3 RTF files in $ResponseBucket" -ForegroundColor Green
Write-Host "✓ Sender Email: $FromEmail" -ForegroundColor Green
Write-Host "✓ Subscribers: s3://$SubscribersBucket/$SubscribersFile" -ForegroundColor Green

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Verify $FromEmail in SES if not already done" -ForegroundColor White
Write-Host "2. Upload subscribers CSV to s3://$SubscribersBucket/$SubscribersFile" -ForegroundColor White
Write-Host "3. Test by uploading an RTF file to $ResponseBucket" -ForegroundColor White
Write-Host "4. Check CloudWatch logs: /aws/lambda/$LambdaName" -ForegroundColor White

Write-Host "`nDeployment completed successfully!" -ForegroundColor Green