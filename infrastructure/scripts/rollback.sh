#!/bin/bash

# AI-powered RFP Response Agent - Rollback Script
# This script rolls back the CloudFormation stack to a previous version

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME_PREFIX="ai-rfp-response-agent"

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

Rollback the AI-powered RFP Response Agent infrastructure

OPTIONS:
    -e, --environment ENVIRONMENT    Environment name (dev, staging, prod) [default: dev]
    -r, --region REGION             AWS region [default: us-east-1]
    -s, --stack-name STACK_NAME     Custom stack name prefix [default: ai-rfp-response-agent]
    -l, --list                      List available stack events and versions
    -f, --force                     Force rollback without confirmation
    -h, --help                      Show this help message

EXAMPLES:
    $0 -e dev                       # Rollback dev environment
    $0 --environment prod --force   # Force rollback prod environment
    $0 -l                          # List stack events

EOF
}

# Parse command line arguments
LIST_ONLY=false
FORCE_ROLLBACK=false

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
        -s|--stack-name)
            STACK_NAME_PREFIX="$2"
            shift 2
            ;;
        -l|--list)
            LIST_ONLY=true
            shift
            ;;
        -f|--force)
            FORCE_ROLLBACK=true
            shift
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

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

# Set stack name
STACK_NAME="${STACK_NAME_PREFIX}-${ENVIRONMENT}"

print_status "Rollback configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $REGION"
echo "  Stack Name: $STACK_NAME"
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

# Check if stack exists
print_status "Checking if stack exists..."
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
    print_error "Stack '$STACK_NAME' does not exist in region '$REGION'"
    exit 1
fi

# Get stack status
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text)

print_status "Current stack status: $STACK_STATUS"

# List stack events if requested
if [[ "$LIST_ONLY" == true ]]; then
    print_status "Recent stack events:"
    aws cloudformation describe-stack-events \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackEvents[0:20].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
        --output table
    
    print_status "Stack change sets (if any):"
    aws cloudformation list-change-sets \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --output table 2>/dev/null || print_warning "No change sets found"
    
    exit 0
fi

# Check if rollback is possible
case "$STACK_STATUS" in
    "UPDATE_FAILED"|"UPDATE_ROLLBACK_FAILED"|"CREATE_FAILED")
        print_status "Stack is in a failed state. Rollback is possible."
        ;;
    "UPDATE_COMPLETE"|"CREATE_COMPLETE")
        print_warning "Stack is in a stable state. Consider using continue-update-rollback if there was a previous failed update."
        if [[ "$FORCE_ROLLBACK" != true ]]; then
            read -p "Do you want to continue with rollback? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_status "Rollback cancelled."
                exit 0
            fi
        fi
        ;;
    "UPDATE_IN_PROGRESS"|"UPDATE_ROLLBACK_IN_PROGRESS"|"DELETE_IN_PROGRESS")
        print_error "Stack is currently being updated. Please wait for the operation to complete."
        exit 1
        ;;
    *)
        print_warning "Stack status '$STACK_STATUS' may not support rollback."
        if [[ "$FORCE_ROLLBACK" != true ]]; then
            read -p "Do you want to attempt rollback anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_status "Rollback cancelled."
                exit 0
            fi
        fi
        ;;
esac

# Show recent stack events before rollback
print_status "Recent stack events before rollback:"
aws cloudformation describe-stack-events \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
    --output table

# Confirm rollback unless forced
if [[ "$FORCE_ROLLBACK" != true ]]; then
    echo ""
    print_warning "This will rollback the stack '$STACK_NAME' to its previous stable state."
    print_warning "This action cannot be undone!"
    echo ""
    read -p "Are you sure you want to proceed? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Rollback cancelled."
        exit 0
    fi
fi

# Attempt to continue update rollback first (for failed updates)
if [[ "$STACK_STATUS" == "UPDATE_ROLLBACK_FAILED" ]]; then
    print_status "Attempting to continue update rollback..."
    
    aws cloudformation continue-update-rollback \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [[ $? -eq 0 ]]; then
        print_status "Continue update rollback initiated. Waiting for completion..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            print_success "Stack rollback completed successfully!"
        else
            print_error "Stack rollback failed!"
            exit 1
        fi
    else
        print_error "Failed to initiate continue update rollback"
        exit 1
    fi
elif [[ "$STACK_STATUS" == "UPDATE_FAILED" ]]; then
    print_status "Attempting to cancel update and rollback..."
    
    # Try to cancel the update first
    aws cloudformation cancel-update-stack \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null || true
    
    # Wait a moment and then continue with rollback
    sleep 5
    
    aws cloudformation continue-update-rollback \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [[ $? -eq 0 ]]; then
        print_status "Update rollback initiated. Waiting for completion..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            print_success "Stack rollback completed successfully!"
        else
            print_error "Stack rollback failed!"
            exit 1
        fi
    else
        print_error "Failed to initiate update rollback"
        exit 1
    fi
else
    print_warning "Stack is not in a failed update state. Manual intervention may be required."
    print_status "Consider using AWS Console for more advanced rollback options."
fi

# Show final stack status
FINAL_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text)

print_status "Final stack status: $FINAL_STATUS"

# Show recent events after rollback
print_status "Recent stack events after rollback:"
aws cloudformation describe-stack-events \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
    --output table

print_success "Rollback operation completed!"
print_status "Please verify that all services are functioning correctly."