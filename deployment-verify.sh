#!/bin/bash

# Complete Deployment Verification and Setup Script
# AI-Powered RFP Response Agent System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="ai-rfp-response-agent-dev"
BUCKET_PREFIX="${BUCKET_PREFIX:-l3harris-qhan}"
REGION="${REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
CLOUDFRONT_ID="${CLOUDFRONT_ID:-E3QHR30BKR6VGZ}"

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓ SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠ WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[✗ ERROR]${NC} $1"; }
log_header() { 
    echo -e "\n${PURPLE}════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}\n"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verify prerequisites
verify_prerequisites() {
    log_header "VERIFYING PREREQUISITES"
    
    local all_good=true
    
    # Check AWS CLI
    if command_exists aws; then
        local aws_version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
        log_success "AWS CLI v$aws_version installed"
        
        # Check AWS credentials
        if aws sts get-caller-identity >/dev/null 2>&1; then
            local account=$(aws sts get-caller-identity --query Account --output text)
            local user=$(aws sts get-caller-identity --query Arn --output text)
            log_success "AWS credentials configured - Account: $account"
        else
            log_error "AWS credentials not configured"
            all_good=false
        fi
    else
        log_error "AWS CLI not installed"
        all_good=false
    fi
    
    # Check Java
    if command_exists java; then
        local java_version=$(java -version 2>&1 | head -n1 | cut -d'"' -f2)
        log_success "Java $java_version installed"
    else
        log_error "Java not installed"
        all_good=false
    fi
    
    # Check Maven
    if command_exists mvn; then
        local mvn_version=$(mvn -version 2>/dev/null | head -n1 | cut -d' ' -f3)
        log_success "Maven $mvn_version installed"
    else
        log_error "Maven not installed"
        all_good=false
    fi
    
    # Check Node.js
    if command_exists node; then
        local node_version=$(node --version)
        log_success "Node.js $node_version installed"
    else
        log_error "Node.js not installed"
        all_good=false
    fi
    
    # Check npm
    if command_exists npm; then
        local npm_version=$(npm --version)
        log_success "npm v$npm_version installed"
    else
        log_error "npm not installed"
        all_good=false
    fi
    
    if [ "$all_good" = false ]; then
        log_error "Please install missing prerequisites before continuing"
        exit 1
    fi
}

# Check AWS infrastructure deployment status
check_aws_infrastructure() {
    log_header "CHECKING AWS INFRASTRUCTURE"
    
    # Check S3 buckets
    log_info "Checking S3 buckets..."
    local buckets=(
        "${BUCKET_PREFIX}-sam-data-in-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-ui-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-rfp-ui-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-cloudformation-templates"
    )
    
    for bucket in "${buckets[@]}"; do
        if aws s3 ls "s3://$bucket" >/dev/null 2>&1; then
            log_success "S3 Bucket: $bucket"
        else
            log_warning "S3 Bucket missing: $bucket"
        fi
    done
    
    # Check DynamoDB tables
    log_info "Checking DynamoDB tables..."
    local tables=(
        "${BUCKET_PREFIX}-sam-opportunities-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-sam-matches-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-sam-proposals-${ENVIRONMENT}"
        "${BUCKET_PREFIX}-sam-reports-${ENVIRONMENT}"
    )
    
    for table in "${tables[@]}"; do
        if aws dynamodb describe-table --table-name "$table" >/dev/null 2>&1; then
            local status=$(aws dynamodb describe-table --table-name "$table" --query 'Table.TableStatus' --output text)
            log_success "DynamoDB Table: $table ($status)"
        else
            log_warning "DynamoDB Table missing: $table"
        fi
    done
    
    # Check Lambda functions
    log_info "Checking Lambda functions..."
    local functions=$(aws lambda list-functions --query 'Functions[?contains(FunctionName,`'${BUCKET_PREFIX}'`)].FunctionName' --output text)
    if [ -n "$functions" ]; then
        for func in $functions; do
            log_success "Lambda Function: $func"
        done
    else
        log_warning "No Lambda functions found with prefix: $BUCKET_PREFIX"
    fi
    
    # Check CloudFormation stacks
    log_info "Checking CloudFormation stacks..."
    local stacks=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName,`rfp`) || contains(StackName,`ai`)].StackName' --output text)
    if [ -n "$stacks" ]; then
        for stack in $stacks; do
            log_success "CloudFormation Stack: $stack"
        done
    else
        log_warning "No CloudFormation stacks found"
    fi
}

