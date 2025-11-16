#!/usr/bin/env pwsh
# Build, push, and deploy Java API to ECS Fargate
# Usage: .\deploy-ecs.ps1 [-Environment dev] [-ImageTag latest]

param(
  [string]$Environment = "dev",
  [string]$Region = "us-east-1",
  [string]$ImageTag = "dev-latest"
)

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){ Write-Host $m -ForegroundColor Green }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Err($m){ Write-Host $m -ForegroundColor Red }

# Resolve ECR info
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REPO   = 'sam-ai-java-api'
$ECR_URL    = "$ACCOUNT_ID.dkr.ecr.$Region.amazonaws.com/$ECR_REPO"
$IMAGE      = "$ECR_URL:$ImageTag"
$CLUSTER    = "$Environment-sam-ai-ecs"
$SERVICE    = "$Environment-java-api"

Info "Building Maven project..."
Push-Location $PSScriptRoot
./build.sh
Pop-Location

Info "Building Docker image: $IMAGE"
docker build -t $IMAGE $PSScriptRoot

Info "Logging into ECR..."
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $ECR_URL

Info "Pushing image..."
docker push $IMAGE

Info "Forcing new ECS deployment..."
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment --region $Region | Out-Null

Info "Waiting for service stability... (this can take a few minutes)"
aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE --region $Region

# Fetch ALB DNS from Terraform outputs (if ran locally) or describe
$AlbDns = try { (terraform -chdir=..\infrastructure\ecs output -raw alb_dns_name) } catch { "" }
if (-not $AlbDns) {
  Info "Attempting to resolve ALB DNS via AWS APIs..."
  # Best-effort discovery: find ALB with name prefix
  $AlbDns = (aws elbv2 describe-load-balancers --region $Region `
    --query "LoadBalancers[?contains(LoadBalancerName, '$Environment-java-api-alb')].DNSName | [0]" `
    --output text)
}

if ($AlbDns) {
  Ok "Service is up behind ALB: http://$AlbDns"
  Info "Health: http://$AlbDns/actuator/health"
} else {
  Warn "Could not resolve ALB DNS. Check with: terraform -chdir=..\infrastructure\ecs output"
}
