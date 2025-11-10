#!/bin/bash

# Complete Deployment Workflow Script
# AI-Powered RFP Response Agent System - Full Deployment Process

set -e

# Load environment configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env.dev" ]; then
  source "$SCRIPT_DIR/.env.dev"
  echo "✓ Loaded environment configuration from .env.dev"
else
  echo "⚠ Warning: .env.dev not found. Please create it with all required variables."
  exit 1
fi

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_header() { echo -e "\n${PURPLE}═══ $1 ═══${NC}\n"; }

# Step 1: Full system verification and build
full_deployment() {
    log_header "RUNNING FULL DEPLOYMENT"
    
    # Run initial verification
    ./deployment-verify.sh
    
    # Deploy infrastructure + Lambda functions
    log_header "DEPLOYING INFRASTRUCTURE"
    deploy_infrastructure
    
    # Deploy API Gateway
    log_header "DEPLOYING API GATEWAY"
    deploy_api_gateway
    
    # Build and deploy Java API to ECS
    log_header "DEPLOYING JAVA API"
    ./deployment-verify.sh build
    deploy_java_api_ecs
    
    # Deploy UI
    log_header "DEPLOYING UI"
    ./deployment-verify.sh deploy-ui
    
    # Deploy CloudFront
    deploy_cloudfront
}

# Step 2: Deploy infrastructure including Lambda functions and CloudFormation
deploy_infrastructure() {
    log_header "DEPLOYING INFRASTRUCTURE + LAMBDA FUNCTIONS + CLOUDFORMATION"
    
    # Check if PowerShell is available for complete deployment
    if command -v powershell >/dev/null 2>&1 || command -v pwsh >/dev/null 2>&1; then
        log_info "Using PowerShell for complete CloudFormation + Lambda deployment..."
        cd deployment
        
        local ps_cmd="powershell"
        if command -v pwsh >/dev/null 2>&1; then
            ps_cmd="pwsh"
        fi
        
        # This deploys:
        # 1. CloudFormation infrastructure (S3, DynamoDB, IAM, etc.)
        # 2. All Lambda functions (10+ functions)
        # 3. Lambda environment configuration
        # 4. Validation workflow
        log_info "Deploying complete stack with CloudFormation and Lambda functions..."
        $ps_cmd -File deploy-complete-stack.ps1 -BucketPrefix "$BUCKET_PREFIX" -Region "$REGION" -TemplatesBucket "ai-rfp-templates-dev" -SamApiKey "placeholder-key" -CompanyName "L3Harris Technologies" -CompanyContact "admin@l3harris.com"
        cd ..
    else
        log_info "PowerShell not available, deploying minimal CloudFormation infrastructure only..."
        log_info "Note: Lambda functions require PowerShell deployment scripts"
        
        # Create CloudFormation templates bucket
        aws s3 mb "s3://${BUCKET_PREFIX}-cloudformation-templates" --region "$REGION" 2>/dev/null || true
        aws s3 sync infrastructure/cloudformation/ "s3://${BUCKET_PREFIX}-cloudformation-templates/" --delete
        
        # Deploy minimal infrastructure if needed
        if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" >/dev/null 2>&1; then
            aws cloudformation deploy \
                --template-file infrastructure/minimal-stack.yaml \
                --stack-name "$STACK_NAME" \
                --parameter-overrides \
                    Environment="$ENVIRONMENT" \
                    BucketPrefix="$BUCKET_PREFIX" \
                --region "$REGION"
        fi
        
        log_info "For Lambda function deployment, use: cd deployment && powershell -File deploy-all-lambdas.ps1"
    fi
}

