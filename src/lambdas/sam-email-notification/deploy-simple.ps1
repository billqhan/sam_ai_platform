param(
    [string]$Environment = "dev",
    [string]$BucketPrefix = "ktest", 
    [string]$FromEmail = "mga.aws2024@gmail.com",
    [string]$SubscribersBucket = "ktest-sam-subscribers"
)

$LambdaName = "$BucketPrefix-sam-email-notification-$Environment"
$Region = "us-east-1"
$TemplatesBucket = "m2-sam-templates-bucket"

Write-Host "=== SAM Email Notification Deployment ===" -ForegroundColor Green
Write-Host "Lambda Name: $LambdaName"
Write-Host "From Email: $FromEmail"
Write-Host "Subscribers Bucket: $SubscribersBucket"

Write-Host "`n1. Deploying Lambda Function..." -ForegroundColor Cyan
$DeployScript = "..\..\infrastructure\scripts\update-lambda-code.ps1"
& $DeployScript -Environment $Environment -TemplatesBucket $TemplatesBucket -BucketPrefix $BucketPrefix -LambdaName "sam-email-notification"

Write-Host "`n2. Configuring Environment Variables..." -ForegroundColor Cyan
$EnvJson = '{"FROM_EMAIL":"' + $FromEmail + '","SUBSCRIBERS_BUCKET":"' + $SubscribersBucket + '","SUBSCRIBERS_FILE":"subscribers.csv","SES_REGION":"us-east-1","EMAIL_SUBJECT_TEMPLATE":"AWS AI-Powered RFI/RFP Response for {solicitation_number}","EMAIL_BODY":"Dear Team, here is the latest match for your review."}'

aws lambda update-function-configuration --function-name $LambdaName --environment "Variables=$EnvJson" --region $Region

Write-Host "`n3. Adding S3 Permission..." -ForegroundColor Cyan
aws lambda add-permission --function-name $LambdaName --principal s3.amazonaws.com --action lambda:InvokeFunction --source-arn "arn:aws:s3:::m-sam-opportunity-responses" --statement-id s3-email-trigger-permission --region $Region

Write-Host "`n4. Checking SES Email..." -ForegroundColor Cyan
aws ses verify-email-identity --email-address $FromEmail --region $Region

Write-Host "`nDeployment completed!" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. Create subscribers CSV: python create-sample-subscribers.py --bucket $SubscribersBucket"
Write-Host "2. Configure S3 event notifications manually in AWS Console"
Write-Host "3. Test by uploading an RTF file"