# Generate web reports and send email notification
param(
  [string]$Region = "us-east-1",
  [string]$BucketPrefix = "l3harris-qhan",
  [string]$Env = "dev"
)

$RunsBucket = "$BucketPrefix-sam-matching-out-runs-$Env"
$MatchBucket = "$BucketPrefix-sam-matching-out-sqs-$Env"
$WebsiteFunction = "$BucketPrefix-sam-produce-web-reports-$Env"
$MergeFunction = "$BucketPrefix-sam-merge-and-archive-result-logs-$Env"
$EmailFunction = "$BucketPrefix-sam-daily-email-notification-$Env"
$UserReportFunction = "$BucketPrefix-sam-produce-user-report-$Env"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GENERATING REPORTS & NOTIFICATIONS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Merge and archive result logs
Write-Host "[1/4] Merging and archiving result logs..." -ForegroundColor Yellow
aws lambda invoke `
  --function-name $MergeFunction `
  --region $Region `
  merge-response.json | Out-Null

$mergeResult = Get-Content merge-response.json | ConvertFrom-Json
Write-Host "  Status: $($mergeResult.statusCode)" -ForegroundColor Green

# Discover latest merged run file in runs/ prefix (e.g., runs/20251029T2130Z.json)
Write-Host "  Locating latest merged run file in s3://$RunsBucket/runs/ ..." -ForegroundColor Gray
$latestRunKey = aws s3api list-objects-v2 `
  --bucket $RunsBucket `
  --prefix "runs/" `
  --query "reverse(sort_by(Contents[?starts_with(Key, 'runs/2')], &LastModified))[0].Key" `
  --output text

if (-not $latestRunKey -or $latestRunKey -eq "None") {
  Write-Host "  No merged run files found. Cannot generate website." -ForegroundColor Red
} else {
  Write-Host "  Latest run file: $latestRunKey" -ForegroundColor Green
}
Write-Host ""

# Step 2: Generate web reports using a synthetic S3 event for the latest run file
Write-Host "[2/4] Generating web reports and dashboard..." -ForegroundColor Yellow
if ($latestRunKey -and $latestRunKey -ne "None") {
  $s3Event = @{
    Records = @(
      @{ eventSource = "aws:s3"; s3 = @{ bucket = @{ name = $RunsBucket }; object = @{ key = $latestRunKey } } }
    )
  } | ConvertTo-Json -Depth 5
  $s3Event | Out-File -FilePath web-event.json -Encoding utf8

  aws lambda invoke `
    --function-name $WebsiteFunction `
    --region $Region `
    --payload fileb://web-event.json `
    web-response.json | Out-Null
} else {
  # Fallback: still invoke without payload (will likely return no-op)
  aws lambda invoke `
    --function-name $WebsiteFunction `
    --region $Region `
    web-response.json | Out-Null
}

$webResult = Get-Content web-response.json | ConvertFrom-Json
Write-Host "  Status: $($webResult.statusCode)" -ForegroundColor Green
if ($webResult.body) {
  $body = $webResult.body | ConvertFrom-Json
  Write-Host "  Message: $($body.message)" -ForegroundColor Green
  if ($body.dashboard_paths) { Write-Host "  Dashboards: $($body.dashboard_paths -join ', ')" -ForegroundColor Green }
}
Write-Host ""

# Step 3: Generate user response templates for today's matches (if any)
Write-Host "[3/4] Generating user response templates (matches only)..." -ForegroundColor Yellow
$today = (Get-Date).ToString('yyyy-MM-dd')
$matchPrefix = "$today/matches/"

$matchKeys = aws s3api list-objects-v2 `
  --bucket $MatchBucket `
  --prefix $matchPrefix `
  --query "Contents[].Key" `
  --output json | ConvertFrom-Json

if ($matchKeys -and $matchKeys.Count -gt 0) {
  Write-Host "  Found $($matchKeys.Count) match file(s). Invoking user-report lambda..." -ForegroundColor Green
  $processed = 0
  foreach ($k in $matchKeys) {
    $evt = @{
      Records = @(
        @{ eventSource = "aws:s3"; s3 = @{ bucket = @{ name = $MatchBucket }; object = @{ key = $k } } }
      )
    } | ConvertTo-Json -Depth 5
    $evt | Out-File -FilePath user-report-event.json -Encoding utf8

    aws lambda invoke `
      --function-name $UserReportFunction `
      --region $Region `
      --payload fileb://user-report-event.json `
      ur-response.json | Out-Null

    $processed++
    if ($processed -ge 20) { break }  # safety cap
  }
  Write-Host "  Invoked user-report for $processed file(s)." -ForegroundColor Green
} else {
  Write-Host "  No matches found for $today (MATCH_THRESHOLD may be high). Skipping user responses." -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Send email notifications
Write-Host "[4/4] Sending email notifications..." -ForegroundColor Yellow
aws lambda invoke `
  --function-name $EmailFunction `
  --region $Region `
  email-response.json | Out-Null

$emailResult = Get-Content email-response.json | ConvertFrom-Json
Write-Host "  Status: $($emailResult.statusCode)" -ForegroundColor Green
if ($emailResult.body) {
  $body = $emailResult.body | ConvertFrom-Json
  Write-Host "  Message: $($body.message)" -ForegroundColor Green
}

Write-Host "" 
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PROCESS COMPLETE!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Website bucket to check:  s3://$BucketPrefix-sam-website-$Env/dashboards/" -ForegroundColor Gray
Write-Host "Opportunity responses bucket: s3://$BucketPrefix-sam-opportunity-responses-$Env/" -ForegroundColor Gray
Write-Host "Review CloudWatch logs for details if needed." -ForegroundColor Gray
