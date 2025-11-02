#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete deployment script for AI-RFP Response Agent
    
.DESCRIPTION
    This script performs a complete deployment:
    1. Deploys CloudFormation infrastructure
    2. Deploys all Lambda function code
    3. Configures Lambda environment variables
    4. Runs reporting workflow to validate
    
.PARAMETER Environment
    Environment name (dev, staging, prod). Default: dev
    
.PARAMETER Region
    AWS region. Default: us-east-1
    
.PARAMETER TemplatesBucket
    S3 bucket containing CloudFormation templates (required)
    
.PARAMETER SamApiKey
    SAM.gov API key (required)
    
.PARAMETER CompanyName
    Company name for reports. Default: L3Harris
    
.PARAMETER CompanyContact
    Company contact email. Default: bill.han@l3harris.com
    
.PARAMETER BucketPrefix
    Prefix for S3 bucket names. Default: l3harris-qhan
    
.PARAMETER KnowledgeBaseId
    Bedrock Knowledge Base ID. Default: '' (disabled)
    
.PARAMETER SkipInfrastructure
    Skip CloudFormation deployment (only deploy Lambda code)
    
.PARAMETER SkipLambdas
    Skip Lambda code deployment
    
.PARAMETER SkipReporting
    Skip reporting workflow validation
    
.EXAMPLE
    .\deploy-complete-stack.ps1 -TemplatesBucket 'dual-bucket-1' -SamApiKey 'your-key'
    
.EXAMPLE
    .\deploy-complete-stack.ps1 -TemplatesBucket 'dual-bucket-1' -SamApiKey 'your-key' -KnowledgeBaseId 'KB123456' -Environment prod
#>

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
    
    [Parameter(Mandatory=$false)]
    [string]$CompanyName = "L3Harris",
    
    [Parameter(Mandatory=$false)]
    [string]$CompanyContact = "bill.han@l3harris.com",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "l3harris-qhan",
    
    [Parameter(Mandatory=$false)]
    [string]$KnowledgeBaseId = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipInfrastructure,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipLambdas,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipReporting
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Helper functions
function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "→ $Message" -ForegroundColor Blue
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Display configuration
Write-Step "STARTING COMPLETE DEPLOYMENT"
Write-Info "Configuration:"
Write-Host "  Environment:       $Environment"
Write-Host "  Region:            $Region"
Write-Host "  Templates Bucket:  $TemplatesBucket"
Write-Host "  Company Name:      $CompanyName"
Write-Host "  Company Contact:   $CompanyContact"
Write-Host "  Bucket Prefix:     $BucketPrefix"
Write-Host "  Knowledge Base ID: $(if ($KnowledgeBaseId) { $KnowledgeBaseId } else { '(disabled)' })"
Write-Host ""
Write-Info "Steps to execute:"
if (!$SkipInfrastructure) { Write-Host "  [1] Deploy CloudFormation infrastructure" }
if (!$SkipLambdas) { Write-Host "  [2] Deploy Lambda function code" }
if (!$SkipLambdas) { Write-Host "  [3] Configure Lambda environment variables" }
if (!$SkipReporting) { Write-Host "  [4] Validate reporting workflow" }
Write-Host ""

# Track deployment status
$DeploymentStatus = @{
    Infrastructure = $false
    Lambdas = $false
    Configuration = $false
    Reporting = $false
}

