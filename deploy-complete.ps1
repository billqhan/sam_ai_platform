#requires -Version 5.1
<#!
Deploy Complete (PowerShell)
Windows-native orchestrator to mirror deploy-complete.sh behavior.

Supported actions:
- verify        : Check prerequisites and environment
- infrastructure: Placeholder (infra via Bash/WSL currently); shows guidance
- lambda        : Deploy all Lambda functions
- ui            : Build and deploy the React UI
- java-api      : Build/deploy Java API (best via Bash/WSL; guidance shown)
- eks           : Provision EKS cluster, deploy Java API to Kubernetes, and verify
 - ecs           : Provision ECS (Fargate) for Java API, deploy, and verify
- cloudfront    : Placeholder; show guidance
- test          : Basic smoke checks
- full          : verify -> lambda -> ui (and show guidance for others)

Parameters may be passed or read from .env.dev when present:
- Environment (dev/staging/prod)
- Region (AWS region, e.g., us-east-1)
- BucketPrefix (S3/ECR naming prefix)
- TemplatesBucket (S3 bucket for templates/artifacts)
- SamApiKey (SAM.gov API key)

Usage:
  powershell -File .\deploy-complete.ps1 -Action full -Environment dev -Region us-east-1 -BucketPrefix myprefix
  powershell -File .\deploy-complete.ps1 -Action lambda -Environment dev -Region us-east-1 -BucketPrefix myprefix
  powershell -File .\deploy-complete.ps1 -Action ui
#>

[CmdletBinding()]
param(
  [ValidateSet('verify','infrastructure','lambda','api-gateway','java-api','ui','eks','ecs','cloudfront','test','full')]
  [string]$Action = 'full',
  [string]$Environment,
  [string]$Region,
  [string]$BucketPrefix,
  [string]$TemplatesBucket,
  [string]$SamApiKey,
  [switch]$JavaApiCompose,
  [switch]$PushImage,              # When set with java-api action, push image to ECR
  [switch]$RunContainer,           # When set, run the container after build/push
  [string]$EcrRepository = 'rfp-response-agent-api', # ECR repository name
  [string]$ImageTag = 'latest',    # Tag to apply when pushing
  [switch]$SkipEksProvision,       # Skip EKS infrastructure provisioning
  [switch]$SkipEksDeploy,          # Skip Java API deployment to EKS
  [switch]$SkipEksVerify,          # Skip EKS deployment verification
  [switch]$SkipEcsProvision,       # Skip ECS provisioning
  [switch]$SkipEcsDeploy,          # Skip ECS deploy
  [switch]$SkipEcsVerify           # Skip ECS verification
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Helpers ---
function Write-Header($Text) { Write-Host "`n==== $Text ====\n" -ForegroundColor Cyan }
function Write-Info($Text)   { Write-Host "[i] $Text" -ForegroundColor Gray }
function Write-Ok($Text)     { Write-Host "[OK] $Text" -ForegroundColor Green }
function Write-Warn($Text)   { Write-Host "[!] $Text" -ForegroundColor Yellow }
function Write-Err($Text)    { Write-Host "[x] $Text" -ForegroundColor Red }

function Resolve-RepoRoot {
  param([string]$StartDir)
  $dir = if ($StartDir) { Resolve-Path $StartDir } else { Get-Location }
  while ($dir -and -not (Test-Path (Join-Path $dir '.git'))) {
    $parent = Split-Path $dir -Parent
    if (-not $parent -or $parent -eq $dir) { break }
    $dir = $parent
  }
  if (-not (Test-Path (Join-Path $dir '.git'))) { $dir = Get-Location }
  return (Resolve-Path $dir)
}

$RepoRoot = Resolve-RepoRoot (Get-Location)
Write-Info "Repo root: $RepoRoot"

# --- .env loader (simple KEY=VALUE) ---
function Import-DotEnv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return @{} }
  $map = @{}
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $eq = $line.IndexOf('=')
    if ($eq -lt 1) { return }
    $k = $line.Substring(0, $eq).Trim()
    if ($k -like 'export *') { $k = $k.Substring(7).Trim() }
    $v = $line.Substring($eq+1).Trim().Trim('"')
    $map[$k] = $v
  }
  return $map
}

