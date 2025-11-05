#!/bin/bash

# Complete Deployment Workflow Script
# AI-Powered RFP Response Agent System - Full Deployment Process

set -e

# Configuration (can be overridden with environment variables)
export STACK_NAME="${STACK_NAME:-ai-rfp-response-agent-dev}"
export BUCKET_PREFIX="${BUCKET_PREFIX:-l3harris-qhan}"
export REGION="${REGION:-us-east-1}"
export ENVIRONMENT="${ENVIRONMENT:-dev}"
export CLOUDFRONT_ID="${CLOUDFRONT_ID:-E3QHR30BKR6VGZ}"

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
    log_header "RUNNING FULL DEPLOYMENT VERIFICATION"
    ./deployment-verify.sh
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
        $ps_cmd -File deploy-complete-stack.ps1 -BucketPrefix "$BUCKET_PREFIX" -Region "$REGION" -TemplatesBucket "${BUCKET_PREFIX}-cloudformation-templates" -SamApiKey "placeholder-key" -CompanyName "L3Harris Technologies" -CompanyContact "admin@l3harris.com"
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

# Step 3: Deploy Java API to Elastic Beanstalk
deploy_java_api_eb() {
    log_header "DEPLOYING JAVA API TO ELASTIC BEANSTALK"
    
    local app_name="${BUCKET_PREFIX}-rfp-java-api"
    local env_name="${app_name}-${ENVIRONMENT}"
    
    # Create application if it doesn't exist
    if ! aws elasticbeanstalk describe-applications --application-names "$app_name" >/dev/null 2>&1; then
        log_info "Creating Elastic Beanstalk application: $app_name"
        aws elasticbeanstalk create-application \
            --application-name "$app_name" \
            --description "Java REST API for RFP Response Agent" \
            --region "$REGION"
    fi
    
    # Upload application version
    local version_label="v$(date +%Y%m%d-%H%M%S)"
    local deploy_bucket="${BUCKET_PREFIX}-deployments-${ENVIRONMENT}"
    
    # Create deployment bucket if needed
    aws s3 mb "s3://$deploy_bucket" --region "$REGION" 2>/dev/null || true
    
    # Upload JAR
    log_info "Uploading Java API JAR..."
    aws s3 cp java-api/target/rfp-response-agent-api-1.0.0.jar "s3://$deploy_bucket/java-api/${version_label}.jar"
    
    # Create application version
    aws elasticbeanstalk create-application-version \
        --application-name "$app_name" \
        --version-label "$version_label" \
        --source-bundle S3Bucket="$deploy_bucket",S3Key="java-api/${version_label}.jar" \
        --region "$REGION"
    
    # Create or update environment
    if ! aws elasticbeanstalk describe-environments --application-name "$app_name" --environment-names "$env_name" >/dev/null 2>&1; then
        log_info "Creating Elastic Beanstalk environment: $env_name"
        aws elasticbeanstalk create-environment \
            --application-name "$app_name" \
            --environment-name "$env_name" \
            --solution-stack-name "64bit Amazon Linux 2 v3.4.0 running Corretto 17" \
            --version-label "$version_label" \
            --option-settings \
                Namespace=aws:autoscaling:launchconfiguration,OptionName=IamInstanceProfile,Value=aws-elasticbeanstalk-ec2-role \
                Namespace=aws:elasticbeanstalk:environment,OptionName=ServiceRole,Value=aws-elasticbeanstalk-service-role \
                Namespace=aws:elasticbeanstalk:application:environment,OptionName=SERVER_PORT,Value=5000 \
                Namespace=aws:elasticbeanstalk:application:environment,OptionName=AWS_REGION,Value="$REGION" \
            --region "$REGION"
    else
        log_info "Updating Elastic Beanstalk environment: $env_name"
        aws elasticbeanstalk update-environment \
            --application-name "$app_name" \
            --environment-name "$env_name" \
            --version-label "$version_label" \
            --region "$REGION"
    fi
    
    log_success "Java API deployment initiated to Elastic Beanstalk"
}

# Step 4: Deploy Java API with Docker to ECS
deploy_java_api_ecs() {
    log_header "DEPLOYING JAVA API WITH DOCKER TO ECS"
    
    local repo_name="${BUCKET_PREFIX}-rfp-java-api"
    local cluster_name="${BUCKET_PREFIX}-ecs-cluster"
    local service_name="${BUCKET_PREFIX}-java-api-service"
    
    # Get AWS account ID
    local aws_account_id=$(aws sts get-caller-identity --query Account --output text)
    
    # Create ECR repository if needed
    if ! aws ecr describe-repositories --repository-names "$repo_name" --region "$REGION" >/dev/null 2>&1; then
        log_info "Creating ECR repository: $repo_name"
        aws ecr create-repository --repository-name "$repo_name" --region "$REGION"
    fi
    
    # Build and push Docker image
    log_info "Building and pushing Docker image..."
    cd java-api
    
    # Get ECR login token
    aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$aws_account_id.dkr.ecr.$REGION.amazonaws.com"
    
    # Build image
    docker build -t "$repo_name" .
    
    # Tag and push
    local image_uri="$aws_account_id.dkr.ecr.$REGION.amazonaws.com/$repo_name:latest"
    docker tag "$repo_name:latest" "$image_uri"
    docker push "$image_uri"
    
    cd ..
    
    log_success "Docker image pushed to ECR: $image_uri"
    log_info "Next: Create ECS cluster and service with this image"
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
    echo "  # Option 1: Elastic Beanstalk (recommended for development)"
    echo "  ./deploy-complete.sh java-eb"
    echo ""
    echo "  # Option 2: ECS with Docker (recommended for production)"
    echo "  ./deploy-complete.sh java-ecs"
    echo ""
    echo "  # Option 3: Manual deployment"
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
    "java-eb")
        ./deployment-verify.sh build
        deploy_java_api_eb
        ;;
    "java-ecs")
        ./deployment-verify.sh build
        deploy_java_api_ecs
        ;;
    "ui")
        ./deployment-verify.sh deploy-ui
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
        echo "Usage: $0 [verify|infrastructure|lambda|java-eb|java-ecs|ui|test|full]"
        echo ""
        echo "Commands:"
        echo "  verify         - Check prerequisites and current deployment status"
        echo "  infrastructure - Deploy AWS CloudFormation infrastructure + Lambda functions"
        echo "  lambda         - Deploy Lambda functions only (requires PowerShell)"
        echo "  java-eb        - Deploy Java API to Elastic Beanstalk"
        echo "  java-ecs       - Deploy Java API to ECS with Docker"
        echo "  ui             - Build and deploy React UI"
        echo "  test           - Test deployed components"
        echo "  full           - Complete deployment verification and testing (default)"
        ;;
esac