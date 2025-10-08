# AI-powered RFP Response Agent - Multi-Phase Deployment Script
# This script can deploy all phases or individual phases

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$true)]
    [string]$TemplatesBucket,
    
    [Parameter(Mandatory=$true)]
    [string]$SamApiKey,
    
    [Parameter(Mandatory=$true)]
    [string]$CompanyName,
    
    [Parameter(Mandatory=$true)]
    [string]$CompanyContact,
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("1", "2", "3", "all")]
    [string]$Phase = "all",
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

if ($Help) {
    Write-Host @"
AI-powered RFP Response Agent - Multi-Phase Deployment

USAGE:
    .\deploy-all-phases.ps1 -TemplatesBucket <bucket> -SamApiKey <key> -CompanyName <name> -CompanyContact <email> [OPTIONS]

PHASES:
    Phase 1: Core Infrastructure (S3 buckets, SQS queues)
    Phase 2: Lambda Functions (simplified versions)
    Phase 3: Security & Monitoring (IAM policies, KMS keys)

OPTIONS:
    -Phase <1|2|3|all>     Deploy specific phase or all phases [default: all]
    -BucketPrefix <prefix> Prefix for S3 bucket names to avoid conflicts

EXAMPLES:
    # Deploy all phases
    .\deploy-all-phases.ps1 -TemplatesBucket "my-bucket" -SamApiKey "key" -CompanyName "My Company" -CompanyContact "email@company.com"
    
    # Deploy only Phase 1
    .\deploy-all-phases.ps1 -TemplatesBucket "my-bucket" -SamApiKey "key" -CompanyName "My Company" -CompanyContact "email@company.com" -Phase 1
    
    # Deploy with bucket prefix
    .\deploy-all-phases.ps1 -TemplatesBucket "my-bucket" -SamApiKey "key" -CompanyName "My Company" -CompanyContact "email@company.com" -BucketPrefix "mycompany"

"@
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== AI-powered RFP Response Agent - Multi-Phase Deployment ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor White
Write-Host "Region: $Region" -ForegroundColor White
Write-Host "Bucket Prefix: $BucketPrefix" -ForegroundColor White
Write-Host "Phase: $Phase" -ForegroundColor White
Write-Host ""

# Upload templates first
Write-Host "[INFO] Uploading CloudFormation templates..." -ForegroundColor Blue
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$CFDir = Join-Path $ProjectRoot "infrastructure\cloudformation"
aws s3 sync $CFDir "s3://$TemplatesBucket/ai-rfp-response-agent/" --exclude "*.md" --exclude "*.json" --exclude "README*" --delete

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to upload templates" -ForegroundColor Red
    exit 1
}
Write-Host "[SUCCESS] Templates uploaded" -ForegroundColor Green

# Phase 1: Core Infrastructure
if ($Phase -eq "1" -or $Phase -eq "all") {
    Write-Host ""
    Write-Host "=== PHASE 1: Core Infrastructure ===" -ForegroundColor Yellow
    & "$ScriptDir\deploy-phase1.ps1" -Environment $Environment -Region $Region -TemplatesBucket $TemplatesBucket -SamApiKey $SamApiKey -CompanyName $CompanyName -CompanyContact $CompanyContact -BucketPrefix $BucketPrefix
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Phase 1 failed. Stopping deployment." -ForegroundColor Red
        exit 1
    }
}

# Phase 2: Lambda Functions
if ($Phase -eq "2" -or $Phase -eq "all") {
    Write-Host ""
    Write-Host "=== PHASE 2: Lambda Functions ===" -ForegroundColor Yellow
    & "$ScriptDir\deploy-phase2.ps1" -Environment $Environment -Region $Region -TemplatesBucket $TemplatesBucket -SamApiKey $SamApiKey -CompanyName $CompanyName -CompanyContact $CompanyContact -BucketPrefix $BucketPrefix
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Phase 2 failed. Stopping deployment." -ForegroundColor Red
        exit 1
    }
}

# Phase 3: Security & Monitoring
if ($Phase -eq "3" -or $Phase -eq "all") {
    Write-Host ""
    Write-Host "=== PHASE 3: Security & Monitoring ===" -ForegroundColor Yellow
    & "$ScriptDir\deploy-phase3.ps1" -Environment $Environment -Region $Region -TemplatesBucket $TemplatesBucket -CompanyContact $CompanyContact -BucketPrefix $BucketPrefix
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Phase 3 failed. Stopping deployment." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=== DEPLOYMENT COMPLETED SUCCESSFULLY ===" -ForegroundColor Green
Write-Host "All requested phases have been deployed successfully!" -ForegroundColor Green