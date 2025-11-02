#!/bin/bash

# Update SAM.gov API Key for Lambda Function
# Usage: ./update-sam-api-key.sh YOUR_ACTUAL_API_KEY

if [ $# -eq 0 ]; then
    echo "Usage: $0 YOUR_SAM_API_KEY"
    echo "Example: $0 abcd1234-5678-9012-3456-789012345678"
    exit 1
fi

API_KEY=$1

echo "Updating SAM.gov API key for Lambda function..."

aws lambda update-function-configuration \
    --function-name l3harris-qhan-sam-gov-daily-download-dev \
    --environment Variables="{
        \"SAM_API_KEY\": \"$API_KEY\",
        \"SAM_API_URL\": \"https://api.sam.gov/prod/opportunities/v2/search\",
        \"OVERRIDE_DATE_FORMAT\": \"MM/DD/YYYY\",
        \"API_LIMIT\": \"1000\",
        \"OVERRIDE_POSTED_FROM\": \"\",
        \"LOG_BUCKET\": \"l3harris-qhan-sam-download-files-logs-dev\",
        \"OUTPUT_BUCKET\": \"l3harris-qhan-sam-data-in-dev\",
        \"X_AMZN_TRACE_ID\": \"ai-rfp-response-agent-dev-LambdaFunctionsStack-HXB3E9R3R6IY-sam-gov-daily-download\",
        \"OVERRIDE_POSTED_TO\": \"\"
    }" \
    --region us-east-1

echo "✅ SAM.gov API key updated successfully!"
echo "You can now test the full workflow."