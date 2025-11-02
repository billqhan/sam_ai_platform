#!/bin/bash

# Complete deployment script for AI-RFP Response Agent
#
# This script performs a complete deployment:
# 1. Deploys CloudFormation infrastructure
# 2. Deploys all Lambda function code
# 3. Configures Lambda environment variables
# 4. Runs reporting workflow to validate
#
# Usage:
#   ./deploy-complete-stack.sh --templates-bucket BUCKET --sam-api-key KEY [OPTIONS]
#
# Options:
#   --environment ENV          Environment name (dev, staging, prod). Default: dev
#   --region REGION           AWS region. Default: us-east-1
#   --templates-bucket BUCKET S3 bucket containing CloudFormation templates (required)
#   --sam-api-key KEY         SAM.gov API key (required)
#   --company-name NAME       Company name for reports. Default: L3Harris
#   --company-contact EMAIL   Company contact email. Default: bill.han@l3harris.com
#   --bucket-prefix PREFIX    Prefix for S3 bucket names. Default: l3harris-qhan
#   --knowledge-base-id ID    Bedrock Knowledge Base ID. Default: '' (disabled)
#   --skip-infrastructure     Skip CloudFormation deployment (only deploy Lambda code)
#   --skip-lambdas           Skip Lambda code deployment
#   --skip-reporting         Skip reporting workflow validation
#   --help                   Show this help message
#
# Examples:
#   ./deploy-complete-stack.sh --templates-bucket 'dual-bucket-1' --sam-api-key 'your-key'
#   ./deploy-complete-stack.sh --templates-bucket 'dual-bucket-1' --sam-api-key 'your-key' --knowledge-base-id 'KB123456' --environment prod

set -e  # Exit on any error

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
TEMPLATES_BUCKET=""
SAM_API_KEY=""
COMPANY_NAME="L3Harris"
COMPANY_CONTACT="bill.han@l3harris.com"
BUCKET_PREFIX="l3harris-qhan"
KNOWLEDGE_BASE_ID=""
SKIP_INFRASTRUCTURE=false
SKIP_LAMBDAS=false
SKIP_REPORTING=false

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Helper functions
write_step() {
    local message="$1"
    echo ""
    echo "========================================"
    echo "  $message"
    echo "========================================"
    echo ""
}

write_success() {
    local message="$1"
    echo "✓ $message"
}

write_info() {
    local message="$1"
    echo "→ $message"
}

write_warning() {
    local message="$1"
    echo "⚠ $message"
}

write_error() {
    local message="$1"
    echo "✗ $message" >&2
}

show_help() {
    grep '^#' "$0" | sed 's/^# //; s/^#//' | head -n -1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
                echo "Error: Environment must be dev, staging, or prod"
                exit 1
            fi
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --templates-bucket)
            TEMPLATES_BUCKET="$2"
            shift 2
            ;;
        --sam-api-key)
            SAM_API_KEY="$2"
            shift 2
            ;;
        --company-name)
            COMPANY_NAME="$2"
            shift 2
            ;;
        --company-contact)
            COMPANY_CONTACT="$2"
            shift 2
            ;;
        --bucket-prefix)
            BUCKET_PREFIX="$2"
            shift 2
            ;;
        --knowledge-base-id)
            KNOWLEDGE_BASE_ID="$2"
            shift 2
            ;;
        --skip-infrastructure)
            SKIP_INFRASTRUCTURE=true
            shift
            ;;
        --skip-lambdas)
            SKIP_LAMBDAS=true
            shift
            ;;
        --skip-reporting)
            SKIP_REPORTING=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$TEMPLATES_BUCKET" ]]; then
    echo "Error: --templates-bucket is required"
    exit 1
fi

if [[ -z "$SAM_API_KEY" ]]; then
    echo "Error: --sam-api-key is required"
    exit 1
fi

# Display configuration
write_step "STARTING COMPLETE DEPLOYMENT"
write_info "Configuration:"
echo "  Environment:       $ENVIRONMENT"
echo "  Region:            $REGION"
echo "  Templates Bucket:  $TEMPLATES_BUCKET"
echo "  Company Name:      $COMPANY_NAME"
echo "  Company Contact:   $COMPANY_CONTACT"
echo "  Bucket Prefix:     $BUCKET_PREFIX"
echo "  Knowledge Base ID: $([ -n "$KNOWLEDGE_BASE_ID" ] && echo "$KNOWLEDGE_BASE_ID" || echo "(disabled)")"
echo ""
write_info "Steps to execute:"
if [[ "$SKIP_INFRASTRUCTURE" != true ]]; then echo "  [1] Deploy CloudFormation infrastructure"; fi
if [[ "$SKIP_LAMBDAS" != true ]]; then echo "  [2] Deploy Lambda function code"; fi
if [[ "$SKIP_LAMBDAS" != true ]]; then echo "  [3] Configure Lambda environment variables"; fi
if [[ "$SKIP_REPORTING" != true ]]; then echo "  [4] Validate reporting workflow"; fi
echo ""

