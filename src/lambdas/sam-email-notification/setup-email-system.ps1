#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick setup script for SAM Email Notification system

.DESCRIPTION
    This script provides a guided setup for the email notification system,
    including creating sample subscribers and deploying the lambda.

.EXAMPLE
    .\setup-email-system.ps1
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "ktest"
)

Write-Host "=== SAM Email Notification Setup ===" -ForegroundColor Green
Write-Host "This script will help you set up the email notification system.`n" -ForegroundColor White

# Get required information
$FromEmail = Read-Host "Enter your verified SES sender email address"
$SubscribersBucket = Read-Host "Enter S3 bucket name for storing subscribers CSV"
$SubscribersFile = Read-Host "Enter subscribers CSV filename (default: subscribers.csv)"
if ([string]::IsNullOrEmpty($SubscribersFile)) { $SubscribersFile = "subscribers.csv" }

Write-Host "`nConfiguration:" -ForegroundColor Yellow
Write-Host "- Environment: $Environment" -ForegroundColor White
Write-Host "- Bucket Prefix: $BucketPrefix" -ForegroundColor White
Write-Host "- From Email: $FromEmail" -ForegroundColor White
Write-Host "- Subscribers Bucket: $SubscribersBucket" -ForegroundColor White
Write-Host "- Subscribers File: $SubscribersFile" -ForegroundColor White

$Confirm = Read-Host "`nProceed with setup? (y/N)"
if ($Confirm -ne "y" -and $Confirm -ne "Y") {
    Write-Host "Setup cancelled." -ForegroundColor Yellow
    exit 0
}

# Step 1: Create sample subscribers file
Write-Host "`n1. Creating sample subscribers file..." -ForegroundColor Cyan
$CreateSample = Read-Host "Create and upload sample subscribers CSV? (Y/n)"
if ($CreateSample -ne "n" -and $CreateSample -ne "N") {
    try {
        python create-sample-subscribers.py --bucket $SubscribersBucket --file $SubscribersFile
        Write-Host "✓ Sample subscribers file created and uploaded" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Failed to create sample file. You can do this manually later." -ForegroundColor Yellow
    }
}

# Step 2: Deploy lambda
Write-Host "`n2. Deploying email notification lambda..." -ForegroundColor Cyan
$Deploy = Read-Host "Deploy the lambda function now? (Y/n)"
if ($Deploy -ne "n" -and $Deploy -ne "N") {
    try {
        & ".\deploy-email-notification.ps1" -Environment $Environment -BucketPrefix $BucketPrefix -FromEmail $FromEmail -SubscribersBucket $SubscribersBucket -SubscribersFile $SubscribersFile
        Write-Host "✓ Lambda deployment completed" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Lambda deployment failed. Check the error above." -ForegroundColor Red
        exit 1
    }
}

# Step 3: Test instructions
Write-Host "`n3. Testing the system..." -ForegroundColor Cyan
Write-Host "To test the email notification system:" -ForegroundColor White
Write-Host "1. Upload a test RTF file:" -ForegroundColor White
Write-Host "   aws s3 cp test_ABC123_response_template.rtf s3://m-sam-opportunity-responses/" -ForegroundColor Gray
Write-Host "2. Check CloudWatch logs:" -ForegroundColor White
Write-Host "   aws logs tail /aws/lambda/$BucketPrefix-sam-email-notification-$Environment --follow" -ForegroundColor Gray
Write-Host "3. Verify email delivery to subscribers" -ForegroundColor White

Write-Host "`nSetup completed! 🎉" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "- Edit the subscribers CSV with real email addresses" -ForegroundColor White
Write-Host "- Verify your sender email in SES if not already done" -ForegroundColor White
Write-Host "- Test the system with a sample RTF upload" -ForegroundColor White