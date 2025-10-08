# AI-powered RFP Response Agent - PowerShell Deployment Script
# This script deploys the CloudFormation infrastructure

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

# Show help if requested
if ($Help) {
    Write-Host @"
AI-powered RFP Response Agent - Deployment Script

USAGE:
    .\deploy.ps1 -TemplatesBucket <bucket> -SamApiKey <key> -CompanyName <name> -CompanyContact <email> [OPTIONS]

PARAMETERS:
    -Environment        Environment name (dev, staging, prod) [default: dev]
    -Region            AWS region [default: us-east-1]
    -TemplatesBucket   S3 bucket for CloudFormation templates (required)
    -SamApiKey         SAM.gov API key (required)
    -CompanyName       Company name for reports (required)
    -CompanyContact    Company contact email (required)
    -StackNamePrefix   Custom stack name prefix [default: ai-rfp-response-agent]
    -BucketPrefix      Prefix for S3 bucket names to avoid conflicts [optional]
    -Help              Show this help message

EXAMPLES:
    .\deploy.ps1 -TemplatesBucket "my-templates-bucket" -SamApiKey "your-api-key" -CompanyName "My Company" -CompanyContact "contact@company.com"
    .\deploy.ps1 -Environment "prod" -TemplatesBucket "prod-templates" -SamApiKey "key" -CompanyName "Company" -CompanyContact "email@company.com" -BucketPrefix "mycompany"

"@
    exit 0
}

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$CFDir = Join-Path $ProjectRoot "infrastructure\cloudformation"
$StackName = "$StackNamePrefix-$Environment"

# Function to write colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Display configuration
Write-Status "Starting deployment with the following configuration:"
Write-Host "  Environment: $Environment"
Write-Host "  Region: $Region"
Write-Host "  Stack Name: $StackName"
Write-Host "  Templates Bucket: $TemplatesBucket"
Write-Host "  Company Name: $CompanyName"
Write-Host "  Company Contact: $CompanyContact"
Write-Host "  Bucket Prefix: $BucketPrefix"
Write-Host ""

# Check if AWS CLI is installed
try {
    $null = Get-Command aws -ErrorAction Stop
} catch {
    Write-Error "AWS CLI is not installed. Please install it first."
    exit 1
}

# Check AWS credentials
try {
    $null = aws sts get-caller-identity 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "AWS credentials not configured"
    }
} catch {
    Write-Error "AWS credentials not configured. Please run 'aws configure' first."
    exit 1
}

# Check if templates bucket exists
Write-Status "Checking if templates bucket exists..."
try {
    $null = aws s3 ls "s3://$TemplatesBucket" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Bucket not accessible"
    }
    Write-Success "Templates bucket is accessible"
} catch {
    Write-Error "Templates bucket '$TemplatesBucket' does not exist or is not accessible."
    exit 1
}

# Upload CloudFormation templates
Write-Status "Uploading CloudFormation templates to S3..."
try {
    aws s3 sync $CFDir "s3://$TemplatesBucket/ai-rfp-response-agent/" --exclude "*.md" --exclude "*.json" --exclude "README*" --delete
    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed"
    }
    Write-Success "Templates uploaded successfully"
} catch {
    Write-Error "Failed to upload templates"
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
        ParameterKey = "TemplatesBucketName"
        ParameterValue = $TemplatesBucket
    },
    @{
        ParameterKey = "TemplatesBucketPrefix"
        ParameterValue = "ai-rfp-response-agent/"
    },
    @{
        ParameterKey = "BucketPrefix"
        ParameterValue = $BucketPrefix
    }
)

# Create parameters file without BOM
$ParametersJson = $Parameters | ConvertTo-Json
[System.IO.File]::WriteAllText($ParamsFile, $ParametersJson, [System.Text.UTF8Encoding]::new($false))

# Check if stack exists
Write-Status "Checking if stack exists..."
try {
    $null = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null
    if ($LASTEXITCODE -eq 0) {
        $StackExists = $true
        Write-Status "Stack exists. Will update existing stack."
    } else {
        $StackExists = $false
        Write-Status "Stack does not exist. Will create new stack."
    }
} catch {
    $StackExists = $false
    Write-Status "Stack does not exist. Will create new stack."
}

# Deploy or update stack
$TemplateUrl = "https://$TemplatesBucket.s3.amazonaws.com/ai-rfp-response-agent/master-template.yaml"

if ($StackExists) {
    Write-Status "Updating CloudFormation stack..."
    try {
        aws cloudformation update-stack --stack-name $StackName --template-url $TemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region
        if ($LASTEXITCODE -ne 0) {
            throw "Update initiation failed"
        }
        
        Write-Status "Stack update initiated. Waiting for completion..."
        aws cloudformation wait stack-update-complete --stack-name $StackName --region $Region
        if ($LASTEXITCODE -ne 0) {
            throw "Stack update failed"
        }
        
        Write-Success "Stack updated successfully!"
    } catch {
        Write-Error "Stack update failed: $_"
        exit 1
    }
} else {
    Write-Status "Creating CloudFormation stack..."
    try {
        aws cloudformation create-stack --stack-name $StackName --template-url $TemplateUrl --parameters "file://$ParamsFile" --capabilities CAPABILITY_NAMED_IAM --region $Region --tags Key=Environment,Value=$Environment Key=Project,Value=AI-RFP-Response-Agent
        if ($LASTEXITCODE -ne 0) {
            throw "Creation initiation failed"
        }
        
        Write-Status "Stack creation initiated. Waiting for completion..."
        aws cloudformation wait stack-create-complete --stack-name $StackName --region $Region
        if ($LASTEXITCODE -ne 0) {
            throw "Stack creation failed"
        }
        
        Write-Success "Stack created successfully!"
    } catch {
        Write-Error "Stack creation failed: $_"
        exit 1
    }
}

# Get stack outputs
Write-Status "Retrieving stack outputs..."
try {
    $Outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output table
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Deployment completed successfully!"
        Write-Host ""
        Write-Host "Stack Outputs:"
        Write-Host $Outputs
        Write-Host ""
        Write-Status "Next steps:"
        Write-Host "1. Upload company information to the sam-company-info-$Environment S3 bucket"
        Write-Host "2. Configure the Bedrock Knowledge Base ID in Lambda environment variables"
        Write-Host "3. Test the pipeline by triggering the daily download function"
        Write-Host "4. Monitor the CloudWatch dashboard for system health"
    } else {
        Write-Warning "Deployment completed but failed to retrieve outputs"
    }
} catch {
    Write-Warning "Deployment completed but failed to retrieve outputs"
}

# Cleanup temporary files
Remove-Item -Path $ParamsFile -Force -ErrorAction SilentlyContinue

Write-Success "Deployment script completed!"