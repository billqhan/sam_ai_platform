# Lambda Function Packaging Script
# This script packages Lambda functions with their dependencies

param(
    [Parameter(Mandatory=$true)]
    [string]$LambdaName,
    
    [Parameter(Mandatory=$true)]
    [string]$SourcePath,
    
    [Parameter(Mandatory=$true)]
    [string]$S3Bucket,
    
    [Parameter(Mandatory=$false)]
    [string]$S3KeyPrefix = "lambda-packages",
    
    [Parameter(Mandatory=$false)]
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"

Write-Host "[INFO] Packaging Lambda function: $LambdaName" -ForegroundColor Blue
Write-Host "  Source Path: $SourcePath"
Write-Host "  S3 Bucket: $S3Bucket"
Write-Host "  S3 Key Prefix: $S3KeyPrefix"

# Create temporary directory for packaging
$TempDir = Join-Path $env:TEMP "lambda-package-$(Get-Random)"
$PackageDir = Join-Path $TempDir "package"
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

try {
    # Copy source files to package directory
    Write-Host "[INFO] Copying source files..." -ForegroundColor Blue
    Copy-Item -Path "$SourcePath\*" -Destination $PackageDir -Recurse -Force
    
    # Check if requirements.txt exists
    $RequirementsFile = Join-Path $PackageDir "requirements.txt"
    if (Test-Path $RequirementsFile) {
        Write-Host "[INFO] Installing dependencies from requirements.txt..." -ForegroundColor Blue
        
        # Install dependencies to package directory
        & python -m pip install -r $RequirementsFile -t $PackageDir --platform linux_x86_64 --only-binary=:all:
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
        
        # Remove unnecessary files
        Get-ChildItem -Path $PackageDir -Recurse -Include "*.pyc", "__pycache__", "*.dist-info", "*.egg-info" | Remove-Item -Recurse -Force
        Remove-Item -Path $RequirementsFile -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[INFO] No requirements.txt found, packaging source only..." -ForegroundColor Yellow
    }
    
    # Create ZIP file
    $ZipFile = Join-Path $TempDir "$LambdaName.zip"
    Write-Host "[INFO] Creating ZIP package..." -ForegroundColor Blue
    
    # Use PowerShell's Compress-Archive
    Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipFile -Force
    
    # Upload to S3
    $S3Key = "$S3KeyPrefix/$LambdaName.zip"
    Write-Host "[INFO] Uploading to S3: s3://$S3Bucket/$S3Key" -ForegroundColor Blue
    
    aws s3 cp $ZipFile "s3://$S3Bucket/$S3Key"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to upload to S3" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[SUCCESS] Lambda function packaged and uploaded successfully!" -ForegroundColor Green
    Write-Host "  S3 Location: s3://$S3Bucket/$S3Key" -ForegroundColor Green
    
    # Return S3 location for use in other scripts
    return @{
        S3Bucket = $S3Bucket
        S3Key = $S3Key
        S3Url = "https://$S3Bucket.s3.amazonaws.com/$S3Key"
    }
    
} finally {
    # Clean up temporary directory
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}