$envFile = Join-Path $RepoRoot '.env.dev'
$envMap = Import-DotEnv -Path $envFile

# Fill parameters from .env.dev if not provided
if (-not $Environment)    { $Environment    = $envMap['ENVIRONMENT']    ; if (-not $Environment) { $Environment = 'dev' } }
if (-not $Region)         { $Region         = $envMap['REGION']         ; if (-not $Region)      { $Region = 'us-east-1' } }
if (-not $BucketPrefix)   { $BucketPrefix   = $envMap['BUCKET_PREFIX']  }
if (-not $TemplatesBucket){ $TemplatesBucket= $envMap['TEMPLATES_BUCKET'] }
if (-not $SamApiKey)      { $SamApiKey      = $envMap['SAM_API_KEY']    }

Write-Info "Environment: $Environment"
Write-Info "Region     : $Region"
if ($BucketPrefix)   { Write-Info "BucketPrefix   : $BucketPrefix" }
if ($TemplatesBucket){ Write-Info "TemplatesBucket: $TemplatesBucket" }

# Export a few for child processes
$env:ENVIRONMENT = $Environment
$env:REGION = $Region
if ($BucketPrefix)    { $env:BUCKET_PREFIX = $BucketPrefix }
if ($TemplatesBucket) { $env:TEMPLATES_BUCKET = $TemplatesBucket }
if ($SamApiKey)       { $env:SAM_API_KEY = $SamApiKey }

# --- Prereq checks ---
function Test-Cmd($name) { try { $null = Get-Command $name -ErrorAction Stop; $true } catch { $false } }

function Step-Verify {
  Write-Header 'VERIFY PREREQUISITES'
  $checks = @(
    @{ Name='AWS CLI';      Cmd='aws';        Args='--version' },
    @{ Name='Python';       Cmd='python';     Args='--version' },
    @{ Name='Node.js';      Cmd='node';       Args='--version' },
    @{ Name='NPM';          Cmd='npm';        Args='--version' },
    @{ Name='PowerShell';   Cmd=$PSVersionTable.PSVersion.ToString(); Args=$null }
  )
  foreach ($c in $checks) {
    if ($c.Args) {
      if (Test-Cmd $c.Cmd) {
        Write-Ok ("$($c.Name): " + (& $c.Cmd $c.Args 2>&1))
      } else {
        Write-Warn "$($c.Name) not found"
      }
    } else {
      Write-Ok ("PowerShell: " + $c.Cmd)
    }
  }
  if (Test-Cmd 'java') {
    try {
      $j = (& java -version 2>&1 | Select-Object -First 1)
      Write-Ok ("Java: " + $j)
    } catch {
      Write-Warn ("Java detected but version check failed: " + ($_.Exception.Message))
    }
  } else {
    Write-Warn 'Java not found (required for java-api)'
  }
  if (Test-Cmd 'docker') { Write-Ok ("Docker: " + (& docker --version)) } else { Write-Warn 'Docker not found (needed for Java/ECS image builds)'}
}

function Step-Lambda {
  Write-Header 'DEPLOY LAMBDA FUNCTIONS'
  # Ensure templates bucket exists (used by deployment/deploy-all-lambdas.ps1)
  $tb = if ($env:TEMPLATES_BUCKET) { $env:TEMPLATES_BUCKET } elseif ($TemplatesBucket) { $TemplatesBucket } else { 'ai-rfp-templates-dev' }
  try {
    $awsFlags = @('--region', $Region)
    if ($env:AWS_INSECURE_SSL -eq 'true') { $awsFlags += '--no-verify-ssl' }
    & aws s3 ls "s3://$tb" @awsFlags *> $null 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Info "Creating templates bucket: s3://$tb"
      & aws s3 mb "s3://$tb" @awsFlags | Out-Null
    }
  } catch {
    Write-Warn "Could not verify/create templates bucket: s3://$tb"
  }
  $script = Join-Path $RepoRoot 'deployment\deploy-all-lambdas.ps1'
  if (-not (Test-Path $script)) { throw "Missing script: $script" }
  $args = @('-Environment', $Environment, '-Region', $Region)
  if ($BucketPrefix) { $args += @('-BucketPrefix', $BucketPrefix) }
  Write-Info "Running: $script $($args -join ' ')"
  & powershell -ExecutionPolicy Bypass -File $script @args
  Write-Ok 'Lambda deployment completed.'
}

