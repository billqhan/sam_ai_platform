# Complete End-to-End Workflow Runner
# This script executes the entire RFP response pipeline

param(
    [int]$OpportunitiesToProcess = 10,
    [switch]$SkipDownload,
    [switch]$WaitForCompletion
)

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
        --function-name l3harris-qhan-sam-gov-daily-download-dev `
        --region us-east-1 `
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
                    bucket = @{ name = "l3harris-qhan-sam-data-in-dev" }
                    object = @{ key = $samFile }
                }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $s3Event | Out-File -Encoding UTF8 -FilePath "$env:TEMP\s3-event.json"
    
    aws lambda invoke `
        --function-name l3harris-qhan-sam-json-processor-dev `
        --payload fileb://$env:TEMP/s3-event.json `
        --region us-east-1 `
        process-response.json | Out-Null
    
    Start-Sleep -Seconds 120  # Wait for processing
    
    # Check logs for result
    $processLogs = aws logs tail "/aws/lambda/l3harris-qhan-sam-json-processor-dev" --since 5m --region us-east-1 2>&1 | 
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

.\trigger-batch-matching.ps1 -Count $OpportunitiesToProcess
Write-Host ""

if ($WaitForCompletion) {
    Write-Host "  ⏳ Waiting for matching to complete (~65 sec per opportunity)..." -ForegroundColor Gray
    $expectedTime = [math]::Ceiling($OpportunitiesToProcess * 65 / 60)
    Write-Host "  ⏰ Estimated time: $expectedTime minutes`n" -ForegroundColor Gray
    
    for ($i = 1; $i -le $expectedTime * 2; $i++) {
        $completed = (aws s3 ls s3://l3harris-qhan-sam-matching-out-sqs-dev/2025-10-29/ --recursive --region us-east-1 | Measure-Object).Count
        $progress = [math]::Round(($completed / $OpportunitiesToProcess) * 100)
        Write-Host "  Progress: $completed/$OpportunitiesToProcess ($progress%)" -ForegroundColor Cyan -NoNewline
        
        if ($completed -ge $OpportunitiesToProcess) {
            Write-Host "  ✅" -ForegroundColor Green
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
    --function-name l3harris-qhan-sam-produce-web-reports-dev `
    --region us-east-1 `
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
    --function-name l3harris-qhan-sam-daily-email-notification-dev `
    --region us-east-1 `
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
Write-Host "  • Matching output: s3://l3harris-qhan-sam-matching-out-sqs-dev/" -ForegroundColor Gray
Write-Host "  • Run logs: s3://l3harris-qhan-sam-matching-out-runs-dev/" -ForegroundColor Gray
Write-Host "  • Website: s3://l3harris-qhan-sam-website-dev/" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 Next: Review CloudWatch logs for detailed results" -ForegroundColor Yellow
Write-Host ""
