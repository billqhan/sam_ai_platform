# Deploy Web UI Script
# This script builds and deploys the React web UI to S3

param(
    [string]$BucketPrefix = $env:BUCKET_PREFIX,
    [string]$Environment = $(if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "dev" }),
    [string]$Region = "us-east-1",
    [switch]$CreateBucket,
    [string]$OverrideBucketName
)

$ErrorActionPreference = "Stop"
$uiDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $uiDir

# Load .env.dev if present to get SAM_WEBSITE_BUCKET / UI_BUCKET
function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
    $map = @{}
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim(); if (-not $line -or $line.StartsWith('#')) { return }
        if ($line.StartsWith('export ')) { $line = $line.Substring(7) }
        $eq = $line.IndexOf('='); if ($eq -lt 1) { return }
        $k = $line.Substring(0,$eq).Trim(); $v = $line.Substring($eq+1).Trim().Trim('"')
        $map[$k] = $v
    }
    return $map
}
$envFile = Join-Path (Split-Path $uiDir -Parent) '.env.dev'
$envMap = Import-DotEnv -Path $envFile

# Determine bucket name precedence: override > SAM_WEBSITE_BUCKET env > UI_BUCKET env > SAM_WEBSITE_BUCKET in file > UI_BUCKET in file > legacy naming
function Expand-Template([string]$value, [hashtable]$vars) {
    if (-not $value) { return $value }
    $pattern = '\$\{([A-Za-z0-9_]+)\}'
    $result = $value
    $max = 5
    for ($i=0; $i -lt $max; $i++) {
        $matches = [regex]::Matches($result, $pattern)
        if ($matches.Count -eq 0) { break }
        foreach ($m in $matches) {
            $k = $m.Groups[1].Value
            $replacement = $null
            if ($vars.ContainsKey($k)) { $replacement = $vars[$k] }
            elseif (Test-Path "Env:$k") { $replacement = (Get-Item -Path "Env:$k").Value }
            if ($replacement) {
                $result = $result.Replace($m.Value, [string]$replacement)
            }
        }
    }
    return $result
}

if ($OverrideBucketName) {
    $BucketName = $OverrideBucketName
} elseif ($env:SAM_WEBSITE_BUCKET) {
    $BucketName = $env:SAM_WEBSITE_BUCKET
} elseif ($env:UI_BUCKET) {
    $BucketName = $env:UI_BUCKET
} elseif ($envMap['SAM_WEBSITE_BUCKET']) {
    $BucketName = $envMap['SAM_WEBSITE_BUCKET']
} elseif ($envMap['UI_BUCKET']) {
    $BucketName = $envMap['UI_BUCKET']
} else {
    $BucketName = if ($BucketPrefix) { "$BucketPrefix-rfp-ui-$Environment" } else { "rfp-ui-$Environment" }
}

# Expand ${VAR} templates using values from .env.dev and current env
$BucketName = Expand-Template $BucketName $envMap
Write-Host "Using bucket: $BucketName" -ForegroundColor Gray

# Common AWS flags (allow insecure SSL via env var override for corporate cert issues)
$awsFlags = @('--region', $Region)
if ($env:AWS_INSECURE_SSL -eq 'true') { $awsFlags += '--no-verify-ssl' }

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "           WEB UI DEPLOYMENT SCRIPT" -ForegroundColor Cyan
Write-Host "===============================================`n" -ForegroundColor Cyan

# Create bucket if requested
if ($CreateBucket) {
    Write-Host "[1/4] Creating S3 bucket..." -ForegroundColor Yellow
    try {
        aws s3 mb "s3://$BucketName" @awsFlags
        Write-Host "  [OK] Bucket created: $BucketName" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Bucket may already exist" -ForegroundColor Yellow
    }
    
    # Configure bucket for static website hosting
    Write-Host "  Configuring static website hosting..." -ForegroundColor Yellow
    aws s3 website "s3://$BucketName" --index-document index.html --error-document index.html @awsFlags
    
    # Set bucket policy for public read
    $policyObj = [ordered]@{
        Version   = "2012-10-17"
        Statement = @(
            [ordered]@{
                Sid       = "PublicReadGetObject"
                Effect    = "Allow"
                Principal = "*"
                Action    = "s3:GetObject"
                Resource  = "arn:aws:s3:::$BucketName/*"
            }
        )
    }
    $policy = $policyObj | ConvertTo-Json -Depth 5
    $policy | Out-File -FilePath bucket-policy.json -Encoding ascii
    aws s3api put-bucket-policy --bucket $BucketName --policy file://bucket-policy.json @awsFlags
    Remove-Item bucket-policy.json
    Write-Host "  [OK] Website hosting configured" -ForegroundColor Green
    Write-Host ""
}

# Build React app (ensure deps installed)
Write-Host "[2/4] Building React application..." -ForegroundColor Yellow
# If local vite exists, skip reinstall
$viteLocal = Join-Path $PWD "node_modules/.bin/vite.cmd"
if (-not (Test-Path $viteLocal)) {
    if (-not (Test-Path (Join-Path $PWD 'node_modules'))) {
        Write-Host "  Installing UI dependencies (npm ci)..." -ForegroundColor Yellow
        try {
            npm ci
        } catch { }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  npm ci failed, falling back to 'npm install'..." -ForegroundColor Yellow
            npm install
        }
    } else {
        Write-Host "  node_modules present; ensuring deps are up to date (npm install)..." -ForegroundColor Yellow
        npm install
    }
}
# Use npx to ensure local vite resolution
npx vite build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [X] Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Build completed" -ForegroundColor Green
Write-Host ""

# Upload to S3
Write-Host "[3/4] Uploading to S3 bucket '$BucketName'..." -ForegroundColor Yellow
aws s3 sync dist/ "s3://$BucketName" --delete @awsFlags
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [X] Upload failed!" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Upload completed" -ForegroundColor Green
Write-Host ""

# Get website URL
Write-Host "[4/4] Deployment complete!" -ForegroundColor Green
$websiteUrl = "http://$BucketName.s3-website-$Region.amazonaws.com"
Write-Host ""
Write-Host "  Website URL: $websiteUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Note: For production, configure CloudFront distribution" -ForegroundColor Yellow
Write-Host "  with custom domain and SSL certificate." -ForegroundColor Yellow
Write-Host ""

# stay in $uiDir