function Step-UI {
  Write-Header 'DEPLOY REACT UI'
  $uiScript = Join-Path $RepoRoot 'ui\deploy.ps1'
  if (Test-Path $uiScript) {
    Write-Info "Running: $uiScript"
    & powershell -ExecutionPolicy Bypass -File $uiScript
  } else {
    Write-Warn 'ui\deploy.ps1 not found. Falling back to npm build only.'
    Push-Location (Join-Path $RepoRoot 'ui')
    try {
      if (-not (Test-Cmd 'npm')) { throw 'npm not found' }
      & npm ci
      & npm run build
      Write-Ok 'UI build completed. Upload to S3 manually if needed.'
    } finally { Pop-Location }
  }
}

function Step-Infrastructure {
  Write-Header 'INFRASTRUCTURE DEPLOYMENT'
  
  if (-not (Test-Cmd 'aws')) {
    Write-Err 'AWS CLI is required for infrastructure deployment'
    return
  }
  
  $cfnDir = Join-Path $RepoRoot 'infrastructure\cloudformation'
  if (-not (Test-Path $cfnDir)) {
    Write-Warn "CloudFormation directory not found: $cfnDir"
    Write-Info 'Skipping infrastructure deployment'
    return
  }
  
  # Check for minimal stack template first (simpler, fewer required params)
  $minimalTemplate = Join-Path $RepoRoot 'infrastructure\minimal-stack.yaml'
  $mainTemplate = $minimalTemplate
  
  if (-not (Test-Path $mainTemplate)) {
    Write-Warn "Minimal template not found: $mainTemplate"
    Write-Info "Trying full lambda-functions.yaml template..."
    $mainTemplate = Join-Path $cfnDir 'lambda-functions.yaml'
    if (-not (Test-Path $mainTemplate)) {
      Write-Warn "No templates found"
      Write-Info 'Available templates:'
      Get-ChildItem -Path $cfnDir -Filter '*.yaml' -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Info "  - $($_.Name)"
      }
      Get-ChildItem -Path (Join-Path $RepoRoot 'infrastructure') -Filter '*.yaml' -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Info "  - infrastructure\$($_.Name)"
      }
      return
    }
  }
  
  # Construct stack name
  $stackName = "$BucketPrefix-sam-infrastructure-$Environment"
  Write-Info "Stack Name: $stackName"
  Write-Info "Template: $mainTemplate"
  
  # Check if stack exists
  $stackExists = $false
  try {
    $null = aws cloudformation describe-stacks --stack-name $stackName --region $Region 2>&1
    if ($LASTEXITCODE -eq 0) {
      $stackExists = $true
      Write-Info "Stack exists - will update"
    }
  } catch {
    Write-Info "Stack does not exist - will create"
  }
  
  # Prepare parameters - only include what template accepts
  $params = @()
  
  # Check what parameters the template accepts
  $templateContent = Get-Content $mainTemplate -Raw
  $hasEnvironmentParam = $templateContent -match 'Environment:\s*\n\s*Type:'
  $hasBucketPrefixParam = $templateContent -match 'BucketPrefix:\s*\n\s*Type:'
  $hasSamApiKeyParam = $templateContent -match 'SamApiKey:\s*\n\s*Type:'
  $hasTemplatesBucketParam = $templateContent -match 'TemplatesBucket:\s*\n\s*Type:'
  
  if ($Environment -and $hasEnvironmentParam) { 
    $params += "ParameterKey=Environment,ParameterValue=$Environment" 
  }
  if ($BucketPrefix -and $hasBucketPrefixParam) { 
    $params += "ParameterKey=BucketPrefix,ParameterValue=$BucketPrefix" 
  }
  if ($SamApiKey -and $hasSamApiKeyParam) { 
    $params += "ParameterKey=SamApiKey,ParameterValue=$SamApiKey" 
  }
  if ($TemplatesBucket -and $hasTemplatesBucketParam) { 
    $params += "ParameterKey=TemplatesBucket,ParameterValue=$TemplatesBucket" 
  }
  
  $awsFlags = @('--region', $Region)
  if ($env:AWS_INSECURE_SSL -eq 'true') { $awsFlags += '--no-verify-ssl' }
  
  # Deploy stack
  try {
    if ($stackExists) {
      Write-Info "Updating CloudFormation stack..."
      $cmdArgs = @(
        'cloudformation', 'update-stack',
        '--stack-name', $stackName,
        '--template-body', "file://$mainTemplate",
        '--capabilities', 'CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'
      )
      if ($params.Count -gt 0) {
        $cmdArgs += '--parameters'
        $cmdArgs += $params
      }
      $cmdArgs += $awsFlags
      
      & aws @cmdArgs
      
      if ($LASTEXITCODE -eq 0) {
        Write-Info "Waiting for stack update to complete..."
        & aws cloudformation wait stack-update-complete --stack-name $stackName @awsFlags
        if ($LASTEXITCODE -eq 0) {
          Write-Ok "Stack updated successfully: $stackName"
        } else {
          Write-Warn "Stack update wait failed - check AWS Console"
        }
      } else {
        Write-Warn "Stack update command failed - may be no changes"
      }
    } else {
      Write-Info "Creating CloudFormation stack..."
      $cmdArgs = @(
        'cloudformation', 'create-stack',
        '--stack-name', $stackName,
        '--template-body', "file://$mainTemplate",
        '--capabilities', 'CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'
      )
      if ($params.Count -gt 0) {
        $cmdArgs += '--parameters'
        $cmdArgs += $params
      }
      $cmdArgs += $awsFlags
      
      & aws @cmdArgs
      
      if ($LASTEXITCODE -eq 0) {
        Write-Info "Waiting for stack creation to complete..."
        & aws cloudformation wait stack-create-complete --stack-name $stackName @awsFlags
        if ($LASTEXITCODE -eq 0) {
          Write-Ok "Stack created successfully: $stackName"
        } else {
          Write-Err "Stack creation failed - check AWS Console"
          return
        }
      } else {
        Write-Err "Stack creation command failed"
        return
      }
    }
    
    # Display stack outputs
    Write-Info "`nStack Outputs:"
    $outputs = aws cloudformation describe-stacks --stack-name $stackName --region $Region --query 'Stacks[0].Outputs' --output table @awsFlags
    Write-Host $outputs
    
  } catch {
    Write-Err "Infrastructure deployment failed: $($_.Exception.Message)"
  }
}

