#!/bin/bash

# Deploy All SAM Lambda Functions
# This script packages and deploys all lambda functions


# Require environment variables to be set (from .env.dev or shell)
if [ -f "../.env.dev" ]; then
    source ../.env.dev
fi

if [[ -z "$ENVIRONMENT" || -z "$BUCKET_PREFIX" || -z "$REGION" ]]; then
    echo "Error: ENVIRONMENT, BUCKET_PREFIX, and REGION must be set in .env.dev or environment."
    exit 1
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --bucket-prefix)
            BUCKET_PREFIX="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================"
echo "  DEPLOYING ALL LAMBDA FUNCTIONS"
echo "========================================"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Bucket Prefix: $BUCKET_PREFIX"
echo "Region: $REGION"
echo ""

# Define all Lambda functions
LAMBDA_FUNCTIONS=(
    "sam-gov-daily-download"
    "sam-json-processor"
    "sam-sqs-generate-match-reports"
    "sam-produce-user-report"
    "sam-merge-and-archive-result-logs"
    "sam-produce-web-reports"
    "sam-daily-email-notification"
)

SOURCE_ROOT="../src/lambdas"
SHARED_DIR="../src/shared"
TEMP_ROOT="temp"

# Create temp directory
mkdir -p "$TEMP_ROOT"

SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_FUNCTIONS=()

