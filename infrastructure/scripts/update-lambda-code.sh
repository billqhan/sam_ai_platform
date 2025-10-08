#!/bin/bash

# Update Lambda Function Code Script
# This script packages and updates Lambda function code with dependencies

set -e

# Default values
ENVIRONMENT="dev"
REGION="us-east-1"
TEMPLATES_BUCKET=""
BUCKET_PREFIX=""
LAMBDA_NAME="sam-gov-daily-download"
ALL_FUNCTIONS=false

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

Update Lambda Function Code with Dependencies

OPTIONS:
    -e, --environment ENV       Environment (dev, staging, prod) [default: dev]
    -r, --region REGION        AWS region [default: us-east-1]
    -b, --bucket BUCKET        Templates S3 bucket (required)
    -p, --prefix PREFIX        Bucket prefix [default: ""]
    -f, --function FUNCTION    Lambda function name [default: sam-gov-daily-download]
    -a, --all                  Update all functions
    -h, --help                 Show this help message

EXAMPLES:
    $0 -b my-templates-bucket -f sam-gov-daily-download
    $0 -b my-templates-bucket -p ktest -a
    $0 -b my-templates-bucket -e prod -f sam-json-processor

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
        -p|--prefix)
            BUCKET_PREFIX="$2"
            shift 2
            ;;
        -f|--function)
            LAMBDA_NAME="$2"
            shift 2
            ;;
        -a|--all)
            ALL_FUNCTIONS=true
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

# Validate required parameters
if [[ -z "$TEMPLATES_BUCKET" ]]; then
    print_error "Templates bucket is required. Use -b option."
    show_usage
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Define Lambda functions and their source paths
declare -A LAMBDA_FUNCTIONS=(
    ["sam-gov-daily-download"]="src/lambdas/sam-gov-daily-download"
    ["sam-json-processor"]="src/lambdas/sam-json-processor"
    ["sam-sqs-generate-match-reports"]="src/lambdas/sam-sqs-generate-match-reports"
    ["sam-produce-user-report"]="src/lambdas/sam-produce-user-report"
    ["sam-merge-and-archive-result-logs"]="src/lambdas/sam-merge-and-archive-result-logs"
    ["sam-produce-web-reports"]="src/lambdas/sam-produce-web-reports"
)