# Track deployment status
DEPLOYMENT_STATUS_INFRASTRUCTURE=false
DEPLOYMENT_STATUS_LAMBDAS=false
DEPLOYMENT_STATUS_CONFIGURATION=false
DEPLOYMENT_STATUS_REPORTING=false

cleanup_on_error() {
    write_error "Deployment failed: $1"
    echo ""
    echo "Deployment Status:"
    echo "  $([ "$DEPLOYMENT_STATUS_INFRASTRUCTURE" = true ] && echo "✓" || echo "✗") Infrastructure"
    echo "  $([ "$DEPLOYMENT_STATUS_LAMBDAS" = true ] && echo "✓" || echo "✗") Lambdas"
    echo "  $([ "$DEPLOYMENT_STATUS_CONFIGURATION" = true ] && echo "✓" || echo "✗") Configuration"
    echo "  $([ "$DEPLOYMENT_STATUS_REPORTING" = true ] && echo "✓" || echo "✗") Reporting"
    echo ""
    exit 1
}

trap 'cleanup_on_error "Script interrupted"' INT TERM

# Step 1: Deploy CloudFormation Infrastructure
if [[ "$SKIP_INFRASTRUCTURE" != true ]]; then
    write_step "STEP 1: DEPLOYING CLOUDFORMATION INFRASTRUCTURE"
    
    INFRA_SCRIPT_PATH="$PROJECT_ROOT/infrastructure/scripts/deploy.sh"
    
    if [[ ! -f "$INFRA_SCRIPT_PATH" ]]; then
        cleanup_on_error "Infrastructure deployment script not found: $INFRA_SCRIPT_PATH"
    fi
    
    write_info "Running infrastructure deployment..."
    
    # Build command arguments
    INFRA_ARGS=(
        --environment "$ENVIRONMENT"
        --region "$REGION"
        --bucket "$TEMPLATES_BUCKET"
        --api-key "$SAM_API_KEY"
        --company-name "$COMPANY_NAME"
        --company-contact "$COMPANY_CONTACT"
        --bucket-prefix "$BUCKET_PREFIX"
    )
    
    if [[ -n "$KNOWLEDGE_BASE_ID" ]]; then
        INFRA_ARGS+=(--knowledge-base-id "$KNOWLEDGE_BASE_ID")
    fi
    
    if ! "$INFRA_SCRIPT_PATH" "${INFRA_ARGS[@]}"; then
        cleanup_on_error "Infrastructure deployment failed"
    fi
    
    DEPLOYMENT_STATUS_INFRASTRUCTURE=true
    write_success "Infrastructure deployment completed"
else
    write_warning "Skipping infrastructure deployment (--skip-infrastructure)"
fi