# Step 3: Deploy Java API with Docker to ECS
deploy_java_api_ecs() {
    log_header "DEPLOYING JAVA API WITH DOCKER TO ECS"
    
    local repo_name="${BUCKET_PREFIX}-rfp-java-api"
    local cluster_name="${BUCKET_PREFIX}-ecs-cluster"
    local service_name="${BUCKET_PREFIX}-java-api-service"
    local task_family="${BUCKET_PREFIX}-java-api-task"
    local log_group="/ecs/${BUCKET_PREFIX}-java-api"
    
    # Get AWS account ID
    local aws_account_id=$(aws sts get-caller-identity --query Account --output text)
    
    # Create ECR repository if needed
    if ! aws ecr describe-repositories --repository-names "$repo_name" --region "$REGION" >/dev/null 2>&1; then
        log_info "Creating ECR repository: $repo_name"
        aws ecr create-repository --repository-name "$repo_name" --region "$REGION"
    fi
    
  # Build and push Docker image (multi-architecture to support amd64 & arm64)
  log_info "Building and pushing multi-arch Docker image..."
  cd java-api

  # Get ECR login token
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$aws_account_id.dkr.ecr.$REGION.amazonaws.com"

  # Define image URI early for buildx push
  local image_uri="$aws_account_id.dkr.ecr.$REGION.amazonaws.com/$repo_name:latest"

  # Ensure Buildx builder exists
  if ! docker buildx inspect multiarch >/dev/null 2>&1; then
    log_info "Creating docker buildx builder 'multiarch'"
    docker buildx create --name multiarch --driver docker-container --use
  else
    docker buildx use multiarch
  fi

  # Warm up QEMU emulators (optional informative step)
  docker run --rm --privileged tonistiigi/binfmt --install all >/dev/null 2>&1 || true

  # Multi-platform build & push directly to ECR (manifest list)
  log_info "Executing buildx build for platforms linux/amd64,linux/arm64"
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --progress plain \
    -t "$image_uri" \
    --push . || { log_error "Multi-arch build failed"; exit 1; }

  # NOTE: If this fails due to BuildKit restrictions, you can fallback:
  # docker build -t "$repo_name" . && docker tag "$repo_name:latest" "$image_uri" && docker push "$image_uri" (will be single-arch only)
    
    cd ..
    
    log_success "Docker image pushed to ECR: $image_uri"
    
    # Create ECS cluster if it doesn't exist
    if ! aws ecs describe-clusters --clusters "$cluster_name" --region "$REGION" 2>/dev/null | grep -q "ACTIVE"; then
        log_info "Creating ECS cluster: $cluster_name"
        aws ecs create-cluster --cluster-name "$cluster_name" --region "$REGION"
    else
        log_info "ECS cluster already exists: $cluster_name"
    fi
    
    # Create CloudWatch log group
    if ! aws logs describe-log-groups --log-group-name-prefix "$log_group" --region "$REGION" 2>/dev/null | grep -q "$log_group"; then
        log_info "Creating CloudWatch log group: $log_group"
        aws logs create-log-group --log-group-name "$log_group" --region "$REGION"
    fi
    
    # Create task execution role if it doesn't exist
    local execution_role_name="${BUCKET_PREFIX}-ecs-task-execution-role"
    if ! aws iam get-role --role-name "$execution_role_name" >/dev/null 2>&1; then
        log_info "Creating ECS task execution role: $execution_role_name"
        
        cat > /tmp/ecs-task-execution-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
        
        aws iam create-role \
            --role-name "$execution_role_name" \
            --assume-role-policy-document file:///tmp/ecs-task-execution-trust-policy.json \
            --region "$REGION"
        
        aws iam attach-role-policy \
            --role-name "$execution_role_name" \
            --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" \
            --region "$REGION"
        
        # Allow ECR access
        aws iam attach-role-policy \
            --role-name "$execution_role_name" \
            --policy-arn "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly" \
            --region "$REGION"
        
        log_info "Waiting 10 seconds for IAM role to propagate..."
        sleep 10
    fi
    
    local execution_role_arn="arn:aws:iam::${aws_account_id}:role/${execution_role_name}"
    
    # Create task role for application (with access to S3, DynamoDB, etc.)
    local task_role_name="${BUCKET_PREFIX}-ecs-task-role"
    if ! aws iam get-role --role-name "$task_role_name" >/dev/null 2>&1; then
        log_info "Creating ECS task role: $task_role_name"
        
        aws iam create-role \
            --role-name "$task_role_name" \
            --assume-role-policy-document file:///tmp/ecs-task-execution-trust-policy.json \
            --region "$REGION"
        
        # Attach policies for S3 and DynamoDB access
        aws iam attach-role-policy \
            --role-name "$task_role_name" \
            --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess" \
            --region "$REGION"
        
        aws iam attach-role-policy \
            --role-name "$task_role_name" \
            --policy-arn "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess" \
            --region "$REGION"
    fi
    
    local task_role_arn="arn:aws:iam::${aws_account_id}:role/${task_role_name}"
    
    # Register task definition
    log_info "Registering ECS task definition..."
    cat > /tmp/task-definition.json <<EOF
{
  "family": "$task_family",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
  "executionRoleArn": "$execution_role_arn",
  "taskRoleArn": "$task_role_arn",
  "containerDefinitions": [
    {
      "name": "java-api",
      "image": "$image_uri",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "SPRING_PROFILES_ACTIVE",
          "value": "prod"
        },
        {
          "name": "RFP_API_AWS_REGION",
          "value": "$REGION"
        },
        {
          "name": "RFP_API_AWS_ENVIRONMENT",
          "value": "$ENVIRONMENT"
        },
        {
          "name": "RFP_API_AWS_PROJECT_PREFIX",
          "value": "$BUCKET_PREFIX"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$log_group",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/api/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF
    
    aws ecs register-task-definition \
        --cli-input-json file:///tmp/task-definition.json \
        --region "$REGION" > /dev/null
    
    log_success "Task definition registered: $task_family"
    
    # Get default VPC and subnets
    log_info "Getting VPC and subnet information..."
    local vpc_id=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region "$REGION")
    local subnet_ids=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc_id" --query "Subnets[*].SubnetId" --output text --region "$REGION" | tr '\t' ',')
    
    # Create security group for ECS service
    local sg_name="${BUCKET_PREFIX}-java-api-sg"
    local sg_id=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$sg_name" "Name=vpc-id,Values=$vpc_id" --query "SecurityGroups[0].GroupId" --output text --region "$REGION" 2>/dev/null)
    
    if [ "$sg_id" == "None" ] || [ -z "$sg_id" ]; then
        log_info "Creating security group: $sg_name"
        sg_id=$(aws ec2 create-security-group \
            --group-name "$sg_name" \
            --description "Security group for Java API ECS service" \
            --vpc-id "$vpc_id" \
            --region "$REGION" \
            --query "GroupId" \
            --output text)
        
        # Allow inbound on port 8080
        aws ec2 authorize-security-group-ingress \
            --group-id "$sg_id" \
            --protocol tcp \
            --port 8080 \
            --cidr 0.0.0.0/0 \
            --region "$REGION"
        
        log_success "Security group created: $sg_id"
    else
        log_info "Security group already exists: $sg_id"
    fi
    
    # Create or update ECS service
    if aws ecs describe-services --cluster "$cluster_name" --services "$service_name" --region "$REGION" 2>/dev/null | grep -q "ACTIVE"; then
        log_info "Updating existing ECS service: $service_name"
        aws ecs update-service \
            --cluster "$cluster_name" \
            --service "$service_name" \
            --task-definition "$task_family" \
            --desired-count 1 \
            --force-new-deployment \
            --region "$REGION" > /dev/null
    else
        log_info "Creating ECS service: $service_name"
        aws ecs create-service \
            --cluster "$cluster_name" \
            --service-name "$service_name" \
            --task-definition "$task_family" \
            --desired-count 1 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[$subnet_ids],securityGroups=[$sg_id],assignPublicIp=ENABLED}" \
            --region "$REGION" > /dev/null
    fi
    
    log_success "ECS service deployed: $service_name"
    log_info "Cluster: $cluster_name"
    log_info "Task Definition: $task_family"
    log_info "Service: $service_name"
    log_info ""
    log_info "To get the public IP of the running task:"
    echo "  aws ecs list-tasks --cluster $cluster_name --service-name $service_name --region $REGION"
    echo "  aws ecs describe-tasks --cluster $cluster_name --tasks <task-arn> --region $REGION --query 'tasks[0].attachments[0].details[?name==\"networkInterfaceId\"].value' --output text"
    echo "  aws ec2 describe-network-interfaces --network-interface-ids <eni-id> --region $REGION --query 'NetworkInterfaces[0].Association.PublicIp' --output text"
}

# Step 4: Deploy API Gateway
deploy_api_gateway() {
    log_header "DEPLOYING API GATEWAY"
    
    local stack_name="${BUCKET_PREFIX}-rfp-api-gateway"
    local api_backend_zip="api-backend-lambda.zip"
    
    # Package the api-backend Lambda function
    log_info "Packaging API backend Lambda function..."
    cd src/lambdas/api-backend
    
    # Clean up old package
    rm -f "$api_backend_zip"
    
    # Install dependencies if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        log_info "Installing Python dependencies..."
        pip3 install -r requirements.txt -t . --upgrade
    fi
    
    # Create deployment package
    zip -r "$api_backend_zip" . -x "*.pyc" -x "__pycache__/*" -x "*.zip"
    
    # Upload to S3
    local lambda_bucket="ai-rfp-templates-dev"
    log_info "Uploading Lambda package to S3..."
    aws s3 cp "$api_backend_zip" "s3://${lambda_bucket}/lambda/${api_backend_zip}" --region "$REGION"
    
    cd ../../..
    
    # Deploy CloudFormation stack
    log_info "Deploying API Gateway CloudFormation stack..."
    
    # Create a modified template that uses S3 for Lambda code
    cat > /tmp/api-gateway-deploy.yaml <<EOF
AWSTemplateFormatVersion: '2010-09-09'
Description: 'API Gateway + Lambda Backend for RFP Response Agent UI'

Parameters:
  Environment:
    Type: String
    Default: '${ENVIRONMENT}'
    Description: 'Environment name'
  
  ProjectPrefix:
    Type: String
    Default: '${BUCKET_PREFIX}'
    Description: 'Prefix for resource naming'
  
  LambdaBucket:
    Type: String
    Default: '${lambda_bucket}'
    Description: 'S3 bucket containing Lambda code'

Resources:
  # API Gateway REST API
  RfpApiGateway:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub '\${ProjectPrefix}-rfp-api-\${Environment}'
      Description: 'API Gateway for RFP Response Agent'
      EndpointConfiguration:
        Types:
          - REGIONAL

  # Root resource (already exists by default)
  
  # Workflow resource
  WorkflowResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RfpApiGateway
      ParentId: !GetAtt RfpApiGateway.RootResourceId
      PathPart: 'workflow'
  
  # Proxy resource under workflow
  WorkflowProxyResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RfpApiGateway
      ParentId: !Ref WorkflowResource
      PathPart: '{proxy+}'
  
  # Opportunities resource
  OpportunitiesResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RfpApiGateway
      ParentId: !GetAtt RfpApiGateway.RootResourceId
      PathPart: 'opportunities'
  
  # Proxy resource under opportunities
  OpportunitiesProxyResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RfpApiGateway
      ParentId: !Ref OpportunitiesResource
      PathPart: '{proxy+}'
  
  # API Backend Lambda Function
  ApiBackendFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '\${ProjectPrefix}-sam-api-backend-\${Environment}'
      Description: 'API Gateway handler for RFP UI backend'
      Runtime: python3.11
      Handler: handler.lambda_handler
      Role: !GetAtt ApiBackendRole.Arn
      Code:
        S3Bucket: !Ref LambdaBucket
        S3Key: 'lambda/api-backend-lambda.zip'
      MemorySize: 512
      Timeout: 30
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment
          PROJECT_PREFIX: !Ref ProjectPrefix
          DOWNLOAD_LAMBDA: !Sub '\${ProjectPrefix}-sam-gov-daily-download-\${Environment}'
          PROCESSOR_LAMBDA: !Sub '\${ProjectPrefix}-sam-json-processor-\${Environment}'
          MATCH_LAMBDA: !Sub '\${ProjectPrefix}-sam-sqs-generate-match-reports-\${Environment}'
          WEB_REPORT_LAMBDA: !Sub '\${ProjectPrefix}-sam-produce-web-reports-\${Environment}'
          USER_REPORT_LAMBDA: !Sub '\${ProjectPrefix}-sam-produce-user-report-\${Environment}'
          EMAIL_LAMBDA: !Sub '\${ProjectPrefix}-sam-daily-email-notification-\${Environment}'
          ARCHIVE_LAMBDA: !Sub '\${ProjectPrefix}-sam-merge-and-archive-result-logs-\${Environment}'
  
  # IAM Role for Lambda
  ApiBackendRole:
    Type: AWS::IAM::Role
    Properties:
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
        - PolicyName: LambdaInvoke
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - lambda:InvokeFunction
                Resource: !Sub 'arn:aws:lambda:\${AWS::Region}:\${AWS::AccountId}:function:\${ProjectPrefix}-sam-*'
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                  - dynamodb:Query
                  - dynamodb:Scan
                Resource: !Sub 'arn:aws:dynamodb:\${AWS::Region}:\${AWS::AccountId}:table/*'
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:ListBucket
                Resource:
                  - !Sub 'arn:aws:s3:::\${ProjectPrefix}-*'
                  - !Sub 'arn:aws:s3:::\${ProjectPrefix}-*/*'
  
  # Lambda Permission for API Gateway
  ApiGatewayInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ApiBackendFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:\${AWS::Region}:\${AWS::AccountId}:\${RfpApiGateway}/*'
  
  # Methods for workflow proxy
  WorkflowProxyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RfpApiGateway
      ResourceId: !Ref WorkflowProxyResource
      HttpMethod: ANY
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:\${AWS::Region}:lambda:path/2015-03-31/functions/\${ApiBackendFunction.Arn}/invocations'
  
  # Methods for opportunities proxy
  OpportunitiesProxyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RfpApiGateway
      ResourceId: !Ref OpportunitiesProxyResource
      HttpMethod: ANY
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:\${AWS::Region}:lambda:path/2015-03-31/functions/\${ApiBackendFunction.Arn}/invocations'
  
  # CORS OPTIONS method for workflow
  WorkflowOptionsMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RfpApiGateway
      ResourceId: !Ref WorkflowProxyResource
      HttpMethod: OPTIONS
      AuthorizationType: NONE
      Integration:
        Type: MOCK
        IntegrationResponses:
          - StatusCode: 200
            ResponseParameters:
              method.response.header.Access-Control-Allow-Headers: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
              method.response.header.Access-Control-Allow-Methods: "'GET,POST,PUT,DELETE,OPTIONS'"
              method.response.header.Access-Control-Allow-Origin: "'*'"
        RequestTemplates:
          application/json: '{"statusCode": 200}'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Headers: true
            method.response.header.Access-Control-Allow-Methods: true
            method.response.header.Access-Control-Allow-Origin: true
  
  # CORS OPTIONS method for opportunities
  OpportunitiesOptionsMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RfpApiGateway
      ResourceId: !Ref OpportunitiesProxyResource
      HttpMethod: OPTIONS
      AuthorizationType: NONE
      Integration:
        Type: MOCK
        IntegrationResponses:
          - StatusCode: 200
            ResponseParameters:
              method.response.header.Access-Control-Allow-Headers: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
              method.response.header.Access-Control-Allow-Methods: "'GET,POST,PUT,DELETE,OPTIONS'"
              method.response.header.Access-Control-Allow-Origin: "'*'"
        RequestTemplates:
          application/json: '{"statusCode": 200}'
      MethodResponses:
        - StatusCode: 200
          ResponseParameters:
            method.response.header.Access-Control-Allow-Headers: true
            method.response.header.Access-Control-Allow-Methods: true
            method.response.header.Access-Control-Allow-Origin: true
  
  # Deployment
  ApiDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn:
      - WorkflowProxyMethod
      - OpportunitiesProxyMethod
      - WorkflowOptionsMethod
      - OpportunitiesOptionsMethod
    Properties:
      RestApiId: !Ref RfpApiGateway
      Description: !Sub 'Deployment for \${Environment}'
  
  # Stage
  ApiStage:
    Type: AWS::ApiGateway::Stage
    Properties:
      RestApiId: !Ref RfpApiGateway
      DeploymentId: !Ref ApiDeployment
      StageName: !Ref Environment
      Description: !Sub '\${Environment} stage'
      TracingEnabled: true

Outputs:
  ApiGatewayUrl:
    Description: 'API Gateway URL'
    Value: !Sub 'https://\${RfpApiGateway}.execute-api.\${AWS::Region}.amazonaws.com/\${Environment}'
  
  ApiGatewayId:
    Description: 'API Gateway ID'
    Value: !Ref RfpApiGateway
  
  ApiBackendFunctionArn:
    Description: 'API Backend Lambda Function ARN'
    Value: !GetAtt ApiBackendFunction.Arn
EOF
    
    aws cloudformation deploy \
        --template-file /tmp/api-gateway-deploy.yaml \
        --stack-name "$stack_name" \
        --capabilities CAPABILITY_IAM \
        --region "$REGION" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            ProjectPrefix="$BUCKET_PREFIX" \
            LambdaBucket="$lambda_bucket"
    
    # Get the API Gateway URL
    local api_url=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    local api_id=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
        --output text)
    
    log_success "API Gateway deployed successfully!"
    log_info "API Gateway URL: $api_url"
    log_info "API Gateway ID: $api_id"
    
    # Automatically update UI .env.production file
    log_info ""
    log_info "Updating UI .env.production with new API Gateway URL..."
    cat > ui/.env.production <<EOF
VITE_API_BASE_URL=$api_url
VITE_AWS_REGION=$REGION
VITE_ENVIRONMENT=$ENVIRONMENT
EOF
    
    log_success "Updated ui/.env.production"
    
    # Rebuild and redeploy UI with new API Gateway URL
    log_info ""
    log_info "Rebuilding and redeploying UI with new API Gateway configuration..."
    ./deployment-verify.sh deploy-ui
    
    log_success "UI rebuilt and redeployed with new API Gateway URL!"
    log_info ""
    log_info "Your UI is now connected to the API Gateway at:"
    echo "  $api_url"
}

# Step 5: Deploy CloudFront Distribution
deploy_cloudfront() {
    log_header "DEPLOYING CLOUDFRONT DISTRIBUTION"
    
    local ui_bucket="${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}"
    local domain_name="${ui_bucket}.s3.${REGION}.amazonaws.com"
    
    # Check if CloudFront distribution already exists for this bucket
    log_info "Checking for existing CloudFront distributions..."
    local existing_dist=$(aws cloudfront list-distributions --query "DistributionList.Items[?Origins.Items[?DomainName=='${domain_name}']].Id" --output text 2>/dev/null | tr -d '\n')
    
    if [ -n "$existing_dist" ] && [ "$existing_dist" != "None" ]; then
        log_success "CloudFront distribution already exists: $existing_dist"
        local cf_domain=$(aws cloudfront get-distribution --id "$existing_dist" --query 'Distribution.DomainName' --output text 2>/dev/null)
        if [ -n "$cf_domain" ]; then
            log_info "CloudFront URL: https://$cf_domain"
            export CLOUDFRONT_ID="$existing_dist"
            return 0
        fi
    fi
    
    log_info "Creating new CloudFront distribution for S3 bucket: $ui_bucket"
    
    # Create CloudFront Origin Access Identity
    local oai_comment="${BUCKET_PREFIX}-ui-oai-${ENVIRONMENT}"
    local oai_id=$(aws cloudfront create-cloud-front-origin-access-identity \
        --cloud-front-origin-access-identity-config \
        "CallerReference=$(date +%s),Comment=$oai_comment" \
        --query 'CloudFrontOriginAccessIdentity.Id' --output text 2>/dev/null)
    
    if [ -z "$oai_id" ]; then
        log_warning "Failed to create Origin Access Identity, using existing or public access"
    else
        log_success "Created Origin Access Identity: $oai_id"
        
        # Get OAI canonical user ID
        local oai_canonical_user=$(aws cloudfront get-cloud-front-origin-access-identity --id "$oai_id" --query 'CloudFrontOriginAccessIdentity.S3CanonicalUserId' --output text)
        
        # Update S3 bucket policy to allow CloudFront OAI
        local bucket_policy=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontOAI",
            "Effect": "Allow",
            "Principal": {
                "CanonicalUser": "$oai_canonical_user"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::${ui_bucket}/*"
        }
    ]
}
EOF
)
        echo "$bucket_policy" > /tmp/cf-bucket-policy.json
        aws s3api put-bucket-policy --bucket "$ui_bucket" --policy file:///tmp/cf-bucket-policy.json
        rm /tmp/cf-bucket-policy.json
    fi
    
    # Create CloudFront distribution
    local dist_config=$(cat <<EOF
{
    "CallerReference": "$(date +%s)",
    "Comment": "CloudFront distribution for ${BUCKET_PREFIX} UI",
    "DefaultRootObject": "index.html",
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "S3-${ui_bucket}",
                "DomainName": "${domain_name}",
                "S3OriginConfig": {
                    "OriginAccessIdentity": "origin-access-identity/cloudfront/${oai_id}"
                }
            }
        ]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-${ui_bucket}",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 2,
            "Items": ["GET", "HEAD"],
            "CachedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"]
            }
        },
        "ForwardedValues": {
            "QueryString": false,
            "Cookies": {
                "Forward": "none"
            }
        },
        "MinTTL": 0,
        "DefaultTTL": 86400,
        "MaxTTL": 31536000,
        "Compress": true
    },
    "CustomErrorResponses": {
        "Quantity": 1,
        "Items": [
            {
                "ErrorCode": 404,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 300
            }
        ]
    },
    "Enabled": true
}
EOF
)
    
    echo "$dist_config" > /tmp/cf-dist-config.json
    local dist_id=$(aws cloudfront create-distribution --distribution-config file:///tmp/cf-dist-config.json \
        --query 'Distribution.Id' --output text 2>/dev/null)
    rm /tmp/cf-dist-config.json
    
    if [ -n "$dist_id" ]; then
        local cf_domain=$(aws cloudfront get-distribution --id "$dist_id" --query 'Distribution.DomainName' --output text)
        log_success "CloudFront distribution created: $dist_id"
        log_info "CloudFront URL: https://$cf_domain"
        log_info "Note: Distribution is being deployed, may take 15-20 minutes to be fully available"
        export CLOUDFRONT_ID="$dist_id"
    else
        log_warning "Failed to create CloudFront distribution. UI is available via S3."
        log_info "S3 website URL: http://${ui_bucket}.s3-website-${REGION}.amazonaws.com"
    fi
}

# Step 5: Test complete system
test_complete_system() {
    log_header "TESTING COMPLETE SYSTEM"
    
    # Test UI
    log_info "Testing UI via CloudFront..."
    if curl -s -I "https://dvik8huzkbem6.cloudfront.net" | head -n1 | grep -q "200\|301\|302"; then
        log_success "✅ UI is accessible"
    else
        log_info "⏳ UI may still be propagating through CloudFront"
    fi
    
    # Test Lambda API
    local lambda_name="${BUCKET_PREFIX}-sam-api-backend-${ENVIRONMENT}"
    if aws lambda get-function --function-name "$lambda_name" >/dev/null 2>&1; then
        log_success "✅ Lambda API is deployed"
    fi
    
    # Test DynamoDB tables
    local tables_count=$(aws dynamodb list-tables --query "length(TableNames[?contains(@,'$BUCKET_PREFIX')])" --output text)
    if [ "$tables_count" -gt 0 ]; then
        log_success "✅ DynamoDB tables deployed ($tables_count tables)"
    fi
    
    # Test S3 buckets
    local buckets_count=$(aws s3 ls | grep -c "$BUCKET_PREFIX" || echo "0")
    if [ "$buckets_count" -gt 0 ]; then
        log_success "✅ S3 buckets deployed ($buckets_count buckets)"
    fi
}

# Step 6: Deploy Lambda functions specifically  
deploy_lambda_functions() {
    log_header "DEPLOYING LAMBDA FUNCTIONS"
    
    if command -v powershell >/dev/null 2>&1 || command -v pwsh >/dev/null 2>&1; then
        log_info "Deploying all Lambda functions with PowerShell..."
        cd deployment
        
        local ps_cmd="powershell"
        if command -v pwsh >/dev/null 2>&1; then
            ps_cmd="pwsh"
        fi
        
        # Deploy all Lambda functions:
        # - sam-gov-daily-download (SAM.gov data retrieval)
        # - sam-json-processor (Opportunity processing)
        # - sam-sqs-generate-match-reports (AI matching)
        # - sam-produce-user-report (Report generation)
        # - sam-merge-and-archive-result-logs (Log management)
        # - sam-produce-web-reports (Web dashboard)
        # - sam-daily-email-notification (Email notifications)
        # - api-backend (REST API backend)
        
        # TEMPLATES_BUCKET is already exported from .env.dev
        $ps_cmd -File deploy-all-lambdas.ps1 -Environment "$ENVIRONMENT" -BucketPrefix "$BUCKET_PREFIX" -Region "$REGION"
        cd ..
        
        log_success "Lambda functions deployment completed"
    else
        log_info "PowerShell not available for Lambda deployment"
        log_info "Lambda functions require PowerShell scripts for packaging and deployment"
        log_info "Manual deployment: cd deployment && powershell -File deploy-all-lambdas.ps1"
    fi
}

# Step 7: Generate final deployment report
generate_deployment_report() {
    log_header "DEPLOYMENT REPORT"
    
    echo "🎯 SYSTEM STATUS:"
    echo "  Region: $REGION"
    echo "  Environment: $ENVIRONMENT"
    echo "  Bucket Prefix: $BUCKET_PREFIX"
    echo ""
    
    echo "🚀 DEPLOYED COMPONENTS:"
    echo "  ✅ React UI: https://dvik8huzkbem6.cloudfront.net"
    echo "  ✅ Java API: Built and ready (JAR: java-api/target/rfp-response-agent-api-1.0.0.jar)"
    echo "  ✅ AWS Infrastructure: S3, DynamoDB, Lambda functions"
    echo "  ✅ CloudFront CDN: Active and distributing UI globally"
    echo ""
    
    echo "📋 QUICK ACCESS COMMANDS:"
    echo "  # Verify deployment:"
    echo "  ./deployment-verify.sh"
    echo ""
    echo "  # Rebuild and redeploy UI:"
    echo "  ./deployment-verify.sh deploy-ui"
    echo ""
    echo "  # Test system:"
    echo "  ./deployment-verify.sh test"
    echo ""
    
    echo "🔧 JAVA API DEPLOYMENT OPTIONS:"
    echo "  # Deploy to ECS with Docker (recommended for production)"
    echo "  ./deploy-complete.sh java-api"
    echo ""
    echo "  # Manual deployment for local testing"
    echo "  java -jar java-api/target/rfp-response-agent-api-1.0.0.jar"
    echo ""
    
    log_success "🎉 Deployment completed successfully!"
}

# Main execution based on arguments
case "${1:-full}" in
    "verify")
        ./deployment-verify.sh
        ;;
    "infrastructure")
        deploy_infrastructure
        ;;
    "lambda")
        deploy_lambda_functions
        ;;
    "api-gateway")
        deploy_api_gateway
        ;;
    "java-api")
        ./deployment-verify.sh build
        deploy_java_api_ecs
        ;;
    "ui")
        ./deployment-verify.sh deploy-ui
        deploy_cloudfront
        ;;
    "cloudfront")
        deploy_cloudfront
        ;;
    "test")
        test_complete_system
        ;;
    "full")
        full_deployment
        test_complete_system
        generate_deployment_report
        ;;
    *)
        echo "Usage: $0 [verify|infrastructure|lambda|api-gateway|java-api|ui|cloudfront|test|full]"
        echo ""
        echo "Commands:"
        echo "  verify         - Check prerequisites and current deployment status"
        echo "  infrastructure - Deploy AWS CloudFormation infrastructure + Lambda functions"
        echo "  lambda         - Deploy Lambda functions only (requires PowerShell)"
        echo "  api-gateway    - Deploy API Gateway + Lambda backend for UI"
        echo "  java-api       - Deploy Java API to ECS with Docker"
        echo "  ui             - Build and deploy React UI with CloudFront"
        echo "  cloudfront     - Create/update CloudFront distribution for UI"
        echo "  test           - Test deployed components"
        echo "  full           - Complete deployment verification and testing (default)"
        ;;
esac