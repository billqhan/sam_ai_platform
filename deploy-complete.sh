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
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Verification & Build Helpers (migrated from deployment-verify.sh)
command_exists() { command -v "$1" >/dev/null 2>&1; }

verify_prerequisites() {
  log_header "VERIFYING PREREQUISITES"
  local all_good=true

  if command_exists aws; then
    local aws_version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
    log_success "AWS CLI v$aws_version installed"
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
      log_warning "AWS credentials not configured (sts get-caller-identity failed)"
      all_good=false
    fi
  else
    log_warning "AWS CLI not installed"
    all_good=false
  fi

  if command_exists docker; then
    log_success "Docker available"
  else
    log_warning "Docker not installed (required for ECS builds)"
    all_good=false
  fi

  if command_exists mvn; then
    log_success "Maven installed"
  else
    log_warning "Maven not installed"
    all_good=false
  fi

  if command_exists node; then
    log_success "Node.js $(node --version) installed"
  else
    log_warning "Node.js not installed"
    all_good=false
  fi
  if command_exists npm; then
    log_success "npm $(npm --version) installed"
  else
    log_warning "npm not installed"
    all_good=false
  fi

  # Environment variables
  for v in BUCKET_PREFIX ENVIRONMENT REGION; do
    if [ -z "${!v}" ]; then
      log_warning "Missing required env var: $v"
      all_good=false
    fi
  done

  [ "$all_good" = true ] || { log_warning "Prerequisite verification failed"; }
  return $([ "$all_good" = true ] && echo 0 || echo 1)
}

build_java_api() {
  log_header "BUILDING JAVA API"
  if [ -d "java-api" ]; then
    (cd java-api && mvn clean package -DskipTests)
    if [ -f "java-api/target/rfp-response-agent-api-1.0.0.jar" ]; then
      log_success "Java API built (JAR present)"
    else
      log_warning "Java API build finished but JAR missing"
    fi
  else
    log_warning "Directory 'java-api' not found"
  fi
}

build_react_ui() {
  log_header "BUILDING REACT UI"
  if [ -d "ui" ]; then
    (cd ui && npm install && npm run build)
    if [ -f "ui/dist/index.html" ]; then
      log_success "React UI build complete"
    else
      log_warning "UI build completed but dist/index.html missing"
    fi
  else
    log_warning "Directory 'ui' not found"
  fi
}

deploy_ui_assets() {
  log_header "DEPLOYING UI ASSETS TO S3"
  local ui_bucket="${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}"
  if [ -d "ui/dist" ]; then
    aws s3 sync ui/dist/ "s3://$ui_bucket/" --delete
    log_success "UI assets synced to S3 bucket: $ui_bucket"
  else
    log_warning "UI dist folder not found; build may have failed"
  fi
}

verify_cloudfront() {
  log_header "VERIFYING CLOUDFRONT DISTRIBUTION"
  local ui_bucket="${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}"
  local domain_name="${ui_bucket}.s3.${REGION}.amazonaws.com"
  local existing_dist=$(aws cloudfront list-distributions --query "DistributionList.Items[?Origins.Items[?DomainName=='${domain_name}']].Id" --output text 2>/dev/null | tr -d '\n')
  if [ -n "$existing_dist" ] && [ "$existing_dist" != "None" ]; then
    local cf_domain=$(aws cloudfront get-distribution --id "$existing_dist" --query 'Distribution.DomainName' --output text 2>/dev/null)
    log_success "CloudFront distribution active: $existing_dist (https://$cf_domain)"
  else
    log_warning "No CloudFront distribution detected for origin: $domain_name"
  fi
}

# Step 1: Full deployment - Java API and UI only
full_deployment() {
    log_header "RUNNING FULL DEPLOYMENT - JAVA API & UI"
  verify_prerequisites || log_warning "Continuing despite prerequisite warnings"
  build_java_api
  log_header "DEPLOYING JAVA API TO ECS"
    deploy_java_api_ecs
  build_react_ui
  deploy_ui_assets
  log_header "DEPLOYING CLOUDFRONT"
    deploy_cloudfront
    
    log_success "\n✅ Full deployment complete!"
    generate_deployment_report
}

# Step 2: Deploy Java API with Docker to ECS
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

# Step 3: Deploy CloudFront Distribution
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