# Function to package a Lambda function
package_lambda_function() {
    local function_name=$1
    local source_path=$2
    local s3_bucket=$3
    local s3_key_prefix="lambda-packages"
    
    print_status "Packaging Lambda function: $function_name"
    echo "  Source Path: $source_path"
    echo "  S3 Bucket: $s3_bucket"
    echo "  S3 Key Prefix: $s3_key_prefix"
    
    # Create temporary directory for packaging
    local temp_dir=$(mktemp -d)
    local package_dir="$temp_dir/package"
    mkdir -p "$package_dir"
    
    # Copy source files to package directory
    print_status "Copying source files..."
    cp -r "$source_path"/* "$package_dir/"
    
    # Check if requirements.txt exists
    local requirements_file="$package_dir/requirements.txt"
    if [[ -f "$requirements_file" ]]; then
        print_status "Installing dependencies from requirements.txt..."
        
        # Install dependencies to package directory
        pip3 install -r "$requirements_file" -t "$package_dir" --platform linux_x86_64
        
        if [[ $? -ne 0 ]]; then
            print_error "Failed to install dependencies"
            rm -rf "$temp_dir"
            return 1
        fi
        
        # Remove unnecessary files
        find "$package_dir" -name "*.pyc" -delete
        find "$package_dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find "$package_dir" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
        find "$package_dir" -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
        rm -f "$requirements_file"
    else
        print_status "No requirements.txt found, packaging source only..."
    fi
    
    # Create ZIP file
    local zip_file="$temp_dir/$function_name.zip"
    print_status "Creating ZIP package..."
    
    cd "$package_dir"
    zip -r "$zip_file" . -q
    cd - > /dev/null
    
    # Upload to S3
    local s3_key="$s3_key_prefix/$function_name.zip"
    print_status "Uploading to S3: s3://$s3_bucket/$s3_key"
    
    aws s3 cp "$zip_file" "s3://$s3_bucket/$s3_key"
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to upload to S3"
        rm -rf "$temp_dir"
        return 1
    fi
    
    print_success "Lambda function packaged and uploaded successfully!"
    print_success "S3 Location: s3://$s3_bucket/$s3_key"
    
    # Clean up temporary directory
    rm -rf "$temp_dir"
    
    # Return S3 location
    echo "$s3_bucket|$s3_key"
}

# Function to update a Lambda function
update_lambda_function() {
    local function_name=$1
    local source_path=$2
    
    print_status "Processing Lambda function: $function_name"
    
    # Construct full function name with prefix and environment
    local full_function_name
    if [[ -n "$BUCKET_PREFIX" ]]; then
        full_function_name="$BUCKET_PREFIX-$function_name-$ENVIRONMENT"
    else
        full_function_name="$function_name-$ENVIRONMENT"
    fi
    
    # Check if function exists
    if ! aws lambda get-function --function-name "$full_function_name" --region "$REGION" &>/dev/null; then
        print_warning "Function $full_function_name not found, skipping..."
        return 0
    fi
    
    # Package the Lambda function
    local package_result
    package_result=$(package_lambda_function "$function_name" "$source_path" "$TEMPLATES_BUCKET")
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to package $function_name"
        return 1
    fi
    
    # Parse S3 location
    local s3_bucket=$(echo "$package_result" | cut -d'|' -f1)
    local s3_key=$(echo "$package_result" | cut -d'|' -f2)
    
    # Update Lambda function code
    print_status "Updating Lambda function code: $full_function_name"
    
    aws lambda update-function-code \
        --function-name "$full_function_name" \
        --s3-bucket "$s3_bucket" \
        --s3-key "$s3_key" \
        --region "$REGION"
    
    if [[ $? -eq 0 ]]; then
        print_success "Updated $full_function_name successfully!"
        
        # Wait for update to complete
        print_status "Waiting for function update to complete..."
        aws lambda wait function-updated --function-name "$full_function_name" --region "$REGION"
        
        if [[ $? -eq 0 ]]; then
            print_success "Function update completed!"
        else
            print_warning "Function update may still be in progress"
        fi
    else
        print_error "Failed to update $full_function_name"
        return 1
    fi
}

echo "=== Lambda Function Code Update ==="
echo "Environment: $ENVIRONMENT"
echo "Bucket Prefix: $BUCKET_PREFIX"
echo "Templates Bucket: $TEMPLATES_BUCKET"
echo ""

if [[ "$ALL_FUNCTIONS" == true ]]; then
    print_status "Updating all Lambda functions..."
    
    for function_name in "${!LAMBDA_FUNCTIONS[@]}"; do
        source_path="$PROJECT_ROOT/${LAMBDA_FUNCTIONS[$function_name]}"
        if [[ -d "$source_path" ]]; then
            update_lambda_function "$function_name" "$source_path"
            echo ""
        else
            print_warning "Source path not found: $source_path"
        fi
    done
else
    if [[ -n "${LAMBDA_FUNCTIONS[$LAMBDA_NAME]}" ]]; then
        source_path="$PROJECT_ROOT/${LAMBDA_FUNCTIONS[$LAMBDA_NAME]}"
        if [[ -d "$source_path" ]]; then
            update_lambda_function "$LAMBDA_NAME" "$source_path"
        else
            print_error "Source path not found: $source_path"
            exit 1
        fi
    else
        print_error "Unknown Lambda function: $LAMBDA_NAME"
        print_error "Available functions: ${!LAMBDA_FUNCTIONS[*]}"
        exit 1
    fi
fi

echo ""
print_success "Lambda function update process completed!"