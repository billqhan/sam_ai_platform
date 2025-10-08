#!/bin/bash

# AI-powered RFP Response Agent - Lambda Package Management Script
# This script packages Lambda functions with their dependencies

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src"
BUILD_DIR="$PROJECT_ROOT/build"
LAMBDAS_DIR="$SRC_DIR/lambdas"

# Default values
FUNCTION_NAME=""
ENVIRONMENT="dev"
UPLOAD_TO_S3=false
S3_BUCKET=""
CLEAN_BUILD=false

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

Package Lambda functions with their dependencies

OPTIONS:
    -f, --function FUNCTION_NAME    Specific function to package (optional, packages all if not specified)
    -e, --environment ENVIRONMENT   Environment name (dev, staging, prod) [default: dev]
    -s, --s3-bucket BUCKET         Upload packages to S3 bucket (optional)
    -c, --clean                    Clean build directory before packaging
    -h, --help                     Show this help message

EXAMPLES:
    $0                                          # Package all functions
    $0 -f sam-gov-daily-download               # Package specific function
    $0 -s my-lambda-packages-bucket            # Package and upload to S3
    $0 -c -f sam-json-processor                # Clean build and package specific function

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--function)
            FUNCTION_NAME="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--s3-bucket)
            S3_BUCKET="$2"
            UPLOAD_TO_S3=true
            shift 2
            ;;
        -c|--clean)
            CLEAN_BUILD=true
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

print_status "Lambda packaging configuration:"
echo "  Function: ${FUNCTION_NAME:-'All functions'}"
echo "  Environment: $ENVIRONMENT"
echo "  Upload to S3: $UPLOAD_TO_S3"
if [[ "$UPLOAD_TO_S3" == true ]]; then
    echo "  S3 Bucket: $S3_BUCKET"
fi
echo "  Clean build: $CLEAN_BUILD"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install it first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed. Please install it first."
    exit 1
fi

# Check if zip is installed
if ! command -v zip &> /dev/null; then
    print_error "zip is not installed. Please install it first."
    exit 1
fi

# Clean build directory if requested
if [[ "$CLEAN_BUILD" == true ]]; then
    print_status "Cleaning build directory..."
    rm -rf "$BUILD_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"

# Function to package a single Lambda function
package_function() {
    local func_name=$1
    local func_dir="$LAMBDAS_DIR/$func_name"
    local build_func_dir="$BUILD_DIR/$func_name"
    local zip_file="$BUILD_DIR/${func_name}.zip"
    
    print_status "Packaging function: $func_name"
    
    # Check if function directory exists
    if [[ ! -d "$func_dir" ]]; then
        print_error "Function directory not found: $func_dir"
        return 1
    fi
    
    # Create function build directory
    rm -rf "$build_func_dir"
    mkdir -p "$build_func_dir"
    
    # Copy function code
    cp -r "$func_dir"/* "$build_func_dir/"
    
    # Check if requirements.txt exists
    if [[ -f "$func_dir/requirements.txt" ]]; then
        print_status "Installing dependencies for $func_name..."
        
        # Install dependencies to build directory (Linux x86_64 compatible for Lambda)
        pip3 install -r "$func_dir/requirements.txt" -t "$build_func_dir" --no-cache-dir --platform linux_x86_64
        
        if [[ $? -ne 0 ]]; then
            print_error "Failed to install dependencies for $func_name"
            return 1
        fi
    else
        print_warning "No requirements.txt found for $func_name"
    fi
    
    # Copy shared libraries if they exist
    local shared_dir="$SRC_DIR/shared"
    if [[ -d "$shared_dir" ]]; then
        print_status "Copying shared libraries for $func_name..."
        cp -r "$shared_dir"/* "$build_func_dir/"
    fi
    
    # Remove unnecessary files
    find "$build_func_dir" -name "*.pyc" -delete
    find "$build_func_dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$build_func_dir" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$build_func_dir" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Create zip file
    print_status "Creating zip file for $func_name..."
    cd "$build_func_dir"
    zip -r "$zip_file" . -q
    cd - > /dev/null
    
    if [[ $? -eq 0 ]]; then
        local zip_size=$(du -h "$zip_file" | cut -f1)
        print_success "Package created: ${func_name}.zip ($zip_size)"
        
        # Upload to S3 if requested
        if [[ "$UPLOAD_TO_S3" == true ]]; then
            print_status "Uploading $func_name to S3..."
            aws s3 cp "$zip_file" "s3://$S3_BUCKET/lambda-packages/$ENVIRONMENT/${func_name}.zip"
            
            if [[ $? -eq 0 ]]; then
                print_success "Uploaded to S3: s3://$S3_BUCKET/lambda-packages/$ENVIRONMENT/${func_name}.zip"
            else
                print_error "Failed to upload $func_name to S3"
                return 1
            fi
        fi
    else
        print_error "Failed to create zip file for $func_name"
        return 1
    fi
    
    return 0
}

# Get list of Lambda functions
if [[ -n "$FUNCTION_NAME" ]]; then
    # Package specific function
    FUNCTIONS=("$FUNCTION_NAME")
else
    # Package all functions
    if [[ ! -d "$LAMBDAS_DIR" ]]; then
        print_error "Lambda functions directory not found: $LAMBDAS_DIR"
        exit 1
    fi
    
    FUNCTIONS=()
    for func_dir in "$LAMBDAS_DIR"/*; do
        if [[ -d "$func_dir" ]]; then
            func_name=$(basename "$func_dir")
            FUNCTIONS+=("$func_name")
        fi
    done
    
    if [[ ${#FUNCTIONS[@]} -eq 0 ]]; then
        print_error "No Lambda functions found in $LAMBDAS_DIR"
        exit 1
    fi
fi

print_status "Found ${#FUNCTIONS[@]} function(s) to package: ${FUNCTIONS[*]}"
echo ""

# Check S3 bucket if upload is requested
if [[ "$UPLOAD_TO_S3" == true ]]; then
    if [[ -z "$S3_BUCKET" ]]; then
        print_error "S3 bucket name is required when using -s option"
        exit 1
    fi
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if bucket exists
    if ! aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
        print_error "S3 bucket '$S3_BUCKET' does not exist or is not accessible."
        exit 1
    fi
fi

# Package functions
FAILED_FUNCTIONS=()
SUCCESSFUL_FUNCTIONS=()

for func_name in "${FUNCTIONS[@]}"; do
    if package_function "$func_name"; then
        SUCCESSFUL_FUNCTIONS+=("$func_name")
    else
        FAILED_FUNCTIONS+=("$func_name")
    fi
    echo ""
done

# Summary
print_status "Packaging Summary:"
echo "  Successful: ${#SUCCESSFUL_FUNCTIONS[@]} (${SUCCESSFUL_FUNCTIONS[*]})"
echo "  Failed: ${#FAILED_FUNCTIONS[@]} (${FAILED_FUNCTIONS[*]})"
echo "  Build directory: $BUILD_DIR"

if [[ ${#FAILED_FUNCTIONS[@]} -gt 0 ]]; then
    print_error "Some functions failed to package. Check the logs above for details."
    exit 1
else
    print_success "All functions packaged successfully!"
fi

# Update Lambda functions if requested
if [[ "$UPLOAD_TO_S3" == true ]]; then
    print_status "Lambda packages are available in S3 at: s3://$S3_BUCKET/lambda-packages/$ENVIRONMENT/"
    print_status "You can now update your Lambda functions using the AWS CLI or CloudFormation."
fi

print_success "Lambda packaging completed!"