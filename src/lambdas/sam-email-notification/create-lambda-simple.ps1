$LambdaName = "ktest-sam-email-notification-dev"
$Region = "us-east-1"
$RoleName = "$LambdaName-role"

Write-Host "Creating Lambda function: $LambdaName"

# Create zip file
Compress-Archive -Path "lambda_function.py" -DestinationPath "lambda.zip" -Force

# Trust policy
$TrustPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

# Create role
aws iam create-role --role-name $RoleName --assume-role-policy-document $TrustPolicy --region $Region

# Attach policies
aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

# Custom policy
$Policy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::m-sam-opportunity-responses/*","arn:aws:s3:::ktest-sam-subscribers/*"]},{"Effect":"Allow","Action":["ses:SendRawEmail"],"Resource":"*"}]}'

aws iam put-role-policy --role-name $RoleName --policy-name "EmailPolicy" --policy-document $Policy

# Wait for role
Start-Sleep -Seconds 15

# Create function
$RoleArn = "arn:aws:iam::302585542747:role/$RoleName"
aws lambda create-function --function-name $LambdaName --runtime python3.11 --role $RoleArn --handler lambda_function.lambda_handler --zip-file "fileb://lambda.zip" --timeout 60 --memory-size 256 --region $Region

Remove-Item "lambda.zip" -Force

Write-Host "Lambda function creation completed"