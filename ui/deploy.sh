#!/bin/bash

# Deploy Web UI Script - Bash Version
# This script builds and deploys the React web UI to S3

# Load environment configuration from project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env.dev" ]; then
    source "$SCRIPT_DIR/../.env.dev"
fi

BUCKET_NAME="${1:-${UI_BUCKET:-${BUCKET_PREFIX:+${BUCKET_PREFIX}-}rfp-ui-${ENVIRONMENT:-dev}}}"
REGION="${2:-${REGION:-us-east-1}}"
CREATE_BUCKET="${3:-false}"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║          WEB UI DEPLOYMENT SCRIPT                     ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if bucket exists
echo "[1/4] Checking S3 bucket..."
if aws s3 ls "s3://$BUCKET_NAME" --region $REGION >/dev/null 2>&1; then
    echo "  ✅ Bucket exists: $BUCKET_NAME"
else
    echo "  Creating S3 bucket: $BUCKET_NAME"
    aws s3 mb "s3://$BUCKET_NAME" --region $REGION
    
    # Configure bucket for static website hosting
    echo "  Configuring static website hosting..."
    aws s3 website "s3://$BUCKET_NAME" --index-document index.html --error-document index.html
    
    # Set bucket policy for public read
    cat > bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF
    aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://bucket-policy.json
    rm -f bucket-policy.json
    echo "  ✅ Website hosting configured"
fi

# Install dependencies
echo ""
echo "[2/4] Installing dependencies..."
npm install
echo "  ✅ Dependencies installed"

# Build the project
echo ""
echo "[3/4] Building React application..."
npm run build
echo "  ✅ Build completed"

# Deploy to S3
echo ""
echo "[4/4] Deploying to S3..."
aws s3 sync dist/ "s3://$BUCKET_NAME" --delete --region $REGION
echo "  ✅ Deployment completed"

# Get website URL
WEBSITE_URL="http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
echo ""
echo "🎉 Deployment Successful!"
echo "   UI URL: $WEBSITE_URL"
echo ""