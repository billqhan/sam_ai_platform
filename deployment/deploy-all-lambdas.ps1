#!/usr/bin/env pwsh

# Deploy All SAM Lambda Functions
# This script packages and deploys all lambda functions

param(
    [string]$Environment = "dev",
    [string]$BucketPrefix = "l3harris-qhan",
    [string]$Region = "us-east-1"
)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYING ALL LAMBDA FUNCTIONS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Bucket Prefix: $BucketPrefix" -ForegroundColor Yellow
Write-Host "Region: $Region`n" -ForegroundColor Yellow

# Define all Lambda functions
$LambdaFunctions = @(
    "sam-gov-daily-download",
    "sam-json-processor",
    "sam-sqs-generate-match-reports",
    "sam-produce-user-report",
    "sam-merge-and-archive-result-logs",
    "sam-produce-web-reports",
    "sam-daily-email-notification"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SourceRoot = Join-Path $ProjectRoot "src/lambdas"
$SharedDir = Join-Path $ProjectRoot "src/shared"
$TempRoot = Join-Path $ScriptDir "temp"

# Create temp directory
if (!(Test-Path $TempRoot)) {
    New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
}

$SuccessCount = 0
$FailCount = 0
$FailedFunctions = @()

foreach ($FunctionName in $LambdaFunctions) {
    $LambdaFullName = "$BucketPrefix-$FunctionName-$Environment"
    $SourceDir = Join-Path $SourceRoot $FunctionName
    $TempDir = Join-Path $TempRoot "lambda_package_$FunctionName"
    $ZipFile = Join-Path $TempRoot "$FunctionName.zip"
    
    Write-Host "`n-------------------------------------------------" -ForegroundColor Gray
    Write-Host "Deploying: $FunctionName" -ForegroundColor Cyan
    Write-Host "-------------------------------------------------" -ForegroundColor Gray
    
    try {
        # Check if source directory exists
        if (!(Test-Path $SourceDir)) {
            Write-Host "    Source directory not found: $SourceDir" -ForegroundColor Yellow
            $FailCount++
            $FailedFunctions += $FunctionName
            continue
        }
        
        # Clean up previous builds
        if (Test-Path $TempDir) {
            Remove-Item -Recurse -Force $TempDir
        }
        if (Test-Path $ZipFile) {
            Remove-Item -Force $ZipFile
        }
        
        # Create temp directory
        New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
        
        Write-Host "   Copying source files..." -ForegroundColor Blue
        
        # Copy lambda function files
        Copy-Item -Path "$SourceDir/*" -Destination $TempDir -Recurse -Force
        
        # Copy shared utilities if they exist
        if (Test-Path $SharedDir) {
            $SharedDestDir = Join-Path $TempDir "shared"
            New-Item -ItemType Directory -Path $SharedDestDir -Force | Out-Null
            Copy-Item -Path "$SharedDir/*" -Destination $SharedDestDir -Recurse -Force
        }
        
        # Check if lambda_function.py exists, if not check for handler.py
        $LambdaFunctionPath = Join-Path $TempDir "lambda_function.py"
        $HandlerPath = Join-Path $TempDir "handler.py"
        
        if (!(Test-Path $LambdaFunctionPath) -and (Test-Path $HandlerPath)) {
            # Create lambda_function.py that imports from handler
            $LambdaFunctionContent = @"
"""
Lambda function entry point for $FunctionName.
"""
from handler import lambda_handler

__all__ = ['lambda_handler']
"@
            Set-Content -Path $LambdaFunctionPath -Value $LambdaFunctionContent
            Write-Host "   Created lambda_function.py wrapper" -ForegroundColor Green
        }
        
        # Install dependencies if requirements.txt exists
        $RequirementsPath = Join-Path $TempDir "requirements.txt"
        if (Test-Path $RequirementsPath) {
            Write-Host "   Installing dependencies..." -ForegroundColor Blue
            pip3 install -r $RequirementsPath -t $TempDir --quiet --no-color
            
            if ($LASTEXITCODE -ne 0) {
                Write-Host "    Warning: Some dependencies may have failed to install" -ForegroundColor Yellow
            } else {
                Write-Host "   Dependencies installed" -ForegroundColor Green
            }
        }
        
        # Create ZIP file
        Write-Host "   Creating deployment package..." -ForegroundColor Blue
        
        # Use PowerShell to create zip
        $ZipAbsolutePath = Join-Path (Resolve-Path $TempRoot).Path "$FunctionName.zip"
        Compress-Archive -Path (Join-Path $TempDir "*") -DestinationPath $ZipAbsolutePath -Force
        
        Write-Host "   Package created: $ZipAbsolutePath" -ForegroundColor Green
        
        # Upload to S3 first (more reliable for large packages)
        $S3CodeBucket = if ($env:TEMPLATES_BUCKET) { $env:TEMPLATES_BUCKET } else { "ai-rfp-templates-dev" }
        $S3CodeKey = "lambda/$FunctionName.zip"
        
        Write-Host "    Uploading to S3: s3://$S3CodeBucket/$S3CodeKey" -ForegroundColor Blue
        aws s3 cp $ZipAbsolutePath "s3://$S3CodeBucket/$S3CodeKey" --region $Region --quiet 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   Failed to upload to S3: $FunctionName" -ForegroundColor Red
            $FailCount++
            $FailedFunctions += $FunctionName
            continue
        }
        
        # Update Lambda function from S3
        Write-Host "    Updating Lambda function from S3..." -ForegroundColor Blue
        
        $UpdateResult = aws lambda update-function-code `
            --function-name $LambdaFullName `
            --s3-bucket $S3CodeBucket `
            --s3-key $S3CodeKey `
            --region $Region `
            --query '{FunctionName:FunctionName,LastModified:LastModified,CodeSize:CodeSize}' `
            --output json 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   Successfully deployed: $FunctionName" -ForegroundColor Green
            $SuccessCount++
            
            # Parse and display update info
            try {
                $UpdateInfo = $UpdateResult | ConvertFrom-Json
                Write-Host "     Size: $($UpdateInfo.CodeSize) bytes" -ForegroundColor Gray
                Write-Host "     Modified: $($UpdateInfo.LastModified)" -ForegroundColor Gray
            } catch {
                # Ignore JSON parse errors
            }
        } else {
            Write-Host "   Failed to deploy: $FunctionName" -ForegroundColor Red
            Write-Host "     Error: $UpdateResult" -ForegroundColor Red
            $FailCount++
            $FailedFunctions += $FunctionName
        }
        
    } catch {
        Write-Host "   Error deploying $FunctionName : $_" -ForegroundColor Red
        $FailCount++
        $FailedFunctions += $FunctionName
    }
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total Functions: $($LambdaFunctions.Count)" -ForegroundColor White
Write-Host " Successful: $SuccessCount" -ForegroundColor Green
Write-Host " Failed: $FailCount" -ForegroundColor Red

if ($FailCount -gt 0) {
    Write-Host "`nFailed Functions:" -ForegroundColor Red
    foreach ($Failed in $FailedFunctions) {
        Write-Host "  - $Failed" -ForegroundColor Red
    }
}

# Clean up temp directory
Write-Host "`nCleaning up temporary files..." -ForegroundColor Gray
if (Test-Path $TempRoot) {
    Remove-Item -Recurse -Force $TempRoot
}

Write-Host "`nDeployment process completed!`n" -ForegroundColor Cyan

exit $FailCount

