# Create Daily Email Notification Lambda Function
# This script creates the Lambda function and IAM role for daily email notifications

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "ktest"
)

$ErrorActionPreference = "Stop"

# Function names
$FunctionName = if ($BucketPrefix) { "$BucketPrefix-sam-daily-email-notification-$Environment" } else { "sam-daily-email-notification-$Environment" }
$RoleName = "$FunctionName-role"

Write-Host "=== Creating Daily Email Notification Lambda Function ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor White
Write-Host "Function Name: $FunctionName" -ForegroundColor White
Write-Host "Role Name: $RoleName" -ForegroundColor White
Write-Host ""

# Check if function already exists
try {
    aws lambda get-function --function-name $FunctionName --region us-east-1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[INFO] Lambda function $FunctionName already exists" -ForegroundColor Yellow
        exit 0
    }
} catch {
    Write-Host "[INFO] Lambda function $FunctionName does not exist, creating..." -ForegroundColor Blue
}

# Create IAM trust policy
$TrustPolicyJson = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
"@

# Create IAM role
Write-Host "[INFO] Creating IAM role: $RoleName" -ForegroundColor Blue
$TrustPolicyJson | Out-File -FilePath "trust-policy-temp.json" -Encoding UTF8

aws iam create-role `
    --role-name $RoleName `
    --assume-role-policy-document file://trust-policy-temp.json `
    --region us-east-1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create IAM role" -ForegroundColor Red
    Remove-Item "trust-policy-temp.json" -ErrorAction SilentlyContinue
    exit 1
}

# Clean up temp file
Remove-Item "trust-policy-temp.json" -ErrorAction SilentlyContinue

# Attach basic execution policy
Write-Host "[INFO] Attaching basic execution policy" -ForegroundColor Blue
aws iam attach-role-policy `
    --role-name $RoleName `
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" `
    --region us-east-1

# Create custom policy for S3 and SES access
$CustomPolicyJson = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::$BucketPrefix-sam-opportunity-responses-$Environment",
                "arn:aws:s3:::$BucketPrefix-sam-opportunity-responses-$Environment/*",
                "arn:aws:s3:::$BucketPrefix-sam-subscribers",
                "arn:aws:s3:::$BucketPrefix-sam-subscribers/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendRawEmail",
                "ses:GetIdentityVerificationAttributes"
            ],
            "Resource": "*"
        }
    ]
}
"@

# Create and attach custom policy
Write-Host "[INFO] Creating custom policy for S3 and SES access" -ForegroundColor Blue
$CustomPolicyJson | Out-File -FilePath "custom-policy-temp.json" -Encoding UTF8

aws iam put-role-policy `
    --role-name $RoleName `
    --policy-name "DailyEmailNotificationPolicy" `
    --policy-document file://custom-policy-temp.json `
    --region us-east-1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create custom policy" -ForegroundColor Red
    Remove-Item "custom-policy-temp.json" -ErrorAction SilentlyContinue
    exit 1
}

# Clean up temp file
Remove-Item "custom-policy-temp.json" -ErrorAction SilentlyContinue

# Wait for role to be available
Write-Host "[INFO] Waiting for IAM role to be available..." -ForegroundColor Blue
Start-Sleep -Seconds 10

# Get role ARN
$RoleArn = aws iam get-role --role-name $RoleName --query 'Role.Arn' --output text --region us-east-1

# Create placeholder zip file
Write-Host "[INFO] Creating placeholder Lambda function" -ForegroundColor Blue
$PlaceholderCode = @"
def lambda_handler(event, context):
    return {'statusCode': 200, 'body': 'Placeholder function - deploy actual code'}
"@

$PlaceholderCode | Out-File -FilePath "lambda_function.py" -Encoding UTF8
Compress-Archive -Path "lambda_function.py" -DestinationPath "function.zip" -Force
Remove-Item "lambda_function.py"

# Create Lambda function
Write-Host "[INFO] Creating Lambda function: $FunctionName" -ForegroundColor Blue
aws lambda create-function `
    --function-name $FunctionName `
    --runtime python3.11 `
    --role $RoleArn `
    --handler lambda_function.lambda_handler `
    --zip-file fileb://function.zip `
    --memory-size 512 `
    --timeout 300 `
    --region us-east-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Lambda function created successfully!" -ForegroundColor Green
    
    # Set environment variables
    Write-Host "[INFO] Setting environment variables" -ForegroundColor Blue
    
    $EnvVarsJson = @"
{
    "Variables": {
        "EMAIL_ENABLED": "true",
        "SES_REGION": "us-east-1",
        "FROM_EMAIL": "mga.aws2024@gmail.com",
        "EMAIL_SUBJECT_TEMPLATE": "Daily AWS AI-Powered RFI/RFP Response for {date}",
        "EMAIL_BODY_TEMPLATE": "Dear {name}, here is the Daily Website for your review.\\n\\nI have attached a zip file containing only the high scoring opportunity matches for {date}.\\n\\nPlease review the Daily Opportunities Website at the URL below for a summary of all data that was processed.",
        "OPPORTUNITY_RESPONSES_BUCKET": "$BucketPrefix-sam-opportunity-responses-$Environment",
        "WEBSITE_BUCKET": "$BucketPrefix-sam-website-$Environment",
        "WEBSITE_BASE_URL": "http://$BucketPrefix-sam-website-$Environment.s3-website-us-east-1.amazonaws.com",
        "SUBSCRIBERS_BUCKET": "$BucketPrefix-sam-subscribers",
        "SUBSCRIBERS_FILE": "subscribers_daily.csv",
        "ATTACHMENT_TYPE": "txt"
    }
}
"@
    
    $EnvVarsJson | Out-File -FilePath "env-vars-temp.json" -Encoding UTF8
    
    aws lambda update-function-configuration `
        --function-name $FunctionName `
        --environment file://env-vars-temp.json `
        --region us-east-1
    
    Remove-Item "env-vars-temp.json" -ErrorAction SilentlyContinue
    
    Write-Host "[SUCCESS] Environment variables set successfully!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create Lambda function" -ForegroundColor Red
    exit 1
}

# Clean up
Remove-Item "function.zip" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[SUCCESS] Daily Email Notification Lambda function setup completed!" -ForegroundColor Green
Write-Host "Function Name: $FunctionName" -ForegroundColor White
Write-Host "Role Name: $RoleName" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Deploy actual code using the deployment scripts" -ForegroundColor White
Write-Host "2. Create subscribers_daily.csv file in S3" -ForegroundColor White
Write-Host "3. Verify SES email address" -ForegroundColor White
Write-Host "4. Test the function" -ForegroundColor White