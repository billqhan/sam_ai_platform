#!/bin/bash

# AI-powered RFP Response Agent - Multi-Phase Deployment Script
# This script can deploy all phases or individual phases

set -e

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
TEMPLATES_BUCKET=""
SAM_API_KEY=""
COMPANY_NAME=""
COMPANY_CONTACT=""
BUCKET_PREFIX=""
PHASE="all"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
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
AI-powered RFP Response Agent - Multi-Phase Deployment

USAGE:
    $0 [OPTIONS]

PHASES:
    Phase 1: Core Infrastructure (S3 buckets, SQS queues)
    Phase 2: Lambda Functions (simplified versions)
    Phase 3: Security & Monitoring (IAM policies, KMS keys)

OPTIONS:
    -e, --environment ENVIRONMENT    Environment name (dev, staging, prod) [default: dev]
    -r, --region REGION             AWS region [default: us-east-1]
    -b, --bucket BUCKET             S3 bucket for CloudFormation templates (required)
    -k, --api-key API_KEY           SAM.gov API key (required)
    -n, --company-name NAME         Company name for reports (required)
    -c, --company-contact EMAIL     Company contact email (required)
    -p, --bucket-prefix PREFIX      Prefix for S3 bucket names to avoid conflicts [optional]
    --phase PHASE                   Deploy specific phase (1|2|3|all) [default: all]
    -h, --help                      Show this help message

EXAMPLES:
    # Deploy all phases
    $0 -b "my-bucket" -k "key" -n "My Company" -c "email@company.com"
    
    # Deploy only Phase 1
    $0 -b "my-bucket" -k "key" -n "My Company" -c "email@company.com" --phase 1
    
    # Deploy with bucket prefix
    $0 -b "my-bucket" -k "key" -n "My Company" -c "email@company.com" -p "mycompany"

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
        --phase)
            PHASE="$2"
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

# Validate required parameters for phases that need them
if [[ "$PHASE" == "all" || "$PHASE" == "1" || "$PHASE" == "2" ]]; then
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
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}=== AI-powered RFP Response Agent - Multi-Phase Deployment ===${NC}"
echo -e "${WHITE}Environment: $ENVIRONMENT${NC}"
echo -e "${WHITE}Region: $REGION${NC}"
echo -e "${WHITE}Bucket Prefix: $BUCKET_PREFIX${NC}"
echo -e "${WHITE}Phase: $PHASE${NC}"
echo ""

# Upload templates first
print_status "Uploading CloudFormation templates..."
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CF_DIR="$PROJECT_ROOT/infrastructure/cloudformation"
aws s3 sync "$CF_DIR" "s3://$TEMPLATES_BUCKET/ai-rfp-response-agent/" \
    --exclude "*.md" \
    --exclude "*.json" \
    --exclude "README*" \
    --delete

if [[ $? -ne 0 ]]; then
    print_error "Failed to upload templates"
    exit 1
fi
print_success "Templates uploaded"

# Phase 1: Core Infrastructure
if [[ "$PHASE" == "1" || "$PHASE" == "all" ]]; then
    echo ""
    echo -e "${YELLOW}=== PHASE 1: Core Infrastructure ===${NC}"
    "$SCRIPT_DIR/deploy-phase1.sh" \
        -e "$ENVIRONMENT" \
        -r "$REGION" \
        -b "$TEMPLATES_BUCKET" \
        -k "$SAM_API_KEY" \
        -n "$COMPANY_NAME" \
        -c "$COMPANY_CONTACT" \
        -p "$BUCKET_PREFIX"
    
    if [[ $? -ne 0 ]]; then
        print_error "Phase 1 failed. Stopping deployment."
        exit 1
    fi
fi

# Phase 2: Lambda Functions
if [[ "$PHASE" == "2" || "$PHASE" == "all" ]]; then
    echo ""
    echo -e "${YELLOW}=== PHASE 2: Lambda Functions ===${NC}"
    "$SCRIPT_DIR/deploy-phase2.sh" \
        -e "$ENVIRONMENT" \
        -r "$REGION" \
        -b "$TEMPLATES_BUCKET" \
        -k "$SAM_API_KEY" \
        -n "$COMPANY_NAME" \
        -c "$COMPANY_CONTACT" \
        -p "$BUCKET_PREFIX"
    
    if [[ $? -ne 0 ]]; then
        print_error "Phase 2 failed. Stopping deployment."
        exit 1
    fi
fi

# Phase 3: Security & Monitoring
if [[ "$PHASE" == "3" || "$PHASE" == "all" ]]; then
    echo ""
    echo -e "${YELLOW}=== PHASE 3: Security & Monitoring ===${NC}"
    "$SCRIPT_DIR/deploy-phase3.sh" \
        -e "$ENVIRONMENT" \
        -r "$REGION" \
        -b "$TEMPLATES_BUCKET" \
        -c "$COMPANY_CONTACT" \
        -p "$BUCKET_PREFIX"
    
    if [[ $? -ne 0 ]]; then
        print_error "Phase 3 failed. Stopping deployment."
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}=== DEPLOYMENT COMPLETED SUCCESSFULLY ===${NC}"
echo -e "${GREEN}All requested phases have been deployed successfully!${NC}"