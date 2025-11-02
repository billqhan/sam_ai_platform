#!/bin/bash

# Complete End-to-End Workflow Runner
# This script executes the entire RFP response pipeline

set -e  # Exit on error

# Default parameters
OPPORTUNITIES_TO_PROCESS=10
SKIP_DOWNLOAD=false
WAIT_FOR_COMPLETION=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --opportunities)
            OPPORTUNITIES_TO_PROCESS="$2"
            shift 2
            ;;
        --skip-download)
            SKIP_DOWNLOAD=true
            shift
            ;;
        --wait)
            WAIT_FOR_COMPLETION=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--opportunities N] [--skip-download] [--wait] [--help]"
            echo "  --opportunities N   Number of opportunities to process (default: 10)"
            echo "  --skip-download     Skip the SAM.gov download step"
            echo "  --wait             Wait for completion of each step"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║   AI-POWERED RFP RESPONSE AGENT - FULL WORKFLOW      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Download from SAM.gov
if [ "$SKIP_DOWNLOAD" = false ]; then
    echo "[1/5] Downloading opportunities from SAM.gov..."
    aws lambda invoke \
        --function-name l3harris-qhan-sam-gov-daily-download-dev \
        --region us-east-1 \
        download-response.json > /dev/null
    
    if [ -f download-response.json ]; then
        download_status=$(jq -r '.statusCode' download-response.json 2>/dev/null || echo "error")
        if [ "$download_status" = "200" ]; then
            opportunities_count=$(jq -r '.body | fromjson | .opportunitiesCount' download-response.json 2>/dev/null || echo "unknown")
            s3_key=$(jq -r '.body | fromjson | .s3ObjectKey' download-response.json 2>/dev/null || echo "unknown")
            echo "  ✅ Downloaded: $opportunities_count opportunities"
            echo "  📄 File: $s3_key"
        else
            echo "  ❌ Download failed with status: $download_status"
            exit 1
        fi
        rm -f download-response.json
    else
        echo "  ❌ Download response file not created"
        exit 1
    fi
else
    echo "[1/5] Skipping SAM.gov download..."
fi

# Step 2: Process opportunities
echo ""
echo "[2/5] Processing opportunities..."
aws lambda invoke \
    --function-name l3harris-qhan-sam-json-processor-dev \
    --region us-east-1 \
    parser-response.json > /dev/null

if [ -f parser-response.json ]; then
    parser_status=$(jq -r '.statusCode' parser-response.json 2>/dev/null || echo "error")
    if [ "$parser_status" = "200" ]; then
        processed_count=$(jq -r '.body | fromjson | .processedCount' parser-response.json 2>/dev/null || echo "unknown")
        echo "  ✅ Processed: $processed_count opportunities"
    else
        echo "  ❌ Processing failed with status: $parser_status"
        exit 1
    fi
    rm -f parser-response.json
else
    echo "  ❌ Parser response file not created"
    exit 1
fi

# Step 3: Generate matches
echo ""
echo "[3/5] Generating AI matches..."
aws lambda invoke \
    --function-name l3harris-qhan-sam-sqs-generate-match-reports-dev \
    --region us-east-1 \
    matching-response.json > /dev/null

if [ -f matching-response.json ]; then
    matching_status=$(jq -r '.statusCode' matching-response.json 2>/dev/null || echo "error")
    if [ "$matching_status" = "200" ]; then
        matches_count=$(jq -r '.body | fromjson | .matchesGenerated' matching-response.json 2>/dev/null || echo "unknown")
        echo "  ✅ Generated: $matches_count matches"
    else
        echo "  ❌ Matching failed with status: $matching_status"
        exit 1
    fi
    rm -f matching-response.json
else
    echo "  ❌ Matching response file not created"
    exit 1
fi

# Step 4: Generate reports
echo ""
echo "[4/5] Generating reports..."
aws lambda invoke \
    --function-name l3harris-qhan-sam-produce-web-reports-dev \
    --region us-east-1 \
    reports-response.json > /dev/null

if [ -f reports-response.json ]; then
    reports_status=$(jq -r '.statusCode' reports-response.json 2>/dev/null || echo "error")
    if [ "$reports_status" = "200" ]; then
        reports_count=$(jq -r '.body | fromjson | .reportsGenerated' reports-response.json 2>/dev/null || echo "unknown")
        echo "  ✅ Generated: $reports_count reports"
    else
        echo "  ❌ Report generation failed with status: $reports_status"
        exit 1
    fi
    rm -f reports-response.json
else
    echo "  ❌ Reports response file not created"
    exit 1
fi

# Step 5: Send email notification
echo ""
echo "[5/5] Sending email notification..."
aws lambda invoke \
    --function-name l3harris-qhan-sam-daily-email-notification-dev \
    --region us-east-1 \
    email-response.json > /dev/null

if [ -f email-response.json ]; then
    email_status=$(jq -r '.statusCode' email-response.json 2>/dev/null || echo "error")
    if [ "$email_status" = "200" ]; then
        echo "  ✅ Email notification sent successfully"
    else
        echo "  ❌ Email notification failed with status: $email_status"
        exit 1
    fi
    rm -f email-response.json
else
    echo "  ❌ Email response file not created"
    exit 1
fi

# Completion
echo ""
echo "🎉 WORKFLOW COMPLETED SUCCESSFULLY!"
echo ""
echo "📊 Summary:"
echo "  • Opportunities downloaded from SAM.gov"
echo "  • $OPPORTUNITIES_TO_PROCESS opportunities processed"
echo "  • AI matches generated"
echo "  • Reports created and published"
echo "  • Email notifications sent"
echo ""
echo "🌐 View results at: http://localhost:3000"
echo "📧 Check your email for the daily summary"
echo ""