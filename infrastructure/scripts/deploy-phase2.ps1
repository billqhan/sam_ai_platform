# AI-powered RFP Response Agent - Phase 2 Deployment (Lambda Functions)
# This script deploys only the Lambda functions and IAM roles

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
AI-powered RFP Response Agent - Phase 2 Deployment (Lambda Functions)

USAGE:
    .\deploy-phase2.ps1 -TemplatesBucket <bucket> -SamApiKey <key> -CompanyName <name> -CompanyContact <email> [OPTIONS]

This deploys Lambda functions and IAM roles. Requires Phase 1 to be deployed first.

"@
    exit 0
}

$StackName = "$StackNamePrefix-phase2-$Environment"
$Phase1StackName = "$StackNamePrefix-phase1-$Environment"

Write-Host "[INFO] Deploying Phase 2: Lambda Functions" -ForegroundColor Blue
Write-Host "  Environment: $Environment"
Write-Host "  Stack Name: $StackName"
Write-Host "  Bucket Prefix: $BucketPrefix"

# Get SQS Queue ARN from Phase 1 stack
try {
    $SqsQueueArn = aws cloudformation describe-stacks --stack-name $Phase1StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='SqsSamJsonMessagesQueueArn'].OutputValue" --output text
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($SqsQueueArn)) {
        throw "Could not get SQS Queue ARN from Phase 1 stack"
    }
    Write-Host "[INFO] Found SQS Queue ARN: $SqsQueueArn" -ForegroundColor Blue
} catch {
    Write-Host "[ERROR] Phase 1 stack not found or incomplete. Please deploy Phase 1 first." -ForegroundColor Red
    exit 1
}

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
        ParameterKey = "SqsSamJsonMessagesQueueArn"
        ParameterValue = $SqsQueueArn
    },
    @{
        ParameterKey = "BucketPrefix"
        ParameterValue = $BucketPrefix
    }
)

$ParametersJson = $Parameters | ConvertTo-Json
[System.IO.File]::WriteAllText($ParamsFile, $ParametersJson, [System.Text.UTF8Encoding]::new($false))

$TemplateUrl = "https://$TemplatesBucket.s3.amazonaws.com/ai-rfp-response-agent/lambda-functions.yaml"

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
        Write-Host "[SUCCESS] Phase 2 deployment completed!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Phase 2 deployment failed!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Phase 2 deployment failed: $_" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item -Path $ParamsFile -Force -ErrorAction SilentlyContinue
}