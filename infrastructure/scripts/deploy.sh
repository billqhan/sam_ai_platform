#!/bin/bash

# AI-powered RFP Response Agent - Deployment Script
# This script deploys the CloudFormation infrastructure

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CF_DIR="$PROJECT_ROOT/infrastructure/cloudformation"

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME_PREFIX="ai-rfp-response-agent"
TEMPLATES_BUCKET=""
SAM_API_KEY=""
COMPANY_NAME=""
COMPANY_CONTACT=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy the AI-powered RFP Response Agent infrastructure

OPTIONS:
    -e, --environment ENVIRONMENT    Environment name (dev, staging, prod) [default: dev]
    -r, --region REGION             AWS region [default: us-east-1]
    -b, --bucket BUCKET             S3 bucket for CloudFormation templates (required)
    -k, --api-key API_KEY           SAM.gov API key (required)
    -n, --company-name NAME         Company name for reports (required)
    -c, --company-contact EMAIL     Company contact email (required)
    -s, --stack-name STACK_NAME     Custom stack name prefix [default: ai-rfp-response-agent]
    -h, --help                      Show this help message

EXAMPLES:
    $0 -e dev -b my-templates-bucket -k "your-api-key" -n "My Company" -c "contact@company.com"
    $0 --environment prod --bucket prod-templates --api-key "key" --company-name "Company" --company-contact "email@company.com"

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
        -s|--stack-name)
            STACK_NAME_PREFIX="$2"
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

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

# Set stack name
STACK_NAME="${STACK_NAME_PREFIX}-${ENVIRONMENT}"

print_status "Starting deployment with the following configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $REGION"
echo "  Stack Name: $STACK_NAME"
echo "  Templates Bucket: $TEMPLATES_BUCKET"
echo "  Company Name: $COMPANY_NAME"
echo "  Company Contact: $COMPANY_CONTACT"
echo ""

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if templates bucket exists
print_status "Checking if templates bucket exists..."
if ! aws s3 ls "s3://$TEMPLATES_BUCKET" &> /dev/null; then
    print_error "Templates bucket '$TEMPLATES_BUCKET' does not exist or is not accessible."
    exit 1
fi

# Upload CloudFormation templates
print_status "Uploading CloudFormation templates to S3..."
aws s3 sync "$CF_DIR" "s3://$TEMPLATES_BUCKET/ai-rfp-response-agent/" \
    --exclude "*.md" \
    --exclude "*.json" \
    --exclude "README*" \
    --delete

if [[ $? -eq 0 ]]; then
    print_success "Templates uploaded successfully"
else
    print_error "Failed to upload templates"
    exit 1
fi

# Create parameters file
PARAMS_FILE="/tmp/deploy-params-${ENVIRONMENT}.json"
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
    "ParameterKey": "TemplatesBucketName",
    "ParameterValue": "$TEMPLATES_BUCKET"
  },
  {
    "ParameterKey": "TemplatesBucketPrefix",
    "ParameterValue": "ai-rfp-response-agent/"
  }
]
EOF

# Check if stack exists
print_status "Checking if stack exists..."
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
    STACK_EXISTS=true
    print_status "Stack exists. Will update existing stack."
else
    STACK_EXISTS=false
    print_status "Stack does not exist. Will create new stack."
fi

# Deploy or update stack
TEMPLATE_URL="https://$TEMPLATES_BUCKET.s3.amazonaws.com/ai-rfp-response-agent/master-template.yaml"

if [[ "$STACK_EXISTS" == true ]]; then
    print_status "Updating CloudFormation stack..."
    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    if [[ $? -eq 0 ]]; then
        print_status "Stack update initiated. Waiting for completion..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            print_success "Stack updated successfully!"
        else
            print_error "Stack update failed!"
            exit 1
        fi
    else
        print_error "Failed to initiate stack update"
        exit 1
    fi
else
    print_status "Creating CloudFormation stack..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --tags Key=Environment,Value="$ENVIRONMENT" Key=Project,Value="AI-RFP-Response-Agent"
    
    if [[ $? -eq 0 ]]; then
        print_status "Stack creation initiated. Waiting for completion..."
        aws cloudformation wait stack-create-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            print_success "Stack created successfully!"
        else
            print_error "Stack creation failed!"
            exit 1
        fi
    else
        print_error "Failed to initiate stack creation"
        exit 1
    fi
fi

# Get stack outputs
print_status "Retrieving stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs' \
    --output table)

if [[ $? -eq 0 ]]; then
    print_success "Deployment completed successfully!"
    echo ""
    echo "Stack Outputs:"
    echo "$OUTPUTS"
    echo ""
    print_status "Next steps:"
    echo "1. Upload company information to the sam-company-info-${ENVIRONMENT} S3 bucket"
    echo "2. Configure the Bedrock Knowledge Base ID in Lambda environment variables"
    echo "3. Test the pipeline by triggering the daily download function"
    echo "4. Monitor the CloudWatch dashboard for system health"
else
    print_warning "Deployment completed but failed to retrieve outputs"
fi

# Cleanup temporary files
rm -f "$PARAMS_FILE"

print_success "Deployment script completed!"