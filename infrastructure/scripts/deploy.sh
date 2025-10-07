#!/bin/bash

# Deployment script for AI RFP Response Agent
# Usage: ./deploy.sh [environment] [sam-api-key]

set -e

ENVIRONMENT=${1:-dev}
SAM_API_KEY=${2}

if [ -z "$SAM_API_KEY" ]; then
    echo "Error: SAM API key is required"
    echo "Usage: ./deploy.sh [environment] [sam-api-key]"
    exit 1
fi

echo "Deploying AI RFP Response Agent to environment: $ENVIRONMENT"

# Package Lambda functions
echo "Packaging Lambda functions..."
cd ../..

# Create deployment package for each Lambda function
LAMBDA_FUNCTIONS=(
    "sam-gov-daily-download"
    "sam-json-processor"
    "sam-sqs-generate-match-reports"
    "sam-produce-user-report"
    "sam-merge-and-archive-result-logs"
    "sam-produce-web-reports"
)

for func in "${LAMBDA_FUNCTIONS[@]}"; do
    echo "Packaging $func..."
    cd "src/lambdas/$func"
    
    # Create deployment directory
    mkdir -p ../../../build/$func
    
    # Copy source files
    cp -r . ../../../build/$func/
    
    # Copy shared libraries
    cp -r ../../shared ../../../build/$func/
    
    # Install dependencies
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt -t ../../../build/$func/
    fi
    
    cd ../../..
done

echo "Packaging complete"

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
cd infrastructure/cloudformation

aws cloudformation deploy \
    --template-file template.yaml \
    --stack-name "ai-rfp-response-agent-$ENVIRONMENT" \
    --parameter-overrides \
        Environment=$ENVIRONMENT \
        SAMAPIKey=$SAM_API_KEY \
    --capabilities CAPABILITY_IAM \
    --region us-east-1

echo "Deployment complete!"