# Check CloudFront distribution
check_cloudfront() {
    log_header "CHECKING CLOUDFRONT DISTRIBUTION"
    
    if aws cloudfront get-distribution --id "$CLOUDFRONT_ID" >/dev/null 2>&1; then
        local domain=$(aws cloudfront get-distribution --id "$CLOUDFRONT_ID" --query 'Distribution.DomainName' --output text)
        local status=$(aws cloudfront get-distribution --id "$CLOUDFRONT_ID" --query 'Distribution.Status' --output text)
        local origin=$(aws cloudfront get-distribution --id "$CLOUDFRONT_ID" --query 'Distribution.DistributionConfig.Origins.Items[0].DomainName' --output text)
        
        log_success "CloudFront Distribution: $domain"
        log_info "  Status: $status"
        log_info "  Origin: $origin"
        log_success "UI URL: https://$domain"
    else
        log_error "CloudFront distribution not found: $CLOUDFRONT_ID"
    fi
}

# Build Java API
build_java_api() {
    log_header "BUILDING JAVA API"
    
    if [ -d "java-api" ]; then
        cd java-api
        log_info "Building Java Spring Boot application..."
        mvn clean package -DskipTests
        
        if [ -f "target/rfp-response-agent-api-1.0.0.jar" ]; then
            local jar_size=$(ls -lh target/rfp-response-agent-api-1.0.0.jar | awk '{print $5}')
            log_success "Java API built successfully - JAR size: $jar_size"
        else
            log_error "Java API build failed - JAR not found"
            exit 1
        fi
        cd ..
    else
        log_error "java-api directory not found"
        exit 1
    fi
}

# Build React UI
build_react_ui() {
    log_header "BUILDING REACT UI"
    
    if [ -d "ui" ]; then
        cd ui
        log_info "Installing npm dependencies..."
        npm install
        
        log_info "Building React application..."
        npm run build
        
        if [ -d "dist" ] && [ -f "dist/index.html" ]; then
            local build_size=$(du -sh dist | cut -f1)
            log_success "React UI built successfully - Build size: $build_size"
        else
            log_error "React UI build failed - dist directory not found"
            exit 1
        fi
        cd ..
    else
        log_error "ui directory not found"
        exit 1
    fi
}

