#!/usr/bin/env pwsh

# Deploy SAM Produce Web Reports Lambda Function
# This script packages and deploys the enhanced web reports lambda function

param(
    [string]$Environment = "dev",
    [string]$BucketPrefix = "ktest"
)

Write-Host "Deploying SAM Produce Web Reports Lambda Function..." -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Bucket Prefix: $BucketPrefix" -ForegroundColor Yellow

# Set variables
$LambdaName = "$BucketPrefix-sam-produce-web-reports-$Environment"
$SourceDir = "src/lambdas/sam-produce-web-reports"
$SharedDir = "src/shared"
$TempDir = "temp/lambda_package_web_reports"
$ZipFile = "temp/sam-produce-web-reports-function.zip"

try {
    # Clean up previous builds
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
    if (Test-Path $ZipFile) {
        Remove-Item -Force $ZipFile
    }

    # Create temp directory
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
    New-Item -ItemType Directory -Path "temp" -Force | Out-Null

    Write-Host "Copying source files..." -ForegroundColor Blue

    # Copy lambda function files
    Copy-Item -Path "$SourceDir/*" -Destination $TempDir -Recurse -Force

    # Copy shared utilities
    $SharedDestDir = Join-Path $TempDir "shared"
    New-Item -ItemType Directory -Path $SharedDestDir -Force | Out-Null
    Copy-Item -Path "$SharedDir/*" -Destination $SharedDestDir -Recurse -Force

    # Create lambda_function.py that imports from handler
    $LambdaFunctionContent = @"
"""
Lambda function entry point for SAM Produce Web Reports.
"""
from handler import lambda_handler

# Export the handler for AWS Lambda
__all__ = ['lambda_handler']
"@

    Set-Content -Path (Join-Path $TempDir "lambda_function.py") -Value $LambdaFunctionContent

    Write-Host "Creating deployment package..." -ForegroundColor Blue

    # Create ZIP file
    $CurrentLocation = Get-Location
    Set-Location $TempDir
    
    # Create ZIP file using 7zip or native compression
    if (Get-Command "7z" -ErrorAction SilentlyContinue) {
        & 7z a -tzip "../sam-produce-web-reports-function.zip" "*" -r
    } else {
        # Fallback to PowerShell compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory((Get-Location), (Join-Path (Split-Path (Get-Location)) "sam-produce-web-reports-function.zip"))
    }
    
    Set-Location $CurrentLocation

    Write-Host "Deploying to AWS Lambda..." -ForegroundColor Blue

    # Update Lambda function code
    aws lambda update-function-code `
        --function-name $LambdaName `
        --zip-file "fileb://$ZipFile" `
        --region us-east-1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Lambda function deployed successfully!" -ForegroundColor Green
        
        # Update environment variables
        Write-Host "Updating environment variables..." -ForegroundColor Blue
        
        $EnvVarsJson = @"
{
    "Variables": {
        "WEBSITE_BUCKET": "$BucketPrefix-sam-website-$Environment",
        "SAM_MATCHING_OUT_RUNS_BUCKET": "$BucketPrefix-sam-matching-out-runs-$Environment",
        "DASHBOARD_PATH": "dashboards/"
    }
}
"@
        
        aws lambda update-function-configuration `
            --function-name $LambdaName `
            --environment $EnvVarsJson `
            --region us-east-1
            
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Environment variables updated successfully!" -ForegroundColor Green
        } else {
            Write-Host "Warning: Failed to update environment variables" -ForegroundColor Yellow
        }
        
        # Test the function
        Write-Host "Testing the deployed function..." -ForegroundColor Blue
        
        $TestEvent = @{
            "Records" = @(
                @{
                    "eventSource" = "aws:s3"
                    "s3" = @{
                        "bucket" = @{
                            "name" = "$BucketPrefix-sam-matching-out-runs-$Environment"
                        }
                        "object" = @{
                            "key" = "runs/$(Get-Date -Format 'yyyyMMdd')T1200Z.json"
                        }
                    }
                }
            )
        } | ConvertTo-Json -Depth 10 -Compress
        
        $TestEventFile = "temp/test-event.json"
        Set-Content -Path $TestEventFile -Value $TestEvent
        
        aws lambda invoke `
            --function-name $LambdaName `
            --payload "file://$TestEventFile" `
            --region us-east-1 `
            "temp/test-response.json"
            
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Function test completed. Check temp/test-response.json for results." -ForegroundColor Green
            $Response = Get-Content "temp/test-response.json" | ConvertFrom-Json
            Write-Host "Response: $($Response | ConvertTo-Json -Depth 3)" -ForegroundColor Cyan
        } else {
            Write-Host "Warning: Function test failed" -ForegroundColor Yellow
        }
        
    } else {
        Write-Host "Failed to deploy Lambda function!" -ForegroundColor Red
        exit 1
    }

} catch {
    Write-Host "Error during deployment: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    # Clean up temp files
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
}

Write-Host "Deployment completed!" -ForegroundColor Green
Write-Host "Lambda Function: $LambdaName" -ForegroundColor Yellow
Write-Host "Website Bucket: $BucketPrefix-sam-website-$Environment" -ForegroundColor Yellow