# Trigger batch matching for opportunities
param(
    [int]$Count = 5
)

$opportunities = aws s3 ls s3://l3harris-qhan-sam-extracted-json-resources-dev/2025-10-29/ --region us-east-1 | 
    ForEach-Object { if ($_ -match 'PRE (.+)/') { $matches[1] } } | 
    Select-Object -First $Count

Write-Host "Processing $($opportunities.Count) opportunities..."

foreach ($opp in $opportunities) {
    Write-Host "  Triggering: $opp"
    
    $s3Event = @{
        Records = @(
            @{
                s3 = @{
                    bucket = @{ name = "l3harris-qhan-sam-extracted-json-resources-dev" }
                    object = @{ key = "2025-10-29/$opp/${opp}_opportunity.json" }
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
        --function-name l3harris-qhan-sam-sqs-generate-match-reports-dev `
        --payload fileb://$env:TEMP/match-$opp.json `
        --invocation-type Event `
        --region us-east-1 `
        "$env:TEMP\response-$opp.json" | Out-Null
    
    Write-Host "    Invoked (async)"
    Start-Sleep -Milliseconds 500
}

Write-Host "`nAll opportunities queued for processing!"
Write-Host "Processing will take ~65 seconds per opportunity"
Write-Host "Check logs in 5-10 minutes for results"
