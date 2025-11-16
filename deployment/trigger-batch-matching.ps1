# Trigger batch matching for opportunities
param(
        [int]$Count = 5,
        [string]$Region,
        [string]$BucketPrefix,
        [string]$Env,
        [string]$Date
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
if (-not $Date)         { $Date         = (Get-Date).ToString('yyyy-MM-dd') }

$ExtractedBucket = "$BucketPrefix-sam-extracted-json-resources-$Env"
$MatchFn = "$BucketPrefix-sam-sqs-generate-match-reports-$Env"

$opportunities = aws s3 ls "s3://$ExtractedBucket/$Date/" --region $Region | 
    ForEach-Object { if ($_ -match 'PRE (.+)/') { $matches[1] } } | 
    Select-Object -First $Count

Write-Host "Processing $($opportunities.Count) opportunities..."

foreach ($opp in $opportunities) {
    Write-Host "  Triggering: $opp"
    
    $s3Event = @{
        Records = @(
            @{
                s3 = @{
                    bucket = @{ name = $ExtractedBucket }
                    object = @{ key = "$Date/$opp/${opp}_opportunity.json" }
                }
            }
        )
    } | ConvertTo-Json -Depth 10 -Compress
    
    $sqsEvent = @{
        Records = @(
            @{
                body = $s3Event
                messageId = "batch-$opp"
            }
        )
    } | ConvertTo-Json -Depth 10
    
    $sqsEvent | Out-File -Encoding UTF8 -FilePath "$env:TEMP\match-$opp.json"
    
    aws lambda invoke `
        --function-name $MatchFn `
        --payload fileb://$env:TEMP/match-$opp.json `
        --invocation-type Event `
        --region $Region `
        "$env:TEMP\response-$opp.json" | Out-Null
    
    Write-Host "    Invoked (async)"
    Start-Sleep -Milliseconds 500
}

Write-Host "`nAll opportunities queued for processing!"
Write-Host "Processing will take ~65 seconds per opportunity"
Write-Host "Check logs in 5-10 minutes for results"
