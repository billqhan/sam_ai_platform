# Sync Lambda environment variables from .env.dev

param(
  [string]$Environment = "dev",
  [string]$BucketPrefix = "dev",
  [string]$Region = "us-east-1",
  [string]$FunctionLogical = "sam-gov-daily-download",
  [switch]$All,
  [string]$EnvFile = "../.env.dev"
)

$ErrorActionPreference = "Stop"

function Read-DotEnv($path) {
  if (-not (Test-Path $path)) { throw ".env file not found: $path" }
  $map = @{}
  Get-Content -LiteralPath $path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    if ($line -like 'export *') { $line = $line.Substring(6).Trim() }
    $eq = $line.IndexOf('=')
    if ($eq -lt 1) { return }
    $k = $line.Substring(0, $eq).Trim()
    $v = $line.Substring($eq+1).Trim()
    # strip inline comments starting with space-hash first
    $hashIx = $v.IndexOf(' #')
    if ($hashIx -ge 0) { $v = $v.Substring(0, $hashIx).Trim() }
    # then remove surrounding quotes if present
    if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Trim('"') }
    $map[$k] = $v
  }
  return $map
}

# Resolve repo root relative to this script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$envPath = if (Test-Path (Join-Path $RepoRoot ".env.dev")) { Join-Path $RepoRoot ".env.dev" } else { (Resolve-Path $EnvFile) }
$envMap = Read-DotEnv $envPath

if (-not $Environment) { $Environment = $envMap['ENVIRONMENT'] }
if (-not $BucketPrefix) { $BucketPrefix = $envMap['BUCKET_PREFIX'] }
if (-not $Region) { $Region = $envMap['REGION'] }


function Get-FullName([string]$logical) {
  if ($BucketPrefix) { return "$BucketPrefix-$logical-$Environment" } else { return "$logical-$Environment" }
}

function Resolve-Vars([string]$val, $vars) {
  if (-not $val) { return $val }
  $out = $val
  foreach ($k in $vars.Keys) {
    $needle = '${' + $k + '}'
    $out = $out.Replace($needle, $vars[$k])
  }
  return $out
}

function Build-DesiredForFunction([string]$logical) {
  $d = @{}
  switch ($logical) {
    'sam-gov-daily-download' {
      if ($envMap.ContainsKey('SAM_API_KEY')) { $d['SAM_API_KEY'] = $envMap['SAM_API_KEY'] }
      if ($envMap.ContainsKey('SAM_API_URL')) { $d['SAM_API_URL'] = $envMap['SAM_API_URL'] }
      if ($envMap.ContainsKey('SAM_DATA_IN_BUCKET')) { $d['OUTPUT_BUCKET'] = Resolve-Vars $envMap['SAM_DATA_IN_BUCKET'] $envMap }
      if ($envMap.ContainsKey('SAM_DOWNLOAD_LOGS_BUCKET')) { $d['LOG_BUCKET'] = Resolve-Vars $envMap['SAM_DOWNLOAD_LOGS_BUCKET'] $envMap }
      foreach ($k in @('API_LIMIT','OVERRIDE_DATE_FORMAT','OVERRIDE_POSTED_FROM','OVERRIDE_POSTED_TO')) { if ($envMap.ContainsKey($k)) { $d[$k] = $envMap[$k] } }
    }
    'sam-json-processor' {
      if ($envMap.ContainsKey('SAM_EXTRACTED_JSON_BUCKET')) {
        $bucket = Resolve-Vars $envMap['SAM_EXTRACTED_JSON_BUCKET'] $envMap
        $d['OUTPUT_BUCKET'] = $bucket
        $d['SAM_EXTRACTED_JSON_RESOURCES_BUCKET'] = $bucket
      }
    }
    'sam-sqs-generate-match-reports' {
      if ($envMap.ContainsKey('BEDROCK_REGION')) { $d['BEDROCK_REGION'] = $envMap['BEDROCK_REGION'] } else { $d['BEDROCK_REGION'] = $Region }
      if ($envMap.ContainsKey('KNOWLEDGE_BASE_ID')) { $d['KNOWLEDGE_BASE_ID'] = $envMap['KNOWLEDGE_BASE_ID'] }
      if ($envMap.ContainsKey('MATCH_THRESHOLD')) { $d['MATCH_THRESHOLD'] = $envMap['MATCH_THRESHOLD'] }
      if ($envMap.ContainsKey('SAM_MATCHING_OUT_SQS_BUCKET')) { $d['OUTPUT_BUCKET_SQS'] = Resolve-Vars $envMap['SAM_MATCHING_OUT_SQS_BUCKET'] $envMap }
      if ($envMap.ContainsKey('SAM_MATCHING_OUT_RUNS_BUCKET')) { $d['OUTPUT_BUCKET_RUNS'] = Resolve-Vars $envMap['SAM_MATCHING_OUT_RUNS_BUCKET'] $envMap }
      if ($envMap.ContainsKey('MAX_ATTACHMENT_FILES')) { $d['MAX_ATTACHMENT_FILES'] = $envMap['MAX_ATTACHMENT_FILES'] }
      if ($envMap.ContainsKey('MAX_DESCRIPTION_CHARS')) { $d['MAX_DESCRIPTION_CHARS'] = $envMap['MAX_DESCRIPTION_CHARS'] }
      if ($envMap.ContainsKey('MODEL_ID_DESC')) { $d['MODEL_ID_DESC'] = $envMap['MODEL_ID_DESC'] }
      if ($envMap.ContainsKey('MODEL_ID_MATCH')) { $d['MODEL_ID_MATCH'] = $envMap['MODEL_ID_MATCH'] }
    }
    'sam-produce-user-report' {
      if ($envMap.ContainsKey('SAM_OPPORTUNITY_RESPONSES_BUCKET')) {
        $bucket = Resolve-Vars $envMap['SAM_OPPORTUNITY_RESPONSES_BUCKET'] $envMap
        $d['OUTPUT_BUCKET'] = $bucket
        $d['DESTINATION_BUCKET'] = $bucket
        $d['SAM_OPPORTUNITY_RESPONSES_BUCKET'] = $bucket
      }
      if ($envMap.ContainsKey('SAM_MATCHING_OUT_SQS_BUCKET')) { $d['SAM_MATCHING_OUT_SQS_BUCKET'] = Resolve-Vars $envMap['SAM_MATCHING_OUT_SQS_BUCKET'] $envMap }
      if ($envMap.ContainsKey('COMPANY_NAME')) { $d['COMPANY_NAME'] = $envMap['COMPANY_NAME'] }
      if ($envMap.ContainsKey('COMPANY_CONTACT')) { $d['COMPANY_CONTACT'] = $envMap['COMPANY_CONTACT'] }
    }
    'sam-merge-and-archive-result-logs' {
      if ($envMap.ContainsKey('SAM_MATCHING_OUT_RUNS_BUCKET')) { $d['S3_OUT_BUCKET'] = Resolve-Vars $envMap['SAM_MATCHING_OUT_RUNS_BUCKET'] $envMap }
    }
    'sam-produce-web-reports' {
      if ($envMap.ContainsKey('SAM_WEBSITE_BUCKET')) {
        $wb = Resolve-Vars $envMap['SAM_WEBSITE_BUCKET'] $envMap
        $d['WEBSITE_BUCKET'] = $wb; $d['SAM_WEBSITE_BUCKET'] = $wb
      }
      if ($envMap.ContainsKey('SAM_MATCHING_OUT_RUNS_BUCKET')) { $d['SAM_MATCHING_OUT_RUNS_BUCKET'] = Resolve-Vars $envMap['SAM_MATCHING_OUT_RUNS_BUCKET'] $envMap }
    }
    'sam-daily-email-notification' {
      if ($envMap.ContainsKey('ENABLE_NOTIFICATIONS')) { $d['EMAIL_ENABLED'] = $envMap['ENABLE_NOTIFICATIONS'] }
      if ($envMap.ContainsKey('REGION')) { $d['SES_REGION'] = $envMap['REGION'] }
      if ($envMap.ContainsKey('EMAIL_FROM')) { $d['FROM_EMAIL'] = $envMap['EMAIL_FROM'] }
      if ($envMap.ContainsKey('SAM_OPPORTUNITY_RESPONSES_BUCKET')) { $d['OPPORTUNITY_RESPONSES_BUCKET'] = Resolve-Vars $envMap['SAM_OPPORTUNITY_RESPONSES_BUCKET'] $envMap }
      if ($envMap.ContainsKey('SAM_WEBSITE_BUCKET')) { $d['WEBSITE_BUCKET'] = Resolve-Vars $envMap['SAM_WEBSITE_BUCKET'] $envMap }
    }
    default { }
  }
  return $d
}

