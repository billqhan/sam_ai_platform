<#
.SYNOPSIS
    Deploy Contract Intelligence Platform UI to S3 + CloudFront

.DESCRIPTION
    This script:
    1. Builds the React UI for production
    2. Deploys S3 + CloudFront infrastructure via CloudFormation
    3. Uploads built files to S3
    4. Invalidates CloudFront cache
    5. Displays the website URL

.PARAMETER Environment
    Deployment environment (dev, staging, prod). Default: dev

.PARAMETER SkipBuild
    Skip the npm build step (use existing build)

.PARAMETER SkipInfrastructure
    Skip CloudFormation deployment (infrastructure already exists)

.EXAMPLE
    .\deploy-ui.ps1
    
.EXAMPLE
    .\deploy-ui.ps1 -Environment prod
    
.EXAMPLE
    .\deploy-ui.ps1 -SkipBuild
#>

param(
    [string]$Environment = "dev",
    [switch]$SkipBuild,
    [switch]$SkipInfrastructure
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectPrefix = "l3harris-qhan"
$StackName = "$ProjectPrefix-ui-hosting-$Environment"
$TemplateFile = "infrastructure/ui-hosting.yaml"
$UIDirectory = "ui"
$Region = "us-east-1"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Contract Intelligence Platform UI Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Stack: $StackName" -ForegroundColor Yellow
Write-Host ""

# Step 1: Build the React UI
if (-not $SkipBuild) {
    Write-Host "Step 1: Building React UI..." -ForegroundColor Green
    
    Push-Location $UIDirectory
    try {
        # Update .env for production
        $ApiEndpoint = "https://gf23r0si4a.execute-api.us-east-1.amazonaws.com/dev"
        
        Write-Host "Creating production .env file..." -ForegroundColor Yellow
        $envContent = "VITE_API_BASE_URL=$ApiEndpoint`nVITE_AWS_REGION=us-east-1`nVITE_ENVIRONMENT=$Environment"
        $envContent | Out-File -FilePath ".env.production" -Encoding UTF8
        
        Write-Host "Running npm build..." -ForegroundColor Yellow
        npm run build
        
        if ($LASTEXITCODE -ne 0) {
            throw "npm build failed"
        }
        
        Write-Host "Build complete" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "Step 1: Skipping build (using existing)" -ForegroundColor Yellow
}

# Step 2: Deploy CloudFormation infrastructure
if (-not $SkipInfrastructure) {
    Write-Host ""
    Write-Host "Step 2: Deploying S3 + CloudFront infrastructure..." -ForegroundColor Green
    
    Write-Host "Validating template..." -ForegroundColor Yellow
    aws cloudformation validate-template --template-body file://$TemplateFile --region $Region | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        throw "Template validation failed"
    }
    
    Write-Host "Deploying CloudFormation stack..." -ForegroundColor Yellow
    aws cloudformation deploy --template-file $TemplateFile --stack-name $StackName --parameter-overrides Environment=$Environment ProjectPrefix=$ProjectPrefix --region $Region --no-fail-on-empty-changeset
    
    if ($LASTEXITCODE -ne 0) {
        throw "CloudFormation deployment failed"
    }
    
    Write-Host "Infrastructure deployed" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "Step 2: Skipping infrastructure deployment" -ForegroundColor Yellow
}

# Step 3: Get stack outputs
Write-Host ""
Write-Host "Step 3: Retrieving stack outputs..." -ForegroundColor Green

$Outputs = aws cloudformation describe-stacks --stack-name $StackName --query 'Stacks[0].Outputs' --region $Region | ConvertFrom-Json

$BucketName = ($Outputs | Where-Object { $_.OutputKey -eq 'UIBucketName' }).OutputValue
$DistributionId = ($Outputs | Where-Object { $_.OutputKey -eq 'CloudFrontDistributionId' }).OutputValue
$WebsiteURL = ($Outputs | Where-Object { $_.OutputKey -eq 'WebsiteURL' }).OutputValue

Write-Host "Bucket: $BucketName" -ForegroundColor Yellow
Write-Host "Distribution: $DistributionId" -ForegroundColor Yellow
Write-Host "URL: $WebsiteURL" -ForegroundColor Yellow

# Step 4: Upload files to S3
Write-Host ""
Write-Host "Step 4: Uploading files to S3..." -ForegroundColor Green

$DistPath = Join-Path $UIDirectory "dist"

if (-not (Test-Path $DistPath)) {
    throw "Build directory not found: $DistPath"
}

Write-Host "Syncing files to s3://$BucketName..." -ForegroundColor Yellow
aws s3 sync $DistPath s3://$BucketName --delete --cache-control "public, max-age=31536000, immutable" --exclude "index.html" --region $Region

# Upload index.html separately with no-cache
Write-Host "Uploading index.html with no-cache..." -ForegroundColor Yellow
$indexPath = Join-Path $DistPath "index.html"
aws s3 cp $indexPath s3://$BucketName/index.html --cache-control "no-cache, no-store, must-revalidate" --content-type "text/html" --region $Region

Write-Host "Files uploaded" -ForegroundColor Green

# Step 5: Invalidate CloudFront cache
Write-Host ""
Write-Host "Step 5: Invalidating CloudFront cache..." -ForegroundColor Green

$InvalidationId = aws cloudfront create-invalidation --distribution-id $DistributionId --paths "/*" --query 'Invalidation.Id' --output text --region $Region

Write-Host "Invalidation ID: $InvalidationId" -ForegroundColor Yellow
Write-Host "Cache invalidation in progress..." -ForegroundColor Yellow

# Summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Website URL: $WebsiteURL" -ForegroundColor Green
Write-Host ""
Write-Host "Note: CloudFront may take 5-10 minutes to fully propagate." -ForegroundColor Yellow
Write-Host "      You can check status at:" -ForegroundColor Yellow
Write-Host "      https://console.aws.amazon.com/cloudfront/v3/home#/distributions/$DistributionId" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Endpoint: https://gf23r0si4a.execute-api.us-east-1.amazonaws.com/dev" -ForegroundColor Yellow
Write-Host ""