try {
    # Step 1: Deploy CloudFormation Infrastructure
    if (!$SkipInfrastructure) {
        Write-Step "STEP 1: DEPLOYING CLOUDFORMATION INFRASTRUCTURE"
        
        $InfraScriptPath = Join-Path $ProjectRoot "infrastructure\scripts\deploy.ps1"
        
        if (!(Test-Path $InfraScriptPath)) {
            throw "Infrastructure deployment script not found: $InfraScriptPath"
        }
        
        Write-Info "Running infrastructure deployment..."
        & $InfraScriptPath `
            -Environment $Environment `
            -Region $Region `
            -TemplatesBucket $TemplatesBucket `
            -SamApiKey $SamApiKey `
            -CompanyName $CompanyName `
            -CompanyContact $CompanyContact `
            -BucketPrefix $BucketPrefix `
            -KnowledgeBaseId $KnowledgeBaseId
        
        if ($LASTEXITCODE -ne 0) {
            throw "Infrastructure deployment failed with exit code $LASTEXITCODE"
        }
        
        $DeploymentStatus.Infrastructure = $true
        Write-Success "Infrastructure deployment completed"
    } else {
        Write-Warning "Skipping infrastructure deployment (--SkipInfrastructure)"
    }
    
    # Step 2: Deploy Lambda Function Code
    if (!$SkipLambdas) {
        Write-Step "STEP 2: DEPLOYING LAMBDA FUNCTION CODE"
        
        $LambdaScriptPath = Join-Path $ScriptDir "deploy-all-lambdas.ps1"
        
        if (!(Test-Path $LambdaScriptPath)) {
            throw "Lambda deployment script not found: $LambdaScriptPath"
        }
        
        Write-Info "Deploying all Lambda functions..."
        & $LambdaScriptPath `
            -Environment $Environment `
            -BucketPrefix $BucketPrefix `
            -Region $Region
        
        if ($LASTEXITCODE -ne 0) {
            throw "Lambda deployment failed with exit code $LASTEXITCODE"
        }
        
        $DeploymentStatus.Lambdas = $true
        Write-Success "Lambda deployment completed"
        
        # Step 3: Configure Lambda Environment Variables
        Write-Step "STEP 3: CONFIGURING LAMBDA ENVIRONMENT VARIABLES"
        
        Write-Info "Updating sam-produce-web-reports environment..."
        aws lambda update-function-configuration `
            --function-name "$BucketPrefix-sam-produce-web-reports-$Environment" `
            --environment "Variables={WEBSITE_BUCKET=$BucketPrefix-sam-website-$Environment,SAM_WEBSITE_BUCKET=$BucketPrefix-sam-website-$Environment,SAM_MATCHING_OUT_RUNS_BUCKET=$BucketPrefix-sam-matching-out-runs-$Environment,DASHBOARD_PATH=dashboards/,X_AMZN_TRACE_ID=ai-rfp-response-agent-$Environment-sam-produce-web-reports}" `
            --region $Region `
            --no-cli-pager | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to update web-reports Lambda configuration"
        } else {
            Write-Success "Updated web-reports Lambda configuration"
        }
        
        Write-Info "Updating sam-produce-user-report environment..."
        aws lambda update-function-configuration `
            --function-name "$BucketPrefix-sam-produce-user-report-$Environment" `
            --environment "Variables={OUTPUT_BUCKET=$BucketPrefix-sam-opportunity-responses-$Environment,SAM_OPPORTUNITY_RESPONSES_BUCKET=$BucketPrefix-sam-opportunity-responses-$Environment,SAM_MATCHING_OUT_SQS_BUCKET=$BucketPrefix-sam-matching-out-sqs-$Environment,AGENT_ID=PLACEHOLDER,AGENT_ALIAS_ID=PLACEHOLDER,OUTPUT_FORMATS=txt\,docx,COMPANY_NAME=$CompanyName,COMPANY_CONTACT=$CompanyContact}" `
            --region $Region `
            --no-cli-pager | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to update user-report Lambda configuration"
        } else {
            Write-Success "Updated user-report Lambda configuration"
        }
        
        # Wait a moment for Lambda configuration to propagate
        Write-Info "Waiting for Lambda configuration to propagate..."
        Start-Sleep -Seconds 5
        
        $DeploymentStatus.Configuration = $true
        Write-Success "Lambda configuration completed"
    } else {
        Write-Warning "Skipping Lambda deployment (--SkipLambdas)"
    }
    
    # Step 4: Validate Reporting Workflow
    if (!$SkipReporting) {
        Write-Step "STEP 4: VALIDATING REPORTING WORKFLOW"
        
        $ReportingScriptPath = Join-Path $ScriptDir "generate-reports-and-notify.ps1"
        
        if (!(Test-Path $ReportingScriptPath)) {
            throw "Reporting script not found: $ReportingScriptPath"
        }
        
        Write-Info "Running reporting workflow..."
        & $ReportingScriptPath `
            -Region $Region `
            -BucketPrefix $BucketPrefix `
            -Env $Environment
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Reporting workflow completed with warnings"
        } else {
            Write-Success "Reporting workflow completed"
        }
        
        $DeploymentStatus.Reporting = $true
    } else {
        Write-Warning "Skipping reporting workflow (--SkipReporting)"
    }
    
    # Final Summary
    Write-Step "DEPLOYMENT COMPLETE"
    
    Write-Host "Deployment Status:" -ForegroundColor Cyan
    foreach ($key in $DeploymentStatus.Keys) {
        $status = if ($DeploymentStatus[$key]) { "✓" } else { "○" }
        $color = if ($DeploymentStatus[$key]) { "Green" } else { "Gray" }
        Write-Host "  $status $key" -ForegroundColor $color
    }
    
    Write-Host "`nNext Steps:" -ForegroundColor Yellow
    Write-Host "  1. Check S3 buckets for generated reports:"
    Write-Host "     - s3://$BucketPrefix-sam-website-$Environment/dashboards/"
    Write-Host "     - s3://$BucketPrefix-sam-opportunity-responses-$Environment/"
    Write-Host "  2. Monitor CloudWatch Logs for Lambda executions"
    Write-Host "  3. Review CloudWatch Dashboard:"
    Write-Host "     https://$Region.console.aws.amazon.com/cloudwatch/home?region=$Region#dashboards:name=AI-RFP-Response-Agent-$Environment"
    Write-Host "  4. (Optional) Enable S3 event notifications for automation"
    Write-Host "  5. (Optional) Configure Bedrock Knowledge Base if not already set"
    Write-Host ""
    
    Write-Success "All deployment steps completed successfully!"
    exit 0
    
} catch {
    Write-Error "Deployment failed: $_"
    Write-Host "`nDeployment Status:" -ForegroundColor Red
    foreach ($key in $DeploymentStatus.Keys) {
        $status = if ($DeploymentStatus[$key]) { "✓" } else { "✗" }
        $color = if ($DeploymentStatus[$key]) { "Green" } else { "Red" }
        Write-Host "  $status $key" -ForegroundColor $color
    }
    Write-Host ""
    exit 1
}
