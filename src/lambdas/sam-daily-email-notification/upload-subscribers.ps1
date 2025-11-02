# Upload Daily Subscribers CSV to S3
# This script uploads the subscribers_daily.csv file to the S3 bucket

param(
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "ktest",
    
    [Parameter(Mandatory=$false)]
    [string]$SubscribersFile = "subscribers_daily.csv"
)

$ErrorActionPreference = "Stop"

$BucketName = "$BucketPrefix-sam-subscribers"

Write-Host "=== Uploading Daily Subscribers CSV ===" -ForegroundColor Cyan
Write-Host "Bucket: $BucketName" -ForegroundColor White
Write-Host "File: $SubscribersFile" -ForegroundColor White
Write-Host ""

# Check if file exists
if (-not (Test-Path $SubscribersFile)) {
    Write-Host "[ERROR] File not found: $SubscribersFile" -ForegroundColor Red
    exit 1
}

# Check if bucket exists
Write-Host "[INFO] Checking if bucket exists: $BucketName" -ForegroundColor Blue
aws s3 ls s3://$BucketName --region us-east-1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Bucket does not exist, creating: $BucketName" -ForegroundColor Blue
    aws s3 mb s3://$BucketName --region us-east-1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create bucket" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[SUCCESS] Bucket created successfully!" -ForegroundColor Green
}

# Upload file
Write-Host "[INFO] Uploading $SubscribersFile to s3://$BucketName/" -ForegroundColor Blue
aws s3 cp $SubscribersFile s3://$BucketName/ --region us-east-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] File uploaded successfully!" -ForegroundColor Green
    
    # Verify upload
    Write-Host "[INFO] Verifying upload..." -ForegroundColor Blue
    aws s3 ls s3://$BucketName/$SubscribersFile --region us-east-1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] File verified in S3!" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Could not verify file in S3" -ForegroundColor Yellow
    }
} else {
    Write-Host "[ERROR] Failed to upload file" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[SUCCESS] Daily subscribers CSV upload completed!" -ForegroundColor Green
Write-Host "S3 Location: s3://$BucketName/$SubscribersFile" -ForegroundColor White