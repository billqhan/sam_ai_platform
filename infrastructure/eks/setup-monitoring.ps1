#!/usr/bin/env pwsh
# Setup monitoring stack (Prometheus + Grafana) on EKS
# Usage: .\setup-monitoring.ps1

param(
    [string]$Namespace = "monitoring",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

Write-Info "=== Setting up EKS Monitoring Stack ==="
Write-Info "Namespace: $Namespace"
Write-Info ""

# Check kubectl
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Error "kubectl not found"
    exit 1
}

# Check helm
if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Error "helm not found. Install from: https://helm.sh/docs/intro/install/"
    exit 1
}

# Add Prometheus Helm repo
Write-Info "Adding Prometheus Helm repository..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
Write-Success "✓ Helm repo added"

# Create namespace
Write-Info "Creating namespace $Namespace..."
kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f -
Write-Success "✓ Namespace ready"

if (-not $SkipInstall) {
    # Install kube-prometheus-stack
    Write-Info "Installing Prometheus + Grafana stack..."
    Write-Info "This may take several minutes..."
    
    $valuesFile = Join-Path $PSScriptRoot "monitoring-values.yaml"
    
    helm upgrade --install monitoring `
        prometheus-community/kube-prometheus-stack `
        --namespace $Namespace `
        --values $valuesFile `
        --wait `
        --timeout 10m
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Helm install failed"
        exit 1
    }
    
    Write-Success "✓ Monitoring stack installed"
}

# Wait for pods
Write-Info "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l "app.kubernetes.io/name=prometheus" -n $Namespace --timeout=5m
kubectl wait --for=condition=ready pod -l "app.kubernetes.io/name=grafana" -n $Namespace --timeout=5m
Write-Success "✓ All pods ready"

# Show status
Write-Info ""
Write-Info "=== Monitoring Stack Status ==="
kubectl get pods -n $Namespace

# Get Grafana admin password
Write-Info ""
Write-Info "=== Grafana Access ==="
$grafanaPassword = kubectl get secret monitoring-grafana -n $Namespace -o jsonpath="{.data.admin-password}" | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }
Write-Info "Username: admin"
Write-Info "Password: $grafanaPassword"

# Port forward instructions
Write-Info ""
Write-Info "=== Access Services ==="
Write-Info "Grafana (UI):"
Write-Info "  kubectl port-forward -n $Namespace svc/monitoring-grafana 3000:80"
Write-Info "  Then open: http://localhost:3000"
Write-Info ""
Write-Info "Prometheus (Queries):"
Write-Info "  kubectl port-forward -n $Namespace svc/monitoring-kube-prometheus-prometheus 9090:9090"
Write-Info "  Then open: http://localhost:9090"
Write-Info ""
Write-Info "AlertManager:"
Write-Info "  kubectl port-forward -n $Namespace svc/monitoring-kube-prometheus-alertmanager 9093:9093"
Write-Info "  Then open: http://localhost:9093"
Write-Info ""

Write-Success "=== Monitoring Setup Complete ==="
Write-Info ""
Write-Info "Next steps:"
Write-Info "1. Access Grafana using port-forward above"
Write-Info "2. Import additional dashboards from https://grafana.com/grafana/dashboards/"
Write-Info "3. Configure AlertManager for your email/Slack"
Write-Info "4. Set up CloudWatch Container Insights: aws eks update-cluster-config --name <cluster> --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'"
Write-Info ""
