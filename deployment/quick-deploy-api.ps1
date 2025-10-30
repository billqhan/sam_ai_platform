# Quick Deploy API Gateway using AWS CLI (No SAM required)
# This script uses plain CloudFormation to deploy the API Gateway

param(
    [string]$Environment = "dev",
    [string]$Region = "us-east-1",
    [string]$ProjectPrefix = "l3harris-qhan"
)

$ErrorActionPreference = "Continue"  # Allow continuing on errors

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RFP Response Agent - Quick API Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$StackName = "$ProjectPrefix-api-gateway-$Environment"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Stack Name: $StackName" -ForegroundColor White
Write-Host "  Environment: $Environment" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White
Write-Host ""

# Check AWS credentials
Write-Host "Checking AWS credentials..." -ForegroundColor Cyan
$AccountId = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] AWS credentials not configured" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] AWS Account: $AccountId" -ForegroundColor Green
Write-Host ""

# Since SAM is not installed, let's create the Lambda function directly
Write-Host "Creating Lambda function package..." -ForegroundColor Cyan
$LambdaDir = "C:\Users\qhan\rfi_response_kiro\src\lambdas\api-backend"
$ZipFile = "C:\Users\qhan\rfi_response_kiro\deployment\api-backend.zip"

# Remove old zip if exists
if (Test-Path $ZipFile) {
    Remove-Item $ZipFile -Force
}

# Create zip file
Write-Host "  Packaging $LambdaDir..." -ForegroundColor Yellow
Compress-Archive -Path "$LambdaDir\*" -DestinationPath $ZipFile -Force
Write-Host "[OK] Created $ZipFile" -ForegroundColor Green
Write-Host ""

# Upload to S3
$S3Bucket = "$ProjectPrefix-sam-deployments-$Environment"
$S3Key = "api-backend/$(Get-Date -Format 'yyyyMMdd-HHmmss')/function.zip"

Write-Host "Uploading Lambda package to S3..." -ForegroundColor Cyan
Write-Host "  Bucket: $S3Bucket" -ForegroundColor Gray
Write-Host "  Key: $S3Key" -ForegroundColor Gray

# Create bucket if needed
aws s3 mb "s3://$S3Bucket" --region $Region 2>&1 | Out-Null

# Upload
aws s3 cp $ZipFile "s3://$S3Bucket/$S3Key" --region $Region
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to upload to S3" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Uploaded successfully" -ForegroundColor Green
Write-Host ""

# Create CloudFormation template with inline code reference
Write-Host "Creating CloudFormation template..." -ForegroundColor Cyan
$TemplateContent = @"
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Simple API Gateway + Lambda for RFP UI'

Parameters:
  Environment:
    Type: String
    Default: '$Environment'
  ProjectPrefix:
    Type: String
    Default: '$ProjectPrefix'
  S3Bucket:
    Type: String
    Default: '$S3Bucket'
  S3Key:
    Type: String
    Default: '$S3Key'