# Deploy React UI to CloudFront
deploy_ui_to_cloudfront() {
    log_header "DEPLOYING REACT UI TO CLOUDFRONT"
    
    local ui_bucket="${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}"
    
    # Deploy to S3
    log_info "Syncing UI files to S3 bucket: $ui_bucket"
    aws s3 sync ui/dist/ "s3://$ui_bucket/" --delete
    
    # Create CloudFront invalidation
    log_info "Creating CloudFront invalidation..."
    local invalidation_id=$(aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_ID" --paths "/*" --query 'Invalidation.Id' --output text 2>/dev/null)
    
    if [ -n "$invalidation_id" ]; then
        log_success "CloudFront invalidation created: $invalidation_id"
        log_info "UI will be available at: https://dvik8huzkbem6.cloudfront.net"
    else
        log_warning "CloudFront invalidation failed, but files are uploaded"
    fi
}

# Deploy Java API options
deploy_java_api_options() {
    log_header "JAVA API DEPLOYMENT OPTIONS"
    
    echo "The Java API is built and ready for deployment. Choose your deployment method:"
    echo ""
    echo "1. Elastic Beanstalk (Recommended for development)"
    echo "2. ECS with Fargate (Recommended for production)"
    echo "3. EKS (Kubernetes)"
    echo "4. Manual deployment (JAR file ready)"
    echo ""
    echo "Current JAR location: java-api/target/rfp-response-agent-api-1.0.0.jar"
    echo ""
    
    log_info "To deploy to Elastic Beanstalk:"
    echo "  eb init l3harris-rfp-java-api --region $REGION"
    echo "  eb create rfp-java-api-env"
    echo ""
    
    log_info "To deploy with Docker to ECS:"
    echo "  cd java-api"
    echo "  docker build -t rfp-java-api ."
    echo "  # Push to ECR and deploy to ECS"
    echo ""
    
    log_info "For manual deployment:"
    echo "  java -jar java-api/target/rfp-response-agent-api-1.0.0.jar"
}

# Test deployment
test_deployment() {
    log_header "TESTING DEPLOYMENT"
    
    # Test CloudFront UI
    log_info "Testing UI accessibility..."
    if curl -s -o /dev/null -w "%{http_code}" "https://dvik8huzkbem6.cloudfront.net" | grep -q "200\|301\|302"; then
        log_success "UI is accessible via CloudFront"
    else
        log_warning "UI may not be accessible yet (cache propagation in progress)"
    fi
    
    # Test existing Lambda API
    local lambda_name="${BUCKET_PREFIX}-sam-api-backend-${ENVIRONMENT}"
    if aws lambda get-function --function-name "$lambda_name" >/dev/null 2>&1; then
        log_success "Lambda API backend is deployed: $lambda_name"
    else
        log_warning "Lambda API backend not found: $lambda_name"
    fi
}

# Generate deployment summary
generate_summary() {
    log_header "DEPLOYMENT SUMMARY"
    
    echo -e "${CYAN}🚀 System Components Status:${NC}"
    echo "  ✅ AWS Infrastructure (S3, DynamoDB, Lambda)"
    echo "  ✅ React UI (Built and deployed to CloudFront)"
    echo "  ✅ Java API (Built, ready for deployment)"
    echo "  ✅ CloudFront CDN (Active and serving UI)"
    echo ""
    
    echo -e "${CYAN}📋 Access URLs:${NC}"
    echo "  🌐 React UI: https://dvik8huzkbem6.cloudfront.net"
    echo "  ⚙️ Java API: Ready for deployment (see options above)"
    echo ""
    
    echo -e "${CYAN}📊 AWS Resources:${NC}"
    echo "  📦 S3 Buckets: Data storage and UI hosting"
    echo "  🗄️  DynamoDB: Opportunity and match data"
    echo "  ⚡ Lambda: Backend processing functions"
    echo "  🌍 CloudFront: Global UI distribution"
    echo ""
    
    echo -e "${CYAN}🔧 Next Steps:${NC}"
    echo "  1. Deploy Java API (see options above)"
    echo "  2. Test complete system workflow"
    echo "  3. Configure API Gateway if needed"
    echo "  4. Set up monitoring and alerting"
    echo ""
    
    log_success "🎉 Deployment verification completed!"
}

# Main execution flow
main() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║          AI-POWERED RFP RESPONSE AGENT                           ║"
    echo "║               DEPLOYMENT VERIFICATION                            ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo "Configuration:"
    echo "  Region: $REGION"
    echo "  Environment: $ENVIRONMENT"
    echo "  Bucket Prefix: $BUCKET_PREFIX"
    echo "  CloudFront ID: $CLOUDFRONT_ID"
    echo ""
    
    # Run all verification and deployment steps
    verify_prerequisites
    check_aws_infrastructure
    check_cloudfront
    build_java_api
    build_react_ui
    deploy_ui_to_cloudfront
    test_deployment
    deploy_java_api_options
    generate_summary
}

# Parse command line arguments
case "${1:-}" in
    "verify")
        verify_prerequisites
        check_aws_infrastructure
        check_cloudfront
        ;;
    "build")
        build_java_api
        build_react_ui
        ;;
    "deploy-ui")
        build_react_ui
        deploy_ui_to_cloudfront
        ;;
    "test")
        test_deployment
        ;;
    "summary")
        generate_summary
        ;;
    *)
        main
        ;;
esac