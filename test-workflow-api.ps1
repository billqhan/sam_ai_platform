# Test Workflow API Endpoint
param(
    [string]$ApiUrl = "https://i7bz81i0l1.execute-api.us-east-1.amazonaws.com/dev",
    [string]$Step = "download"
)

$ErrorActionPreference = 'Continue'

Write-Host "`n=== Testing Workflow API ===" -ForegroundColor Cyan
Write-Host "API URL: $ApiUrl" -ForegroundColor Gray
Write-Host "Step: $Step`n" -ForegroundColor Gray

# Test 1: Check if API Gateway is accessible
Write-Host "[1] Testing API Gateway health..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-WebRequest -Uri "$ApiUrl/health" -Method GET -UseBasicParsing -TimeoutSec 10
    Write-Host "    ✓ API Gateway is accessible" -ForegroundColor Green
    Write-Host "    Status: $($healthResponse.StatusCode)" -ForegroundColor Gray
} catch {
    Write-Host "    ✗ API Gateway not accessible" -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Test workflow endpoint
Write-Host "`n[2] Testing workflow/$Step endpoint..." -ForegroundColor Yellow
try {
    $body = @{} | ConvertTo-Json
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    $response = Invoke-WebRequest `
        -Uri "$ApiUrl/workflow/$Step" `
        -Method POST `
        -Body $body `
        -Headers $headers `
        -UseBasicParsing `
        -TimeoutSec 30
    
    Write-Host "    ✓ Workflow request succeeded" -ForegroundColor Green
    Write-Host "    Status: $($response.StatusCode)" -ForegroundColor Gray
    Write-Host "    Response:" -ForegroundColor Gray
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5 | Write-Host -ForegroundColor Gray
    
} catch {
    Write-Host "    ✗ Workflow request failed" -ForegroundColor Red
    Write-Host "    Status: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "    Response Body: $responseBody" -ForegroundColor Red
    }
}

# Test 3: Check workflow status
Write-Host "`n[3] Testing workflow/status endpoint..." -ForegroundColor Yellow
try {
    $statusResponse = Invoke-WebRequest -Uri "$ApiUrl/workflow/status" -Method GET -UseBasicParsing -TimeoutSec 10
    Write-Host "    ✓ Status endpoint accessible" -ForegroundColor Green
    $statusResponse.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5 | Write-Host -ForegroundColor Gray
} catch {
    Write-Host "    ✗ Status endpoint failed" -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Test Complete ===`n" -ForegroundColor Cyan
