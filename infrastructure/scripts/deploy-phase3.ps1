# AI-powered RFP Response Agent - Phase 3 Deployment (Security & Monitoring)
# This script deploys IAM security policies and monitoring

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "staging", "prod")]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1",
    
    [Parameter(Mandatory=$true)]
    [string]$TemplatesBucket,
    
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
AI-powered RFP Response Agent - Phase 3 Deployment (Security & Monitoring)

USAGE:
    .\deploy-phase3.ps1 -TemplatesBucket <bucket> -CompanyContact <email> [OPTIONS]

This deploys security policies and monitoring. Requires Phase 1 and 2 to be deployed first.

"@
    exit 0
}

$StackName = "$StackNamePrefix-phase3-$Environment"

Write-Host "[INFO] Deploying Phase 3: Security & Monitoring" -ForegroundColor Blue
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
        ParameterKey = "BucketPrefix"
        ParameterValue = $BucketPrefix
    }
)

$ParametersJson = $Parameters | ConvertTo-Json
[System.IO.File]::WriteAllText($ParamsFile, $ParametersJson, [System.Text.UTF8Encoding]::new($false))

# Deploy IAM Security Policies
$IamStackName = "$StackNamePrefix-iam-$Environment"
$IamTemplateUrl = "https://$TemplatesBucket.s3.amazonaws.com/ai-rfp-response-agent/iam-security-policies-simple.yaml"

Write-Host "[INFO] Deploying IAM Security Policies..." -ForegroundColor Blue
try {
    $null = aws cloudformation describe-stacks --stack-name $IamStackName --region $Region 2>$null
    if ($LASTEXITCODE -eq 0) {
        aws cloudformation update-stack --stack-name $IamStackName --template-url $IamTemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region
        aws cloudformation wait stack-update-complete --stack-name $IamStackName --region $Region
    } else {
        aws cloudformation create-stack --stack-name $IamStackName --template-url $IamTemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region
        aws cloudformation wait stack-create-complete --stack-name $IamStackName --region $Region
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] IAM Security Policies deployed!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] IAM Security Policies deployment failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] IAM deployment failed: $_" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item -Path $ParamsFile -Force -ErrorAction SilentlyContinue
}

Write-Host "[SUCCESS] Phase 3 deployment completed!" -ForegroundColor Green