for FUNCTION_NAME in "${LAMBDA_FUNCTIONS[@]}"; do
    LAMBDA_FULL_NAME="${ENVIRONMENT}-${FUNCTION_NAME}-${ENVIRONMENT}"
    SOURCE_DIR="${SOURCE_ROOT}/${FUNCTION_NAME}"
    TEMP_DIR="${TEMP_ROOT}/lambda_package_${FUNCTION_NAME}"
    ZIP_FILE="${TEMP_ROOT}/${FUNCTION_NAME}.zip"
    
    echo ""
    echo "-------------------------------------------------"
    echo "Deploying: $FUNCTION_NAME"
    echo "-------------------------------------------------"
    
    # Check if source directory exists
    if [[ ! -d "$SOURCE_DIR" ]]; then
        echo "    Source directory not found: $SOURCE_DIR"
        ((FAIL_COUNT++))
        FAILED_FUNCTIONS+=("$FUNCTION_NAME")
        continue
    fi
    
    # Clean up previous builds
    rm -rf "$TEMP_DIR" 2>/dev/null
    rm -f "$ZIP_FILE" 2>/dev/null
    
    # Create temp directory
    mkdir -p "$TEMP_DIR"
    
    echo "   Copying source files..."
    
    # Copy lambda function files
    cp -r "$SOURCE_DIR"/* "$TEMP_DIR/"
    
    # Copy shared utilities if they exist
    if [[ -d "$SHARED_DIR" ]]; then
        SHARED_DEST_DIR="${TEMP_DIR}/shared"
        mkdir -p "$SHARED_DEST_DIR"
        cp -r "$SHARED_DIR"/* "$SHARED_DEST_DIR/"
    fi
    
    # Check if lambda_function.py exists, if not check for handler.py
    LAMBDA_FUNCTION_PATH="${TEMP_DIR}/lambda_function.py"
    HANDLER_PATH="${TEMP_DIR}/handler.py"
    
    if [[ ! -f "$LAMBDA_FUNCTION_PATH" && -f "$HANDLER_PATH" ]]; then
        # Create lambda_function.py that imports from handler
        cat > "$LAMBDA_FUNCTION_PATH" << EOF
"""
Lambda function entry point for $FUNCTION_NAME.
"""
from handler import lambda_handler

__all__ = ['lambda_handler']
EOF
        echo "   Created lambda_function.py wrapper"
    fi
    
    # Install dependencies if requirements.txt exists
    REQUIREMENTS_PATH="${TEMP_DIR}/requirements.txt"
    if [[ -f "$REQUIREMENTS_PATH" ]]; then
        echo "   Installing dependencies..."
        python3 -m pip install -r "$REQUIREMENTS_PATH" -t "$TEMP_DIR" --quiet --no-color
        
        if [[ $? -ne 0 ]]; then
            echo "    Warning: Some dependencies may have failed to install"
        else
            echo "   Dependencies installed"
        fi
    fi
    
    # Create ZIP file
    echo "   Creating deployment package..."
    
    # Use zip command
    cd "$TEMP_DIR"
    zip -r "../${FUNCTION_NAME}.zip" . > /dev/null 2>&1
    cd - > /dev/null
    
    if [[ -f "$ZIP_FILE" ]]; then
        echo "   Package created: $ZIP_FILE"
        
        # Upload to S3 first (more reliable for large packages)
        S3_CODE_BUCKET="${TEMPLATES_BUCKET:-ai-rfp-templates-dev}"
        S3_CODE_KEY="lambda/${FUNCTION_NAME}.zip"
        
        echo "    Uploading to S3: s3://${S3_CODE_BUCKET}/${S3_CODE_KEY}"
        aws s3 cp "$ZIP_FILE" "s3://${S3_CODE_BUCKET}/${S3_CODE_KEY}" --region "$REGION" --quiet
        
        if [[ $? -ne 0 ]]; then
            echo "   Failed to upload to S3: $FUNCTION_NAME"
            ((FAIL_COUNT++))
            FAILED_FUNCTIONS+=("$FUNCTION_NAME")
            continue
        fi
        
        # Update Lambda function from S3
        echo "    Updating Lambda function from S3..."
        
        UPDATE_RESULT=$(aws lambda update-function-code \
            --function-name "$LAMBDA_FULL_NAME" \
            --s3-bucket "$S3_CODE_BUCKET" \
            --s3-key "$S3_CODE_KEY" \
            --region "$REGION" \
            --query '{FunctionName:FunctionName,LastModified:LastModified,CodeSize:CodeSize}' \
            --output json 2>&1)
        
        if [[ $? -eq 0 ]]; then
            echo "   Successfully deployed: $FUNCTION_NAME"
            ((SUCCESS_COUNT++))
            
            # Parse and display update info
            FUNCTION_SIZE=$(echo "$UPDATE_RESULT" | jq -r '.CodeSize' 2>/dev/null)
            LAST_MODIFIED=$(echo "$UPDATE_RESULT" | jq -r '.LastModified' 2>/dev/null)
            
            if [[ "$FUNCTION_SIZE" != "null" && -n "$FUNCTION_SIZE" ]]; then
                echo "     Size: $FUNCTION_SIZE bytes"
            fi
            if [[ "$LAST_MODIFIED" != "null" && -n "$LAST_MODIFIED" ]]; then
                echo "     Modified: $LAST_MODIFIED"
            fi
        else
            echo "   Failed to deploy: $FUNCTION_NAME"
            echo "     Error: $UPDATE_RESULT"
            ((FAIL_COUNT++))
            FAILED_FUNCTIONS+=("$FUNCTION_NAME")
        fi
    else
        echo "   Failed to create package for: $FUNCTION_NAME"
        ((FAIL_COUNT++))
        FAILED_FUNCTIONS+=("$FUNCTION_NAME")
    fi
done

# Summary
echo ""
echo "========================================"
echo "  DEPLOYMENT SUMMARY"
echo "========================================"
echo "Total Functions: ${#LAMBDA_FUNCTIONS[@]}"
echo " Successful: $SUCCESS_COUNT"
echo " Failed: $FAIL_COUNT"

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo ""
    echo "Failed Functions:"
    for FAILED in "${FAILED_FUNCTIONS[@]}"; do
        echo "  - $FAILED"
    done
fi

# Clean up temp directory
echo ""
echo "Cleaning up temporary files..."
rm -rf "$TEMP_ROOT"

echo ""
echo "Deployment process completed!"
echo ""

exit $FAIL_COUNT