Resources:
  ApiGatewayRestApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub '\${ProjectPrefix}-rfp-api-\${Environment}'
      Description: 'RFP Response Agent API'
      EndpointConfiguration:
        Types:
          - REGIONAL

  ApiGatewayDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn:
      - ApiGatewayMethodHealth
      - ApiGatewayMethodDashboard
      - ApiGatewayMethodWorkflow
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      StageName: !Ref Environment

  # Lambda Execution Role
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '\${ProjectPrefix}-api-backend-role-\${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: LambdaInvokePolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - lambda:InvokeFunction
                Resource: !Sub 'arn:aws:lambda:\${AWS::Region}:\${AWS::AccountId}:function:\${ProjectPrefix}-sam-*'
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:ListBucket
                Resource:
                  - !Sub 'arn:aws:s3:::\${ProjectPrefix}-*'
                  - !Sub 'arn:aws:s3:::\${ProjectPrefix}-*/*'

  # Lambda Function
  ApiBackendFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '\${ProjectPrefix}-sam-api-backend-\${Environment}'
      Runtime: python3.11
      Handler: handler.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        S3Bucket: !Ref S3Bucket
        S3Key: !Ref S3Key
      MemorySize: 512
      Timeout: 30
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment
          PROJECT_PREFIX: !Ref ProjectPrefix

  # Lambda Permission for API Gateway
  LambdaApiPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ApiBackendFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:\${AWS::Region}:\${AWS::AccountId}:\${ApiGatewayRestApi}/*'

  # Health endpoint
  ApiGatewayResourceHealth:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ParentId: !GetAtt ApiGatewayRestApi.RootResourceId
      PathPart: health

  ApiGatewayMethodHealth:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ResourceId: !Ref ApiGatewayResourceHealth
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:\${AWS::Region}:lambda:path/2015-03-31/functions/\${ApiBackendFunction.Arn}/invocations'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Origin: true

  # Dashboard endpoint
  ApiGatewayResourceDashboard:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ParentId: !GetAtt ApiGatewayRestApi.RootResourceId
      PathPart: dashboard

  ApiGatewayResourceDashboardMetrics:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ParentId: !Ref ApiGatewayResourceDashboard
      PathPart: metrics

  ApiGatewayMethodDashboard:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ResourceId: !Ref ApiGatewayResourceDashboardMetrics
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:\${AWS::Region}:lambda:path/2015-03-31/functions/\${ApiBackendFunction.Arn}/invocations'

  # Workflow endpoint
  ApiGatewayResourceWorkflow:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ParentId: !GetAtt ApiGatewayRestApi.RootResourceId
      PathPart: workflow

  ApiGatewayResourceWorkflowTrigger:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ParentId: !Ref ApiGatewayResourceWorkflow
      PathPart: trigger

  ApiGatewayMethodWorkflow:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ResourceId: !Ref ApiGatewayResourceWorkflowTrigger
      HttpMethod: POST
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:\${AWS::Region}:lambda:path/2015-03-31/functions/\${ApiBackendFunction.Arn}/invocations'

  # Enable CORS
  ApiGatewayOptionsHealth:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref ApiGatewayRestApi
      ResourceId: !Ref ApiGatewayResourceHealth
      HttpMethod: OPTIONS
      AuthorizationType: NONE
      Integration:
        Type: MOCK
        IntegrationResponses:
          - StatusCode: 200
            ResponseParameters:
              method.response.header.Access-Control-Allow-Headers: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'"
              method.response.header.Access-Control-Allow-Methods: "'GET,POST,OPTIONS'"
              method.response.header.Access-Control-Allow-Origin: "'*'"
            ResponseTemplates:
              application/json: ''
        RequestTemplates:
          application/json: '{"statusCode": 200}'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Headers: true
            method.response.header.Access-Control-Allow-Methods: true
            method.response.header.Access-Control-Allow-Origin: true

Outputs:
  ApiEndpoint:
    Description: 'API Gateway endpoint URL'
    Value: !Sub 'https://\${ApiGatewayRestApi}.execute-api.\${AWS::Region}.amazonaws.com/\${Environment}'
    Export:
      Name: !Sub '\${ProjectPrefix}-api-endpoint-\${Environment}'
  
  ApiFunctionArn:
    Description: 'API Backend Lambda Function ARN'
    Value: !GetAtt ApiBackendFunction.Arn
"@

$TemplateFile = "C:\Users\qhan\rfi_response_kiro\infrastructure\api-gateway-simple.yaml"
$TemplateContent | Out-File -FilePath $TemplateFile -Encoding UTF8 -Force
Write-Host "[OK] Template created" -ForegroundColor Green
Write-Host ""

# Deploy CloudFormation stack
Write-Host "Deploying CloudFormation stack..." -ForegroundColor Cyan
Write-Host "  This may take 2-3 minutes..." -ForegroundColor Yellow

aws cloudformation deploy `
    --template-file $TemplateFile `
    --stack-name $StackName `
    --capabilities CAPABILITY_NAMED_IAM `
    --parameter-overrides `
        Environment=$Environment `
        ProjectPrefix=$ProjectPrefix `
        S3Bucket=$S3Bucket `
        S3Key=$S3Key `
    --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Deployment complete" -ForegroundColor Green
Write-Host ""

# Get API endpoint
Write-Host "Retrieving API endpoint..." -ForegroundColor Cyan
$ApiEndpoint = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" `
    --output text `
    --region $Region

Write-Host "[OK] API Endpoint: $ApiEndpoint" -ForegroundColor Green
Write-Host ""

# Update UI .env file
Write-Host "Updating UI environment file..." -ForegroundColor Cyan
$EnvFile = "C:\Users\qhan\rfi_response_kiro\ui\.env"
$EnvContent = @"
# API Gateway Endpoint
VITE_API_BASE_URL=$ApiEndpoint

# AWS Region
VITE_AWS_REGION=$Region

# Environment
VITE_ENVIRONMENT=$Environment

# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@

$EnvContent | Out-File -FilePath $EnvFile -Encoding UTF8 -Force
Write-Host "[OK] Created $EnvFile" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "API Endpoint: $ApiEndpoint" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Restart UI dev server: cd ui && npm run dev" -ForegroundColor White
Write-Host "  2. Open http://localhost:3001" -ForegroundColor White
Write-Host "  3. Try the workflow!" -ForegroundColor White
Write-Host ""
Write-Host "Test API:" -ForegroundColor Yellow
Write-Host "  curl $ApiEndpoint/health" -ForegroundColor Gray
Write-Host ""
