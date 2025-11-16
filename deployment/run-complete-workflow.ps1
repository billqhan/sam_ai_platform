# Complete End-to-End Workflow Runner
# This script executes the entire RFP response pipeline

param(
        [int]$OpportunitiesToProcess = 10,
        [switch]$SkipDownload,
        [switch]$WaitForCompletion,
        [string]$Region,
        [string]$BucketPrefix,
        [string]$Env
)

# Load .env.dev defaults when parameters are not provided
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$EnvFilePath = Join-Path $RepoRoot ".env.dev"
function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
    $map = @{}
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }
        $k = $line.Substring(0, $eq).Trim().Replace('export ','')
        $v = $line.Substring($eq+1).Trim().Trim('"')
        $map[$k] = $v
    }
    return $map
}

$envMap = Import-DotEnv -Path $EnvFilePath
if (-not $Region)       { $Region       = $envMap['REGION'];        if (-not $Region)       { $Region = 'us-east-1' } }
if (-not $BucketPrefix) { $BucketPrefix = $envMap['BUCKET_PREFIX']; if (-not $BucketPrefix) { $BucketPrefix = 'dev' } }
if (-not $Env)          { $Env          = $envMap['ENVIRONMENT'];   if (-not $Env)          { $Env = 'dev' } }

# Derived names
$DataInBucket   = "$BucketPrefix-sam-data-in-$Env"
$ExtractedBucket= "$BucketPrefix-sam-extracted-json-resources-$Env"
$MatchingSqs    = "$BucketPrefix-sam-matching-out-sqs-$Env"
$RunsBucket     = "$BucketPrefix-sam-matching-out-runs-$Env"
$WebsiteBucket  = "$BucketPrefix-sam-website-$Env"

$DownloadFn = "$BucketPrefix-sam-gov-daily-download-$Env"
$ProcessorFn = "$BucketPrefix-sam-json-processor-$Env"
$MatchFn = "$BucketPrefix-sam-sqs-generate-match-reports-$Env"
$WebFn = "$BucketPrefix-sam-produce-web-reports-$Env"
$EmailFn = "$BucketPrefix-sam-daily-email-notification-$Env"

$ErrorActionPreference = "Continue"

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AI-POWERED RFP RESPONSE AGENT - FULL WORKFLOW      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Download from SAM.gov
if (-not $SkipDownload) {
    Write-Host "[1/5] Downloading opportunities from SAM.gov..." -ForegroundColor Yellow
    aws lambda invoke `
        --function-name $DownloadFn `
        --region $Region `
        download-response.json | Out-Null
    
    $downloadResult = Get-Content download-response.json | ConvertFrom-Json
    if ($downloadResult.statusCode -eq 200) {
        $downloadBody = $downloadResult.body | ConvertFrom-Json
        Write-Host "  ✅ Downloaded: $($downloadBody.opportunitiesCount) opportunities" -ForegroundColor Green
        Write-Host "  📄 File: $($downloadBody.s3ObjectKey)" -ForegroundColor Gray
        $samFile = $downloadBody.s3ObjectKey
    } else {
        Write-Host "  ❌ Download failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    
    # Step 2: Process JSON
    Write-Host "[2/5] Extracting individual opportunities..." -ForegroundColor Yellow
    Write-Host "  ⏳ This may take 2-5 minutes..." -ForegroundColor Gray
    
    $s3Event = @{
        Records = @(
            @{
                s3 = @{
                    bucket = @{ name = $DataInBucket }
                    object = @{ key = $samFile }
                }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $s3Event | Out-File -Encoding UTF8 -FilePath "$env:TEMP\s3-event.json"
    
    aws lambda invoke `
        --function-name $ProcessorFn `
        --payload fileb://$env:TEMP/s3-event.json `
        --region $Region `
        process-response.json | Out-Null
    
    Start-Sleep -Seconds 120  # Wait for processing
    
    # Check logs for result
    $processLogs = aws logs tail "/aws/lambda/$ProcessorFn" --since 5m --region $Region 2>&1 | 
        Select-String "total_opportunities" | Select-Object -Last 1
    
    if ($processLogs) {
        Write-Host "  ✅ Extraction complete" -ForegroundColor Green
        Write-Host "  $processLogs" -ForegroundColor Gray
    }
    Write-Host ""
}

# Step 3: AI Matching Analysis
Write-Host "[3/5] Running AI matching analysis..." -ForegroundColor Yellow
Write-Host "  🤖 Processing $OpportunitiesToProcess opportunities with Bedrock..." -ForegroundColor Gray

.\trigger-batch-matching.ps1 -Count $OpportunitiesToProcess -Region $Region -BucketPrefix $BucketPrefix -Env $Env
Write-Host ""

if ($WaitForCompletion) {
    Write-Host "  ⏳ Waiting for matching to complete (~65 sec per opportunity)..." -ForegroundColor Gray
    $expectedTime = [math]::Ceiling($OpportunitiesToProcess * 65 / 60)
    Write-Host "  Estimated time: $expectedTime minutes" -ForegroundColor Gray
    Write-Host ""
    
    $today = (Get-Date).ToString('yyyy-MM-dd')
    for ($i = 1; $i -le $expectedTime * 2; $i++) {
        $completed = (aws s3 ls "s3://$MatchingSqs/$today/" --recursive --region $Region | Measure-Object).Count
        $progressPct = [math]::Round(($completed / $OpportunitiesToProcess) * 100)
        $progressMsg = "  Progress: $completed/$OpportunitiesToProcess ($progressPct percent)"
        Write-Host $progressMsg -ForegroundColor Cyan -NoNewline
        
        if ($completed -ge $OpportunitiesToProcess) {
            Write-Host " [DONE]" -ForegroundColor Green
            break
        }
        
        Write-Host "`r" -NoNewline
        Start-Sleep -Seconds 30
    }
    Write-Host ""
}

# Step 4: Generate Reports
Write-Host "[4/5] Generating web reports and dashboards..." -ForegroundColor Yellow
aws lambda invoke `
    --function-name $WebFn `
    --region $Region `
    web-response.json | Out-Null

$webResult = Get-Content web-response.json | ConvertFrom-Json
if ($webResult.statusCode -eq 200) {
    Write-Host "  ✅ Web reports generated" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Web reports may be incomplete" -ForegroundColor Yellow
}
Write-Host ""

# Step 5: Send Notifications
Write-Host "[5/5] Sending email notifications..." -ForegroundColor Yellow
aws lambda invoke `
    --function-name $EmailFn `
    --region $Region `
    email-response.json | Out-Null

$emailResult = Get-Content email-response.json | ConvertFrom-Json
if ($emailResult.statusCode -eq 200) {
    Write-Host "  ✅ Email notifications sent" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Email may not have been sent (check SES configuration)" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              WORKFLOW COMPLETE!                       ║" -ForegroundColor Cyan  
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Results:" -ForegroundColor Yellow
Write-Host "  • Matching output: s3://$MatchingSqs/" -ForegroundColor Gray
Write-Host "  • Run logs: s3://$RunsBucket/" -ForegroundColor Gray
Write-Host "  • Website: s3://$WebsiteBucket/" -ForegroundColor Gray
Write-Host ""
Write-Host "Next: Review CloudWatch logs for detailed results" -ForegroundColor Yellow
Write-Host ""