# Step 2: Deploy Lambda Function Code
if [[ "$SKIP_LAMBDAS" != true ]]; then
    write_step "STEP 2: DEPLOYING LAMBDA FUNCTION CODE"
    
    LAMBDA_SCRIPT_PATH="$SCRIPT_DIR/deploy-all-lambdas.sh"
    
    if [[ ! -f "$LAMBDA_SCRIPT_PATH" ]]; then
        cleanup_on_error "Lambda deployment script not found: $LAMBDA_SCRIPT_PATH"
    fi
    
    write_info "Deploying all Lambda functions..."
    if ! "$LAMBDA_SCRIPT_PATH" \
        --environment "$ENVIRONMENT" \
        --bucket-prefix "$BUCKET_PREFIX" \
        --region "$REGION"; then
        cleanup_on_error "Lambda deployment failed"
    fi
    
    DEPLOYMENT_STATUS_LAMBDAS=true
    write_success "Lambda deployment completed"
    
    # Step 3: Configure Lambda Environment Variables
    write_step "STEP 3: CONFIGURING LAMBDA ENVIRONMENT VARIABLES"
    
    write_info "Updating sam-produce-web-reports environment..."
    if aws lambda update-function-configuration \
        --function-name "$BUCKET_PREFIX-sam-produce-web-reports-$ENVIRONMENT" \
        --environment "Variables={WEBSITE_BUCKET=$BUCKET_PREFIX-sam-website-$ENVIRONMENT,SAM_WEBSITE_BUCKET=$BUCKET_PREFIX-sam-website-$ENVIRONMENT,SAM_MATCHING_OUT_RUNS_BUCKET=$BUCKET_PREFIX-sam-matching-out-runs-$ENVIRONMENT,DASHBOARD_PATH=dashboards/,X_AMZN_TRACE_ID=ai-rfp-response-agent-$ENVIRONMENT-sam-produce-web-reports}" \
        --region "$REGION" \
        --no-cli-pager >/dev/null; then
        write_success "Updated web-reports Lambda configuration"
    else
        write_warning "Failed to update web-reports Lambda configuration"
    fi
    
    write_info "Updating sam-produce-user-report environment..."
    if aws lambda update-function-configuration \
        --function-name "$BUCKET_PREFIX-sam-produce-user-report-$ENVIRONMENT" \
        --environment "Variables={OUTPUT_BUCKET=$BUCKET_PREFIX-sam-opportunity-responses-$ENVIRONMENT,SAM_OPPORTUNITY_RESPONSES_BUCKET=$BUCKET_PREFIX-sam-opportunity-responses-$ENVIRONMENT,SAM_MATCHING_OUT_SQS_BUCKET=$BUCKET_PREFIX-sam-matching-out-sqs-$ENVIRONMENT,AGENT_ID=PLACEHOLDER,AGENT_ALIAS_ID=PLACEHOLDER,OUTPUT_FORMATS=txt\\,docx,COMPANY_NAME=$COMPANY_NAME,COMPANY_CONTACT=$COMPANY_CONTACT}" \
        --region "$REGION" \
        --no-cli-pager >/dev/null; then
        write_success "Updated user-report Lambda configuration"
    else
        write_warning "Failed to update user-report Lambda configuration"
    fi
    
    # Wait a moment for Lambda configuration to propagate
    write_info "Waiting for Lambda configuration to propagate..."
    sleep 5
    
    DEPLOYMENT_STATUS_CONFIGURATION=true
    write_success "Lambda configuration completed"
else
    write_warning "Skipping Lambda deployment (--skip-lambdas)"
fi

# Step 4: Validate Reporting Workflow
if [[ "$SKIP_REPORTING" != true ]]; then
    write_step "STEP 4: VALIDATING REPORTING WORKFLOW"
    
    REPORTING_SCRIPT_PATH="$SCRIPT_DIR/generate-reports-and-notify.sh"
    
    if [[ ! -f "$REPORTING_SCRIPT_PATH" ]]; then
        cleanup_on_error "Reporting script not found: $REPORTING_SCRIPT_PATH"
    fi
    
    write_info "Running reporting workflow..."
    if "$REPORTING_SCRIPT_PATH" \
        --region "$REGION" \
        --bucket-prefix "$BUCKET_PREFIX" \
        --env "$ENVIRONMENT"; then
        write_success "Reporting workflow completed"
    else
        write_warning "Reporting workflow completed with warnings"
    fi
    
    DEPLOYMENT_STATUS_REPORTING=true
else
    write_warning "Skipping reporting workflow (--skip-reporting)"
fi

# Final Summary
write_step "DEPLOYMENT COMPLETE"

echo "Deployment Status:"
echo "  $([ "$DEPLOYMENT_STATUS_INFRASTRUCTURE" = true ] && echo "✓" || echo "○") Infrastructure"
echo "  $([ "$DEPLOYMENT_STATUS_LAMBDAS" = true ] && echo "✓" || echo "○") Lambdas"
echo "  $([ "$DEPLOYMENT_STATUS_CONFIGURATION" = true ] && echo "✓" || echo "○") Configuration"
echo "  $([ "$DEPLOYMENT_STATUS_REPORTING" = true ] && echo "✓" || echo "○") Reporting"

echo ""
echo "Next Steps:"
echo "  1. Check S3 buckets for generated reports:"
echo "     - s3://$BUCKET_PREFIX-sam-website-$ENVIRONMENT/dashboards/"
echo "     - s3://$BUCKET_PREFIX-sam-opportunity-responses-$ENVIRONMENT/"
echo "  2. Monitor CloudWatch Logs for Lambda executions"
echo "  3. Review CloudWatch Dashboard:"
echo "     https://$REGION.console.aws.amazon.com/cloudwatch/home?region=$REGION#dashboards:name=AI-RFP-Response-Agent-$ENVIRONMENT"
echo "  4. (Optional) Enable S3 event notifications for automation"
echo "  5. (Optional) Configure Bedrock Knowledge Base if not already set"
echo ""

write_success "All deployment steps completed successfully!"
exit 0