# Step 3: Test complete system
test_complete_system() {
    log_header "TESTING JAVA API & UI"
    
    # Test UI in S3
    log_info "Testing UI deployment..."
    local ui_bucket="${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}"
    if aws s3 ls "s3://$ui_bucket/index.html" >/dev/null 2>&1; then
        log_success "✅ UI deployed to S3: $ui_bucket"
    else
        log_warning "⚠️  UI not found in S3"
    fi
    
    # Test Java API on ECS
    log_info "Testing Java API deployment..."
    local cluster_name="${BUCKET_PREFIX}-ecs-cluster"
    local service_name="${BUCKET_PREFIX}-java-api-service"
    if aws ecs describe-services --cluster "$cluster_name" --services "$service_name" --region "$REGION" 2>/dev/null | grep -q "ACTIVE"; then
        log_success "✅ Java API service running: $service_name"
    else
        log_warning "⚠️  Java API service not found or not active"
    fi
    echo ""
    verify_cloudfront || true
}

# Step 4: Generate final deployment report
generate_deployment_report() {
    log_header "DEPLOYMENT REPORT"
    
    echo "🎯 SYSTEM STATUS:"
    echo "  Region: $REGION"
    echo "  Environment: $ENVIRONMENT"
    echo "  Bucket Prefix: $BUCKET_PREFIX"
    echo ""
    
    echo "🚀 DEPLOYED COMPONENTS:"
    echo "  ✅ Java API: ECS Cluster (${BUCKET_PREFIX}-ecs-cluster)"
    echo "  ✅ React UI: S3 + CloudFront"
    echo ""
    echo ""
    
    echo "📋 QUICK ACCESS COMMANDS:"
    echo "  # Verify prerequisites only:" 
    echo "  ./deploy-complete.sh verify"
    echo ""
    echo "  # Build & deploy Java API only:" 
    echo "  ./deploy-complete.sh java-api"
    echo ""
    echo "  # Build & deploy UI only:" 
    echo "  ./deploy-complete.sh ui"
    echo ""
    echo "  # Test deployed components:" 
    echo "  ./deploy-complete.sh test"
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
deploy_eks_cluster() {
  log_header "DEPLOYING EKS CLUSTER (OPTIONAL)"
  
  # Check if cluster already exists
  local cluster_name="${EKS_CLUSTER_NAME:-rfp-dev-cluster}"
  if eksctl get cluster --name "$cluster_name" --region "$REGION" >/dev/null 2>&1; then
    log_success "EKS cluster already exists: $cluster_name"
    # Ensure kubeconfig context is present
    aws eks update-kubeconfig --region "$REGION" --name "$cluster_name" >/dev/null 2>&1 || true
    return 0
  fi
  
  local cluster_script="deployment/eks/create-cluster.sh"
  if [ ! -f "$cluster_script" ]; then
    log_warning "Cluster script not found: $cluster_script"
    return 1
  fi
  
  # Allow overrides via env vars
  [ -n "$EKS_CLUSTER_NAME" ] && export CLUSTER_NAME="$EKS_CLUSTER_NAME"
  [ -n "$EKS_NAMESPACE" ] && export EKS_NAMESPACE="$EKS_NAMESPACE"
  bash "$cluster_script"
}

deploy_java_api_eks() {
  log_header "DEPLOYING JAVA API TO EKS VIA HELM (OPTIONAL)"
  
  # Check prerequisites
  if ! command -v helm >/dev/null 2>&1; then
    log_warning "Helm not installed"
    log_info "Install Helm: brew install helm"
    log_info "Or visit: https://helm.sh/docs/intro/install/"
    return 1
  fi
  
  if ! command -v kubectl >/dev/null 2>&1; then
    log_warning "kubectl not installed"
    log_info "Install kubectl: brew install kubectl"
    return 1
  fi
  
  # Ensure cluster exists (create if needed, skip if already exists)
  deploy_eks_cluster || { log_warning "Failed to ensure EKS cluster exists"; return 1; }

  # Ensure kubeconfig is set to the target cluster
  if [ -n "${EKS_CLUSTER_NAME:-}" ]; then
    log_info "Updating kubeconfig for cluster $EKS_CLUSTER_NAME"
    aws eks update-kubeconfig --region "$REGION" --name "$EKS_CLUSTER_NAME" >/dev/null
  fi
  
  # Create Fargate profile if EKS_USE_FARGATE is true
  if [ "${EKS_USE_FARGATE:-false}" = "true" ]; then
    local cluster_name="${EKS_CLUSTER_NAME:-rfp-dev-cluster}"
    local namespace="${EKS_NAMESPACE:-rfp}"
    local profile_name="${namespace}-fargate"
    
    # Check if Fargate profile already exists
    if eksctl get fargateprofile --cluster "$cluster_name" --region "$REGION" --name "$profile_name" >/dev/null 2>&1; then
      log_info "Fargate profile '$profile_name' already exists for namespace '$namespace'"
    else
      log_info "Creating Fargate profile '$profile_name' for namespace '$namespace'"
      eksctl create fargateprofile \
        --cluster "$cluster_name" \
        --region "$REGION" \
        --name "$profile_name" \
        --namespace "$namespace"
      log_success "Fargate profile created: $profile_name"
    fi
  fi
  
  # Derive IMAGE_TAG if not provided
  if [ -z "${IMAGE_TAG:-}" ]; then
    IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
    export IMAGE_TAG
    log_info "IMAGE_TAG not set; using $IMAGE_TAG"
  fi
  
  # Build IMAGE_REPO from account/region/prefix if not provided
  if [ -z "${IMAGE_REPO:-}" ]; then
    local aws_account_id
    aws_account_id=$(aws sts get-caller-identity --query Account --output text)
    local repo_name
    repo_name="${BUCKET_PREFIX}-rfp-java-api"
    export IMAGE_REPO="$aws_account_id.dkr.ecr.$REGION.amazonaws.com/$repo_name"
    log_info "Using IMAGE_REPO: $IMAGE_REPO"
  fi
  
  # Validate image tag exists in ECR, fallback to 'latest' if missing
  if [ -n "${repo_name:-}" ]; then
    if ! aws ecr describe-images --repository-name "$repo_name" --image-ids imageTag="$IMAGE_TAG" --region "$REGION" >/dev/null 2>&1; then
      log_warning "ECR image tag '$IMAGE_TAG' not found in $repo_name; falling back to 'latest'"
      IMAGE_TAG="latest"
      export IMAGE_TAG
    fi
  fi
  
  # Map EKS_NAMESPACE to helm script's NAMESPACE variable if provided
  if [ -n "${EKS_NAMESPACE:-}" ]; then
    export NAMESPACE="$EKS_NAMESPACE"
  fi
  
  local helm_script="deployment/eks/deploy-java-api.sh"
  if [ ! -f "$helm_script" ]; then
    log_warning "Helm deploy script not found: $helm_script"
    return 1
  fi
  if [ -z "$IMAGE_TAG" ]; then
    log_warning "IMAGE_TAG not set. Export IMAGE_TAG=<ecr-tag> before running or pass inline."
  fi
  bash "$helm_script"
}

case "${1:-full}" in
  "verify")
    verify_prerequisites
    ;;
  "java-api")
    verify_prerequisites || true
    build_java_api
    deploy_java_api_ecs
    ;;
  "ui")
    verify_prerequisites || true
    build_react_ui
    deploy_ui_assets
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
    "eks-cluster")
      deploy_eks_cluster
      ;;
    "java-api-eks")
      deploy_eks_cluster  # Ensure cluster exists; harmless if already created
      deploy_java_api_eks
      ;;
    *)
        echo "Usage: $0 [verify|java-api|ui|cloudfront|test|full|eks-cluster|java-api-eks]"
        echo ""
        echo "Commands:"
        echo "  verify         - Check prerequisites and current deployment status"
        echo "  java-api       - Build and deploy Java API to ECS with Docker"
        echo "  ui             - Build and deploy React UI with CloudFront"
        echo "  cloudfront     - Create/update CloudFront distribution for UI"
        echo "  test           - Test deployed components (Java API & UI)"
        echo "  full           - Complete deployment: Java API + UI + CloudFront (default)"
        echo "  eks-cluster    - Create EKS cluster (optional, not in default flow)"
        echo "  java-api-eks   - Deploy Java API to EKS via Helm"
        echo ""
        echo "NOTE: Lambda functions and API Gateway are managed in separate project"
        ;;
esac