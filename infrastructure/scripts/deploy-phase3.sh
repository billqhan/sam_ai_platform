#!/bin/bash

# AI-powered RFP Response Agent - Phase 3 Deployment (Security & Monitoring)
# This script deploys IAM security policies and monitoring

set -e

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME_PREFIX="ai-rfp-response-agent"
TEMPLATES_BUCKET=""
COMPANY_CONTACT=""
BUCKET_PREFIX=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    cat << EOF
AI-powered RFP Response Agent - Phase 3 Deployment (Security & Monitoring)

USAGE:
    $0 [OPTIONS]

This deploys security policies and monitoring. Requires Phase 1 and 2 to be deployed first.

OPTIONS:
    -e, --environment ENVIRONMENT    Environment name (dev, staging, prod) [default: dev]
    -r, --region REGION             AWS region [default: us-east-1]
    -b, --bucket BUCKET             S3 bucket for CloudFormation templates (required)
    -c, --company-contact EMAIL     Company contact email (required)
    -p, --bucket-prefix PREFIX      Prefix for S3 bucket names to avoid conflicts [optional]
    -h, --help                      Show this help message

EXAMPLES:
    $0 -e dev -b my-templates-bucket -c "contact@company.com" -p "mycompany"

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -b|--bucket)
            TEMPLATES_BUCKET="$2"
            shift 2
            ;;
        -c|--company-contact)
            COMPANY_CONTACT="$2"
            shift 2
            ;;
        -p|--bucket-prefix)
            BUCKET_PREFIX="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$TEMPLATES_BUCKET" ]]; then
    print_error "Templates bucket is required. Use -b or --bucket option."
    exit 1
fi

if [[ -z "$COMPANY_CONTACT" ]]; then
    print_error "Company contact is required. Use -c or --company-contact option."
    exit 1
fi

print_status "Deploying Phase 3: Security & Monitoring"
echo "  Environment: $ENVIRONMENT"
echo "  Bucket Prefix: $BUCKET_PREFIX"

# Create parameters file
PARAMS_FILE="/tmp/deploy-phase3-params-${ENVIRONMENT}.json"
cat > "$PARAMS_FILE" << EOF
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "$ENVIRONMENT"
  },
  {
    "ParameterKey": "BucketPrefix",
    "ParameterValue": "$BUCKET_PREFIX"
  }
]
EOF

# Deploy IAM Security Policies
IAM_STACK_NAME="$STACK_NAME_PREFIX-iam-$ENVIRONMENT"
IAM_TEMPLATE_URL="https://$TEMPLATES_BUCKET.s3.amazonaws.com/ai-rfp-response-agent/iam-security-policies-simple.yaml"

print_status "Deploying IAM Security Policies..."

if aws cloudformation describe-stacks --stack-name "$IAM_STACK_NAME" --region "$REGION" &> /dev/null; then
    aws cloudformation update-stack \
        --stack-name "$IAM_STACK_NAME" \
        --template-url "$IAM_TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    aws cloudformation wait stack-update-complete \
        --stack-name "$IAM_STACK_NAME" \
        --region "$REGION"
else
    aws cloudformation create-stack \
        --stack-name "$IAM_STACK_NAME" \
        --template-url "$IAM_TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    aws cloudformation wait stack-create-complete \
        --stack-name "$IAM_STACK_NAME" \
        --region "$REGION"
fi

if [[ $? -eq 0 ]]; then
    print_success "IAM Security Policies deployed!"
else
    print_error "IAM Security Policies deployment failed!"
    exit 1
fi

print_success "Phase 3 deployment completed!"

# Cleanup
rm -f "$PARAMS_FILE"