# AI-powered RFP Response Agent - Phase 1 Deployment (Core Infrastructure)
# This script deploys only the core S3 buckets and SQS queues

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
    [string]$StackNamePrefix = "ai-rfp-response-agent",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

if ($Help) {
    Write-Host @"
AI-powered RFP Response Agent - Phase 1 Deployment (Core Infrastructure)

USAGE:
    .\deploy-phase1.ps1 -TemplatesBucket <bucket> -SamApiKey <key> -CompanyName <name> -CompanyContact <email> [OPTIONS]

This deploys only the core infrastructure: S3 buckets and SQS queues.

"@
    exit 0
}

$StackName = "$StackNamePrefix-phase1-$Environment"

Write-Host "[INFO] Deploying Phase 1: Core Infrastructure (S3 + SQS)" -ForegroundColor Blue
Write-Host "  Environment: $Environment"
Write-Host "  Stack Name: $StackName"
Write-Host "  Bucket Prefix: $BucketPrefix"

# Create parameters file
$ParamsFile = [System.IO.Path]::GetTempFileName()
$Parameters = @(
    @{
        ParameterKey = "Environment"
        ParameterValue = $Environment
    },
    @{
        ParameterKey = "SamApiKey"
        ParameterValue = $SamApiKey
    },
    @{
        ParameterKey = "CompanyName"
        ParameterValue = $CompanyName
    },
    @{
        ParameterKey = "CompanyContact"
        ParameterValue = $CompanyContact
    },
    @{
        ParameterKey = "BucketPrefix"
        ParameterValue = $BucketPrefix
    }
)

$ParametersJson = $Parameters | ConvertTo-Json
[System.IO.File]::WriteAllText($ParamsFile, $ParametersJson, [System.Text.UTF8Encoding]::new($false))

$TemplateUrl = "https://$TemplatesBucket.s3.amazonaws.com/ai-rfp-response-agent/main-template.yaml"

try {
    $null = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[INFO] Updating existing stack..." -ForegroundColor Blue
        aws cloudformation update-stack --stack-name $StackName --template-url $TemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region
        aws cloudformation wait stack-update-complete --stack-name $StackName --region $Region
    } else {
        Write-Host "[INFO] Creating new stack..." -ForegroundColor Blue
        aws cloudformation create-stack --stack-name $StackName --template-url $TemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region
        aws cloudformation wait stack-create-complete --stack-name $StackName --region $Region
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Phase 1 deployment completed!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Phase 1 deployment failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Phase 1 deployment failed: $_" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item -Path $ParamsFile -Force -ErrorAction SilentlyContinue
}