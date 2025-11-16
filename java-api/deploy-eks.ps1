#!/usr/bin/env pwsh
# Deploy Java API to EKS
# Usage: .\deploy-eks.ps1 [-Environment dev] [-SkipBuild] [-SkipPush] [-SkipDeploy]

param(
    [string]$Environment = "dev",
    [switch]$SkipBuild,
    [switch]$SkipPush,
    [switch]$SkipDeploy,
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host $msg -ForegroundColor Red }

# Configuration
$REGION = "us-east-1"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REPO = "sam-ai-java-api"
$ECR_URL = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"
$CLUSTER_NAME = "$Environment-sam-ai-eks"
$IMAGE_TAG = "$Environment-$ImageTag"
$FULL_IMAGE = "${ECR_URL}:${IMAGE_TAG}"

Write-Info "=== EKS Deployment Configuration ==="
Write-Info "Environment: $Environment"
Write-Info "Region: $REGION"
Write-Info "Cluster: $CLUSTER_NAME"
Write-Info "Image: $FULL_IMAGE"
Write-Info ""

# Check prerequisites
Write-Info "Checking prerequisites..."

$commands = @("docker", "kubectl", "aws")
foreach ($cmd in $commands) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "$cmd is not installed or not in PATH"
        exit 1
    }
}

Write-Success "✓ Prerequisites OK"

# Build Docker image
if (-not $SkipBuild) {
    Write-Info "Building Docker image..."
    
    Push-Location $PSScriptRoot
    
    # Build with Maven
    Write-Info "Running Maven build..."
    & ./build.sh
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Maven build failed"
        Pop-Location
        exit 1
    }
    
    # Build Docker image
    Write-Info "Building Docker image: $FULL_IMAGE"
    docker build -t $FULL_IMAGE .
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        Pop-Location
        exit 1
    }
    
    # Also tag as latest for local testing
    docker tag $FULL_IMAGE "${ECR_URL}:dev-latest"
    
    Pop-Location
    Write-Success "✓ Build complete"
} else {
    Write-Warning "Skipping build"
}

# Push to ECR
if (-not $SkipPush) {
    Write-Info "Pushing image to ECR..."
    
    # Login to ECR
    Write-Info "Logging in to ECR..."
    $loginCmd = aws ecr get-login-password --region $REGION
    $loginCmd | docker login --username AWS --password-stdin $ECR_URL
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ECR login failed"
        exit 1
    }
    
    # Push image
    Write-Info "Pushing $FULL_IMAGE..."
    docker push $FULL_IMAGE
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker push failed"
        exit 1
    }
    
    # Push latest tag
    docker push "${ECR_URL}:dev-latest"
    
    Write-Success "✓ Image pushed to ECR"
} else {
    Write-Warning "Skipping push to ECR"
}

# Deploy to EKS
if (-not $SkipDeploy) {
    Write-Info "Deploying to EKS..."
    
    # Update kubeconfig
    Write-Info "Updating kubeconfig for cluster $CLUSTER_NAME..."
    aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to update kubeconfig"
        exit 1
    }
    
    # Verify cluster access
    Write-Info "Verifying cluster access..."
    kubectl cluster-info
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Cannot access cluster"
        exit 1
    }
    
    # Create namespace if not exists
    Write-Info "Creating namespace sam-ai..."
    kubectl create namespace sam-ai --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Kubernetes manifests
    Write-Info "Applying Kubernetes manifests..."
    kubectl apply -f $PSScriptRoot/k8s/deployment.yaml
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to apply deployment"
        exit 1
    }
    
    # Update image (force rollout)
    Write-Info "Updating deployment image..."
    kubectl set image deployment/java-api java-api=$FULL_IMAGE -n sam-ai
    kubectl rollout restart deployment/java-api -n sam-ai
    
    # Wait for rollout
    Write-Info "Waiting for rollout to complete..."
    kubectl rollout status deployment/java-api -n sam-ai --timeout=5m
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Rollout failed"
        exit 1
    }
    
    Write-Success "✓ Deployment complete"
    
    # Show deployment status
    Write-Info ""
    Write-Info "=== Deployment Status ==="
    kubectl get pods -n sam-ai -l app=java-api
    kubectl get svc -n sam-ai -l app=java-api
    
    # Get service endpoint
    Write-Info ""
    Write-Info "=== Service Endpoint ==="
    $svcUrl = kubectl get svc java-api -n sam-ai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
    if ($svcUrl) {
        Write-Success "Load Balancer URL: http://$svcUrl"
        Write-Info "Health Check: http://$svcUrl:8081/actuator/health"
    } else {
        Write-Warning "Load Balancer is still provisioning. Check status with: kubectl get svc -n sam-ai"
    }
    
} else {
    Write-Warning "Skipping deployment to EKS"
}

Write-Success ""
Write-Success "=== Deployment Complete ==="
Write-Info ""
Write-Info "Useful commands:"
Write-Info "  View pods:        kubectl get pods -n sam-ai"
Write-Info "  View logs:        kubectl logs -f deployment/java-api -n sam-ai"
Write-Info "  View services:    kubectl get svc -n sam-ai"
Write-Info "  Describe pod:     kubectl describe pod <pod-name> -n sam-ai"
Write-Info "  Port forward:     kubectl port-forward svc/java-api-internal 8080:8080 -n sam-ai"
Write-Info "  Scale deployment: kubectl scale deployment/java-api --replicas=3 -n sam-ai"
Write-Info ""
