# Test Merge and Archive Lambda Function
# This script tests the deployed merge and archive lambda function

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev",
    
    [Parameter(Mandatory=$false)]
    [string]$BucketPrefix = "ktest"
)

$ErrorActionPreference = "Stop"

$LambdaName = "sam-merge-and-archive-result-logs"
$FullFunctionName = "$BucketPrefix-$LambdaName-$Environment"
$S3Bucket = "$BucketPrefix-sam-matching-out-runs-$Environment"

Write-Host "=== Testing Merge and Archive Lambda Function ===" -ForegroundColor Cyan
Write-Host "Function Name: $FullFunctionName" -ForegroundColor White
Write-Host "S3 Bucket: $S3Bucket" -ForegroundColor White
Write-Host ""

# Check if function exists
Write-Host "[INFO] Checking if Lambda function exists..." -ForegroundColor Blue
try {
    $FunctionInfo = aws lambda get-function --function-name $FullFunctionName --region us-east-1 | ConvertFrom-Json
    Write-Host "[SUCCESS] Function found!" -ForegroundColor Green
    Write-Host "  Runtime: $($FunctionInfo.Configuration.Runtime)" -ForegroundColor White
    Write-Host "  Handler: $($FunctionInfo.Configuration.Handler)" -ForegroundColor White
    Write-Host "  Memory: $($FunctionInfo.Configuration.MemorySize) MB" -ForegroundColor White
    Write-Host "  Timeout: $($FunctionInfo.Configuration.Timeout) seconds" -ForegroundColor White
} catch {
    Write-Host "[ERROR] Function not found: $FullFunctionName" -ForegroundColor Red
    exit 1
}

# Check environment variables
Write-Host ""
Write-Host "[INFO] Checking environment variables..." -ForegroundColor Blue
$EnvVars = $FunctionInfo.Configuration.Environment.Variables
if ($EnvVars.S3_OUT_BUCKET) {
    Write-Host "[SUCCESS] S3_OUT_BUCKET: $($EnvVars.S3_OUT_BUCKET)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] S3_OUT_BUCKET environment variable not set" -ForegroundColor Red
}

if ($EnvVars.active) {
    Write-Host "[SUCCESS] active: $($EnvVars.active)" -ForegroundColor Green
} else {
    Write-Host "[WARNING] active environment variable not set (will default to false)" -ForegroundColor Yellow
}

# Check S3 bucket exists
Write-Host ""
Write-Host "[INFO] Checking S3 bucket..." -ForegroundColor Blue
try {
    aws s3 ls "s3://$S3Bucket/" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] S3 bucket exists: $S3Bucket" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] S3 bucket not accessible: $S3Bucket" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Failed to check S3 bucket: $S3Bucket" -ForegroundColor Red
}

# Check EventBridge rule
Write-Host ""
Write-Host "[INFO] Checking EventBridge rule..." -ForegroundColor Blue
$RuleName = "sam-lambda-every-5min-summarizer-$Environment"
try {
    $RuleInfo = aws events describe-rule --name $RuleName --region us-east-1 | ConvertFrom-Json
    Write-Host "[SUCCESS] EventBridge rule found: $RuleName" -ForegroundColor Green
    Write-Host "  Schedule: $($RuleInfo.ScheduleExpression)" -ForegroundColor White
    Write-Host "  State: $($RuleInfo.State)" -ForegroundColor White
    
    # Check rule targets
    $Targets = aws events list-targets-by-rule --rule $RuleName --region us-east-1 | ConvertFrom-Json
    $LambdaTarget = $Targets.Targets | Where-Object { $_.Arn -like "*$FullFunctionName*" }
    if ($LambdaTarget) {
        Write-Host "[SUCCESS] Lambda function is configured as target" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Lambda function not found in rule targets" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] EventBridge rule not found: $RuleName" -ForegroundColor Red
}

# Test function invocation
Write-Host ""
Write-Host "[INFO] Testing function invocation..." -ForegroundColor Blue
try {
    $TestPayload = '{"source": "test", "detail-type": "Scheduled Event"}'
    aws lambda invoke --function-name $FullFunctionName --region us-east-1 --payload $TestPayload response.json | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Function invocation successful!" -ForegroundColor Green
        if (Test-Path "response.json") {
            $Response = Get-Content "response.json" | ConvertFrom-Json
            Write-Host "Response:" -ForegroundColor White
            Write-Host ($Response | ConvertTo-Json -Depth 3) -ForegroundColor White
            Remove-Item "response.json" -Force
        }
    } else {
        Write-Host "[ERROR] Function invocation failed" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] Failed to invoke function" -ForegroundColor Red
}

Write-Host ""
Write-Host "[INFO] Test completed!" -ForegroundColor Green