function Step-JavaApi {
  Write-Header 'JAVA API DEPLOYMENT'
  if (-not (Test-Cmd 'docker')) { Write-Err 'Docker is required for container builds'; return }
  $javaApiDir = Join-Path $RepoRoot 'java-api'
  if (-not (Test-Path $javaApiDir)) { Write-Err "Missing directory: $javaApiDir"; return }

  Write-Info "Building Docker image from $javaApiDir"
  Push-Location $javaApiDir
  try {
    & docker build -t rfp-response-agent-api:local .
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed with exit code $LASTEXITCODE" }
    Write-Ok 'Docker image built: rfp-response-agent-api:local'
    # Optional ECR push
    if ($PushImage) {
      if (-not (Test-Cmd 'aws')) { Write-Err 'AWS CLI required for ECR push'; return }
      Write-Info 'Preparing to push image to ECR'
      $accountId = try { aws sts get-caller-identity --query Account --output text } catch { Write-Err 'Failed to get AWS account ID'; return }
      if (-not $accountId) { Write-Err 'Empty AWS account ID'; return }
      $registry = "$accountId.dkr.ecr.$Region.amazonaws.com"
      Write-Info "Ensuring ECR repository exists: $EcrRepository"
      $repoExists = aws ecr describe-repositories --repository-names $EcrRepository 2>$null
      if ($LASTEXITCODE -ne 0) {
        Write-Info "Creating ECR repository $EcrRepository"
        aws ecr create-repository --repository-name $EcrRepository | Out-Null
      }
      Write-Info "Logging into ECR: $registry"
      aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry | Out-Null
      if ($LASTEXITCODE -ne 0) { Write-Err 'Docker login to ECR failed'; return }
      $fullTag = "$registry/${EcrRepository}:$ImageTag"
      Write-Info "Tagging local image as $fullTag"
      docker tag rfp-response-agent-api:local $fullTag
      if ($LASTEXITCODE -ne 0) { Write-Err 'Failed to tag image'; return }
      Write-Info "Pushing image $fullTag"
      docker push $fullTag
      if ($LASTEXITCODE -ne 0) { Write-Err 'Image push failed'; return } else { Write-Ok "Image pushed: $fullTag" }
    }

    # Optional compose or single container run
    if ($JavaApiCompose) {
      if (Test-Path (Join-Path $javaApiDir 'docker-compose.yml')) {
        Write-Info 'Starting docker-compose stack (API + dependencies)...'
        & docker compose up --build -d
        if ($LASTEXITCODE -ne 0) { Write-Warn 'docker compose reported a non-zero exit. Check logs with: docker compose logs -f' }
        else { Write-Ok 'docker-compose stack started. Health: http://localhost:8080/api/health' }
      } else {
        Write-Warn 'docker-compose.yml not found; skipping compose start.'
      }
    } elseif ($RunContainer) {
      $runImage = if ($PushImage) { "$registry/${EcrRepository}:$ImageTag" } else { 'rfp-response-agent-api:local' }
      Write-Info "Running container from image $runImage"
      docker rm -f rfp-response-agent-api 2>$null | Out-Null
      docker run -d --name rfp-response-agent-api -p 8080:8080 $runImage
      if ($LASTEXITCODE -ne 0) { Write-Warn 'Container start failed' } else { Write-Ok 'Container started: http://localhost:8080/api/health' }
    } else {
      Write-Info 'To run locally:'
      Write-Info '  cd java-api; docker run -p 8080:8080 rfp-response-agent-api:local'
      Write-Info 'Or start compose: cd java-api; docker compose up --build'
      Write-Info 'To push to ECR:'
      Write-Info '  .\deploy-complete.ps1 -Action java-api -PushImage -Region us-east-1 -Environment dev'
    }
  }
  finally {
    Pop-Location
  }
}

