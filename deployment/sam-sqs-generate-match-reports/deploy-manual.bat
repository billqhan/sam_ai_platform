@echo off
echo Creating Lambda deployment package...

REM Clean up existing package
if exist lambda-deployment-package.zip del lambda-deployment-package.zip

REM Create zip file using PowerShell
powershell -Command "Compress-Archive -Path 'lambda_function.py','requirements.txt','shared' -DestinationPath 'lambda-deployment-package.zip' -CompressionLevel Optimal"

echo.
echo Deployment package created: lambda-deployment-package.zip
echo.
echo To deploy, run:
echo aws lambda update-function-code --function-name ktest-sam-sqs-generate-match-reports-dev --zip-file fileb://lambda-deployment-package.zip --region us-east-1
echo.
echo Or upload lambda-deployment-package.zip through AWS Console
pause