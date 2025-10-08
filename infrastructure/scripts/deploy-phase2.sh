#!/bin/bash

# AI-powered RFP Response Agent - Phase 2 Deployment (Lambda Functions)
# This script deploys only the Lambda functions and IAM roles

set -e

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME_PREFIX="ai-rfp-response-agent"
TEMPLATES_BUCKET=""
SAM_API_KEY=""
COMPANY_NAME=""
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
AI-powered RFP Response Agent - Phase 2 Deployment (Lambda Functions)

USAGE:
    $0 [OPTIONS]

This deploys Lambda functions and IAM roles. Requires Phase 1 to be deployed first.

OPTIONS:
    -e, --environment ENVIRONMENT    Environment name (dev, staging, prod) [default: dev]
    -r, --region REGION             AWS region [default: us-east-1]
    -b, --bucket BUCKET             S3 bucket for CloudFormation templates (required)
    -k, --api-key API_KEY           SAM.gov API key (required)
    -n, --company-name NAME         Company name for reports (required)
    -c, --company-contact EMAIL     Company contact email (required)
    -p, --bucket-prefix PREFIX      Prefix for S3 bucket names to avoid conflicts [optional]
    -h, --help                      Show this help message

EXAMPLES:
    $0 -e dev -b my-templates-bucket -k "your-api-key" -n "My Company" -c "contact@company.com" -p "mycompany"

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
        -k|--api-key)
            SAM_API_KEY="$2"
            shift 2
            ;;
        -n|--company-name)
            COMPANY_NAME="$2"
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

if [[ -z "$SAM_API_KEY" ]]; then
    print_error "SAM.gov API key is required. Use -k or --api-key option."
    exit 1
fi

if [[ -z "$COMPANY_NAME" ]]; then
    print_error "Company name is required. Use -n or --company-name option."
    exit 1
fi

if [[ -z "$COMPANY_CONTACT" ]]; then
    print_error "Company contact is required. Use -c or --company-contact option."
    exit 1
fi

STACK_NAME="$STACK_NAME_PREFIX-phase2-$ENVIRONMENT"
PHASE1_STACK_NAME="$STACK_NAME_PREFIX-phase1-$ENVIRONMENT"

print_status "Deploying Phase 2: Lambda Functions"
echo "  Environment: $ENVIRONMENT"
echo "  Stack Name: $STACK_NAME"
echo "  Bucket Prefix: $BUCKET_PREFIX"

# Get SQS Queue ARN from Phase 1 stack
SQS_QUEUE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$PHASE1_STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='SqsSamJsonMessagesQueueArn'].OutputValue" \
    --output text)

if [[ -z "$SQS_QUEUE_ARN" || "$SQS_QUEUE_ARN" == "None" ]]; then
    print_error "Phase 1 stack not found or incomplete. Please deploy Phase 1 first."
    exit 1
fi

print_status "Found SQS Queue ARN: $SQS_QUEUE_ARN"

# Create parameters file
PARAMS_FILE="/tmp/deploy-phase2-params-${ENVIRONMENT}.json"
cat > "$PARAMS_FILE" << EOF
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "$ENVIRONMENT"
  },
  {
    "ParameterKey": "SamApiKey",
    "ParameterValue": "$SAM_API_KEY"
  },
  {
    "ParameterKey": "CompanyName",
    "ParameterValue": "$COMPANY_NAME"
  },
  {
    "ParameterKey": "CompanyContact",
    "ParameterValue": "$COMPANY_CONTACT"
  },
  {
    "ParameterKey": "SqsSamJsonMessagesQueueArn",
    "ParameterValue": "$SQS_QUEUE_ARN"
  },
  {
    "ParameterKey": "BucketPrefix",
    "ParameterValue": "$BUCKET_PREFIX"
  }
]
EOF

TEMPLATE_URL="https://$TEMPLATES_BUCKET.s3.amazonaws.com/ai-rfp-response-agent/lambda-functions.yaml"

# Check if stack exists and deploy
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
    print_status "Updating existing stack..."
    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    aws cloudformation wait stack-update-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
else
    print_status "Creating new stack..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
fi

if [[ $? -eq 0 ]]; then
    print_success "Phase 2 deployment completed!"
else
    print_error "Phase 2 deployment failed!"
    exit 1
fi

# Cleanup
rm -f "$PARAMS_FILE"