function Step-EKS {
  Write-Header 'EKS DEPLOYMENT (PROVISION, DEPLOY, VERIFY)'
  
  # Check prerequisites
  if (-not (Test-Cmd 'terraform')) {
    Write-Err 'Terraform is required for EKS provisioning. Install from: https://www.terraform.io/downloads'
    return
  }
  if (-not (Test-Cmd 'kubectl')) {
    Write-Err 'kubectl is required. Install from: https://kubernetes.io/docs/tasks/tools/'
    return
  }
  if (-not (Test-Cmd 'docker')) {
    Write-Err 'Docker is required for building container images'
    return
  }
  
  $eksDir = Join-Path $RepoRoot 'infrastructure\eks'
  $javaApiDir = Join-Path $RepoRoot 'java-api'
  
  if (-not (Test-Path $eksDir)) {
    Write-Err "Missing EKS infrastructure directory: $eksDir"
    return
  }
  if (-not (Test-Path $javaApiDir)) {
    Write-Err "Missing Java API directory: $javaApiDir"
    return
  }
  
  # Step 1: Provision EKS Infrastructure
  if (-not $SkipEksProvision) {
    Write-Header 'Step 1/3: Provisioning EKS Infrastructure'
    Write-Info 'This will create: VPC, EKS cluster, node groups, ECR repository, IAM roles'
    Write-Warn 'This operation takes 15-20 minutes and incurs AWS charges (~$143/month for dev)'
    
    $provisionScript = Join-Path $eksDir 'provision-eks.ps1'
    if (-not (Test-Path $provisionScript)) {
      Write-Err "Missing provision script: $provisionScript"
      return
    }
    
    Push-Location $eksDir
    try {
      Write-Info "Running: $provisionScript -Action apply -Environment $Environment"
      & powershell -ExecutionPolicy Bypass -File $provisionScript -Action apply -Environment $Environment
      if ($LASTEXITCODE -ne 0) {
        Write-Err 'EKS provisioning failed'
        return
      }
      Write-Ok 'EKS infrastructure provisioned successfully'
    }
    finally {
      Pop-Location
    }
  } else {
    Write-Warn 'Skipping EKS provisioning (--SkipEksProvision)'
  }
  
  # Step 2: Deploy Java API to EKS
  if (-not $SkipEksDeploy) {
    Write-Header 'Step 2/3: Deploying Java API to EKS'
    Write-Info 'Building image, pushing to ECR, and deploying to Kubernetes'
    
    $deployScript = Join-Path $javaApiDir 'deploy-eks.ps1'
    if (-not (Test-Path $deployScript)) {
      Write-Err "Missing deploy script: $deployScript"
      return
    }
    
    Push-Location $javaApiDir
    try {
      Write-Info "Running: $deployScript -Environment $Environment"
      & powershell -ExecutionPolicy Bypass -File $deployScript -Environment $Environment
      if ($LASTEXITCODE -ne 0) {
        Write-Err 'Java API deployment to EKS failed'
        return
      }
      Write-Ok 'Java API deployed to EKS successfully'
    }
    finally {
      Pop-Location
    }
  } else {
    Write-Warn 'Skipping Java API deployment (--SkipEksDeploy)'
  }
  
  # Step 3: Verify Deployment
  if (-not $SkipEksVerify) {
    Write-Header 'Step 3/3: Verifying EKS Deployment'
    
    try {
      # Update kubeconfig
      $clusterName = "$Environment-sam-ai-eks"
      Write-Info "Updating kubeconfig for cluster: $clusterName"
      & aws eks update-kubeconfig --region $Region --name $clusterName
      
      # Check cluster info
      Write-Info 'Cluster info:'
      & kubectl cluster-info
      
      # Check pods
      Write-Info "`nPods in sam-ai namespace:"
      & kubectl get pods -n sam-ai
      
      # Check services
      Write-Info "`nServices in sam-ai namespace:"
      & kubectl get svc -n sam-ai
      
      # Get load balancer URL
      Write-Info "`nRetrieving Load Balancer URL..."
      $svcUrl = & kubectl get svc java-api -n sam-ai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>$null
      
      if ($svcUrl) {
        Write-Ok "`nJava API Endpoints:"
        Write-Host "  API:    http://$svcUrl" -ForegroundColor Green
        Write-Host "  Health: http://${svcUrl}:8081/actuator/health" -ForegroundColor Green
        
        # Test health endpoint
        Write-Info "`nTesting health endpoint..."
        Start-Sleep -Seconds 5  # Give LB time to register
        try {
          $response = Invoke-WebRequest -Uri "http://${svcUrl}:8081/actuator/health" -TimeoutSec 10 -UseBasicParsing -ErrorAction SilentlyContinue
          if ($response.StatusCode -eq 200) {
            Write-Ok "Health check passed: HTTP $($response.StatusCode)"
          } else {
            Write-Warn "Health check returned: HTTP $($response.StatusCode)"
          }
        } catch {
          Write-Warn "Health check failed (LB may still be initializing): $($_.Exception.Message)"
          Write-Info "Try again in a few minutes: curl http://${svcUrl}:8081/actuator/health"
        }
      } else {
        Write-Warn 'Load Balancer URL not yet available. It may still be provisioning.'
        Write-Info 'Check status with: kubectl get svc java-api -n sam-ai'
      }
      
      # Show HPA status
      Write-Info "`nHorizontal Pod Autoscaler:"
      & kubectl get hpa -n sam-ai
      
      Write-Ok "`nEKS deployment verification completed"
      
      # Useful commands
      Write-Info "`nUseful commands:"
      Write-Host "  View logs:        kubectl logs -f deployment/java-api -n sam-ai" -ForegroundColor Gray
      Write-Host "  Port forward:     kubectl port-forward svc/java-api-internal 8080:8080 -n sam-ai" -ForegroundColor Gray
      Write-Host "  Scale manually:   kubectl scale deployment/java-api --replicas=3 -n sam-ai" -ForegroundColor Gray
      Write-Host "  Describe pod:     kubectl describe pod <pod-name> -n sam-ai" -ForegroundColor Gray
      
    } catch {
      Write-Err "Verification failed: $($_.Exception.Message)"
    }
  } else {
    Write-Warn 'Skipping EKS verification (--SkipEksVerify)'
  }
  
  Write-Ok "`nEKS deployment complete!"
  Write-Info "For monitoring setup, run: cd infrastructure\eks; .\setup-monitoring.ps1"
}

