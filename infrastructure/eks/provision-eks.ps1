#!/usr/bin/env pwsh
# Provision EKS infrastructure with Terraform
# Usage: .\provision-eks.ps1 [-Action plan|apply|destroy] [-AutoApprove]

param(
    [ValidateSet("plan", "apply", "destroy")]
    [string]$Action = "plan",
    [switch]$AutoApprove,
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"

function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host $msg -ForegroundColor Red }

$TERRAFORM_DIR = Join-Path $PSScriptRoot ".." "infrastructure" "eks"

Write-Info "=== EKS Infrastructure Provisioning ==="
Write-Info "Action: $Action"
Write-Info "Environment: $Environment"
Write-Info "Terraform Dir: $TERRAFORM_DIR"
Write-Info ""

# Check Terraform installation
if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    Write-Error "Terraform is not installed. Install from: https://www.terraform.io/downloads"
    exit 1
}

Push-Location $TERRAFORM_DIR

try {
    # Initialize Terraform
    Write-Info "Initializing Terraform..."
    terraform init -upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform init failed"
    }
    Write-Success "✓ Terraform initialized"
    
    # Validate configuration
    Write-Info "Validating Terraform configuration..."
    terraform validate
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform validation failed"
    }
    Write-Success "✓ Configuration valid"
    
    # Execute action
    switch ($Action) {
        "plan" {
            Write-Info "Running Terraform plan..."
            terraform plan -var="environment=$Environment" -out=tfplan
            Write-Success "✓ Plan complete. Review above output."
            Write-Info "To apply: .\provision-eks.ps1 -Action apply -AutoApprove"
        }
        
        "apply" {
            Write-Info "Applying Terraform configuration..."
            
            if ($AutoApprove) {
                terraform apply -var="environment=$Environment" -auto-approve
            } else {
                terraform apply -var="environment=$Environment"
            }
            
            if ($LASTEXITCODE -ne 0) {
                throw "Terraform apply failed"
            }
            
            Write-Success "✓ Infrastructure provisioned successfully"
            
            # Show outputs
            Write-Info ""
            Write-Info "=== Terraform Outputs ==="
            terraform output
            
            # Configure kubectl
            Write-Info ""
            Write-Info "Configuring kubectl..."
            $clusterName = terraform output -raw cluster_name
            $region = terraform output -raw aws_region
            aws eks update-kubeconfig --region us-east-1 --name $clusterName
            
            Write-Success "✓ kubectl configured"
            
            Write-Info ""
            Write-Info "=== Next Steps ==="
            Write-Info "1. Install AWS Load Balancer Controller:"
            Write-Info "   kubectl apply -f https://github.com/kubernetes-sigs/aws-load-balancer-controller/releases/download/v2.7.0/v2_7_0_full.yaml"
            Write-Info ""
            Write-Info "2. Install Metrics Server (for HPA):"
            Write-Info "   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
            Write-Info ""
            Write-Info "3. Deploy Java API:"
            Write-Info "   cd java-api"
            Write-Info "   .\deploy-eks.ps1"
            Write-Info ""
        }
        
        "destroy" {
            Write-Warning "WARNING: This will destroy all EKS infrastructure!"
            Write-Warning "Type 'yes' to confirm destruction:"
            
            if (-not $AutoApprove) {
                $confirmation = Read-Host
                if ($confirmation -ne "yes") {
                    Write-Info "Destroy cancelled"
                    exit 0
                }
            }
            
            Write-Info "Destroying infrastructure..."
            terraform destroy -var="environment=$Environment" -auto-approve
            
            if ($LASTEXITCODE -ne 0) {
                throw "Terraform destroy failed"
            }
            
            Write-Success "✓ Infrastructure destroyed"
        }
    }
    
} catch {
    Write-Error "Error: $_"
    exit 1
} finally {
    Pop-Location
}

Write-Success ""
Write-Success "=== Operation Complete ==="