function Update-One([string]$logical) {
  $fullName = Get-FullName $logical
  Write-Host "[INFO] Updating env for: $fullName ($Region)" -ForegroundColor Cyan
  $desired = Build-DesiredForFunction $logical
  if ($desired.Keys.Count -eq 0) { Write-Host "[WARN] No relevant keys for $logical, skipping" -ForegroundColor Yellow; return }

  $awsFlags = @('--region', $Region)
  if ($env:AWS_INSECURE_SSL -eq 'true') { $awsFlags += '--no-verify-ssl' }
  $currentCfg = aws lambda get-function-configuration --function-name $fullName @awsFlags | ConvertFrom-Json
  $current = @{}
  if ($currentCfg.Environment -and $currentCfg.Environment.Variables) { $current = $currentCfg.Environment.Variables }
  $merged = @{}
  $current.PSObject.Properties | ForEach-Object { $merged[$_.Name] = $_.Value }
  $desired.Keys | ForEach-Object { $merged[$_] = $desired[$_] }
  $payload = @{ Variables = $merged } | ConvertTo-Json -Depth 5
  $tmp = [System.IO.Path]::GetTempFileName()
  [System.IO.File]::WriteAllText($tmp, $payload, [System.Text.UTF8Encoding]::new($false))
  Write-Host "[INFO] Applying environment update..." -ForegroundColor Blue
  aws lambda update-function-configuration --function-name $fullName --environment file://$tmp @awsFlags | Out-Null
  if ($LASTEXITCODE -eq 0) { Write-Host "[SUCCESS] Updated environment variables for $fullName" -ForegroundColor Green } else { Write-Host "[ERROR] Failed to update environment for $fullName" -ForegroundColor Red }
  Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue
}

if ($All) {
  $targets = @(
    'sam-gov-daily-download',
    'sam-json-processor',
    'sam-sqs-generate-match-reports',
    'sam-produce-user-report',
    'sam-merge-and-archive-result-logs',
    'sam-produce-web-reports',
    'sam-daily-email-notification'
  )
  foreach ($t in $targets) { Update-One $t }
} else {
  Update-One $FunctionLogical
}