function Step-CloudFront {
  Write-Header 'CLOUDFRONT DEPLOYMENT'
  Write-Info 'If ui\deploy.ps1 configured CloudFront, it should be up. Otherwise deploy distribution manually or via IaC.'
}

function Step-ECS {
  Write-Header 'ECS (Fargate) DEPLOYMENT (PROVISION, DEPLOY, VERIFY)'

  if (-not (Test-Cmd 'terraform')) { Write-Err 'Terraform is required for ECS provisioning'; return }
  if (-not (Test-Cmd 'docker'))    { Write-Err 'Docker is required to build container images'; return }
  if (-not (Test-Cmd 'aws'))       { Write-Err 'AWS CLI is required'; return }

  $ecsDir = Join-Path $RepoRoot 'infrastructure\ecs'
  $javaApiDir = Join-Path $RepoRoot 'java-api'
  if (-not (Test-Path $ecsDir))    { Write-Err "Missing ECS infrastructure directory: $ecsDir"; return }
  if (-not (Test-Path $javaApiDir)){ Write-Err "Missing Java API directory: $javaApiDir"; return }

  # Step 1: Provision ECS infra
  if (-not $SkipEcsProvision) {
    Write-Header 'Step 1/3: Provisioning ECS Infrastructure'
    $provisionScript = Join-Path $ecsDir 'provision-ecs.ps1'
    if (-not (Test-Path $provisionScript)) { Write-Err "Missing provision script: $provisionScript"; return }
    Push-Location $ecsDir
    try {
      Write-Info "Running: $provisionScript -Action apply -Environment $Environment -AutoApprove"
      & powershell -ExecutionPolicy Bypass -File $provisionScript -Action apply -Environment $Environment -AutoApprove
      if ($LASTEXITCODE -ne 0) { Write-Err 'ECS provisioning failed'; return }
      Write-Ok 'ECS infrastructure provisioned successfully.'
    } finally { Pop-Location }
  } else {
    Write-Warn 'Skipping ECS provisioning (--SkipEcsProvision)'
  }

  # Step 2: Deploy Java API to ECS
  if (-not $SkipEcsDeploy) {
    Write-Header 'Step 2/3: Deploying Java API to ECS'
    $deployScript = Join-Path $javaApiDir 'deploy-ecs.ps1'
    if (-not (Test-Path $deployScript)) { Write-Err "Missing deploy script: $deployScript"; return }
    Push-Location $javaApiDir
    try {
      Write-Info "Running: $deployScript -Environment $Environment -Region $Region -ImageTag dev-latest"
      & powershell -ExecutionPolicy Bypass -File $deployScript -Environment $Environment -Region $Region -ImageTag 'dev-latest'
      if ($LASTEXITCODE -ne 0) { Write-Err 'ECS deployment failed'; return }
      Write-Ok 'Java API deployed to ECS.'
    } finally { Pop-Location }
  } else {
    Write-Warn 'Skipping ECS deployment (--SkipEcsDeploy)'
  }

  # Step 3: Verify
  if (-not $SkipEcsVerify) {
    Write-Header 'Step 3/3: Verifying ECS Service'
    try {
      $AlbDns = try { (terraform -chdir=$ecsDir output -raw alb_dns_name) } catch { "" }
      if (-not $AlbDns) {
        Write-Info 'Attempting to discover ALB DNS via AWS CLI...'
        $AlbDns = (aws elbv2 describe-load-balancers --region $Region `
          --query "LoadBalancers[?contains(LoadBalancerName, '$Environment-java-api-alb')].DNSName | [0]" `
          --output text)
      }
      if ($AlbDns -and $AlbDns -ne 'None') {
        Write-Ok ("ALB: http://{0}" -f $AlbDns)
        Write-Info ("Health: http://{0}/actuator/health" -f $AlbDns)
        try {
          Start-Sleep -Seconds 5
          $resp = Invoke-WebRequest -Uri ("http://{0}/actuator/health" -f $AlbDns) -TimeoutSec 10 -UseBasicParsing -ErrorAction SilentlyContinue
          if ($resp.StatusCode -eq 200) { Write-Ok 'Health check passed (HTTP 200)' } else { Write-Warn ("Health HTTP {0}" -f $resp.StatusCode) }
        } catch { Write-Warn "Health check request failed: $($_.Exception.Message)" }
      } else {
        Write-Warn 'ALB DNS not available yet. It may still be provisioning.'
      }
    } catch {
      Write-Err ("Verification failed: {0}" -f $_.Exception.Message)
    }
  } else {
    Write-Warn 'Skipping ECS verification (--SkipEcsVerify)'
  }

  Write-Ok 'ECS deployment complete!'
}

