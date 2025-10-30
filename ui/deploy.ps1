# Deploy Web UI Script
# This script builds and deploys the React web UI to S3

param(
    [string]$BucketName = "l3harris-qhan-rfp-ui-dev",
    [string]$Region = "us-east-1",
    [switch]$CreateBucket
)

$ErrorActionPreference = "Stop"

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          WEB UI DEPLOYMENT SCRIPT                     ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Create bucket if requested
if ($CreateBucket) {
    Write-Host "[1/4] Creating S3 bucket..." -ForegroundColor Yellow
    try {
        aws s3 mb "s3://$BucketName" --region $Region
        Write-Host "  ✅ Bucket created: $BucketName" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Bucket may already exist" -ForegroundColor Yellow
    }
    
    # Configure bucket for static website hosting
    Write-Host "  Configuring static website hosting..." -ForegroundColor Yellow
    aws s3 website "s3://$BucketName" --index-document index.html --error-document index.html
    
    # Set bucket policy for public read
    $policy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BucketName/*"
        }
    ]
}
"@
    $policy | Out-File -FilePath bucket-policy.json -Encoding ascii
    aws s3api put-bucket-policy --bucket $BucketName --policy file://bucket-policy.json
    Remove-Item bucket-policy.json
    Write-Host "  ✅ Website hosting configured" -ForegroundColor Green
    Write-Host ""
}

# Build React app
Write-Host "[2/4] Building React application..." -ForegroundColor Yellow
Set-Location ui
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Build completed" -ForegroundColor Green
Write-Host ""

# Upload to S3
Write-Host "[3/4] Uploading to S3..." -ForegroundColor Yellow
aws s3 sync dist/ "s3://$BucketName" --delete --region $Region
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Upload failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Upload completed" -ForegroundColor Green
Write-Host ""

# Get website URL
Write-Host "[4/4] Deployment complete!" -ForegroundColor Green
$websiteUrl = "http://$BucketName.s3-website-$Region.amazonaws.com"
Write-Host ""
Write-Host "  🌐 Website URL: $websiteUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Note: For production, configure CloudFront distribution" -ForegroundColor Yellow
Write-Host "  with custom domain and SSL certificate." -ForegroundColor Yellow
Write-Host ""

Set-Location ..
