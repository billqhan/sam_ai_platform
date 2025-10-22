param(
    [string]$Environment = "dev",
    [string]$BucketPrefix = "ktest"
)

$LambdaName = "$BucketPrefix-sam-email-notification-$Environment"
$Region = "us-east-1"

Write-Host "Creating Lambda function: $LambdaName" -ForegroundColor Green

# Create a minimal zip file for initial deployment
$TempDir = "temp-lambda"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
Copy-Item "lambda_function.py" "$TempDir/"
Copy-Item "requirements.txt" "$TempDir/"

# Create zip file
$ZipPath = "lambda-deployment.zip"
Compress-Archive -Path "$TempDir\*" -DestinationPath $ZipPath -Force
Remove-Item $TempDir -Recurse -Force

# Get or create IAM role
$RoleName = "$LambdaName-role"
$RoleArn = "arn:aws:iam::302585542747:role/$RoleName"

Write-Host "Creating IAM role: $RoleName" -ForegroundColor Cyan

# Trust policy for Lambda
$TrustPolicy = @'
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
'@

# Create role (ignore error if exists)
aws iam create-role --role-name $RoleName --assume-role-policy-document $TrustPolicy --region $Region 2>$null

# Attach basic Lambda execution policy
aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" --region $Region

# Attach S3 and SES policies
$PolicyDocument = @'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::m-sam-opportunity-responses/*",
                "arn:aws:s3:::ktest-sam-subscribers/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendRawEmail"
            ],
            "Resource": "*"
        }
    ]
}
'@

aws iam put-role-policy --role-name $RoleName --policy-name "EmailNotificationPolicy" --policy-document $PolicyDocument --region $Region

Write-Host "Creating Lambda function..." -ForegroundColor Cyan

# Wait a moment for role to propagate
Start-Sleep -Seconds 10

# Create Lambda function
aws lambda create-function `
    --function-name $LambdaName `
    --runtime python3.11 `
    --role $RoleArn `
    --handler lambda_function.lambda_handler `
    --zip-file "fileb://$ZipPath" `
    --timeout 60 `
    --memory-size 256 `
    --region $Region

# Clean up
Remove-Item $ZipPath -Force

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Lambda function created successfully!" -ForegroundColor Green
    Write-Host "Now you can run the deployment script to update the code and configuration."
} else {
    Write-Host "✗ Lambda function creation failed" -ForegroundColor Red
}