function Step-Test {
  Write-Header 'TEST DEPLOYMENT'
  Write-Info 'Basic smoke checks (AWS identity, S3 listing)'
  try {
    Write-Ok ("AWS Caller Identity: " + (aws sts get-caller-identity | Out-String).Trim())
  } catch { Write-Warn "AWS CLI not authenticated: $($_.Exception.Message)" }
}

function Show-Usage {
  Write-Host @'
Usage:
  .\deploy-complete.ps1 -Action [verify|infrastructure|lambda|ui|java-api|eks|ecs|cloudfront|test|full] \
    -Environment dev -Region us-east-1 -BucketPrefix myprefix [-JavaApiCompose]

Examples:
  .\deploy-complete.ps1 -Action full
  .\deploy-complete.ps1 -Action lambda -Environment dev -Region us-east-1 -BucketPrefix myprefix
  .\deploy-complete.ps1 -Action ui
  .\deploy-complete.ps1 -Action java-api -JavaApiCompose
  .\deploy-complete.ps1 -Action eks -Environment dev -Region us-east-1
  .\deploy-complete.ps1 -Action eks -SkipEksProvision  # Deploy only (cluster already exists)
  .\deploy-complete.ps1 -Action ecs -Environment dev -Region us-east-1
  .\deploy-complete.ps1 -Action ecs -SkipEcsProvision  # Deploy only (cluster already exists)
'@
}

try {
  switch ($Action) {
    'verify'         { Step-Verify }
    'infrastructure' { Step-Infrastructure }
    'lambda'         { Step-Lambda }
    'ui'             { Step-UI }
    'java-api'       { Step-JavaApi }
    'eks'            { Step-EKS }
    'ecs'            { Step-ECS }
    'cloudfront'     { Step-CloudFront }
    'test'           { Step-Test }
    'full'           {
      Step-Verify
      Step-Infrastructure
      Step-Lambda
      Step-UI
      Step-JavaApi
      Step-ECS
      Step-CloudFront
      Step-Test
      Write-Ok 'Full deployment sequence completed.'
    }
    default          { Show-Usage }
  }
}
catch {
  Write-Err ($_ | Out-String)
  exit 1
}
