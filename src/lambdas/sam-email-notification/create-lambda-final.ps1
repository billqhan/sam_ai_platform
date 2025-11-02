$LambdaName = "ktest-sam-email-notification-dev"
$Region = "us-east-1"
$RoleName = "$LambdaName-role"

Write-Host "Creating Lambda function: $LambdaName"

# Create zip file
Compress-Archive -Path "lambda_function.py" -DestinationPath "lambda.zip" -Force

# Create role
Write-Host "Creating IAM role..."
aws iam create-role --role-name $RoleName --assume-role-policy-document file://trust-policy.json --region $Region

# Attach basic execution policy
Write-Host "Attaching policies..."
aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

# Attach custom policy
aws iam put-role-policy --role-name $RoleName --policy-name "EmailPolicy" --policy-document file://lambda-policy.json

# Wait for role propagation
Write-Host "Waiting for role propagation..."
Start-Sleep -Seconds 15

# Create function
Write-Host "Creating Lambda function..."
$RoleArn = "arn:aws:iam::302585542747:role/$RoleName"
aws lambda create-function --function-name $LambdaName --runtime python3.11 --role $RoleArn --handler lambda_function.lambda_handler --zip-file "fileb://lambda.zip" --timeout 60 --memory-size 256 --region $Region

# Clean up
Remove-Item "lambda.zip" -Force

Write-Host "Done!"