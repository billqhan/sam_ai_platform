#!/usr/bin/env pwsh
# Provision ECS infrastructure with Terraform
# Usage: .\provision-ecs.ps1 [-Action plan|apply|destroy] [-Environment dev] [-AutoApprove]

param(
  [ValidateSet("plan","apply","destroy")]
  [string]$Action = "plan",
  [string]$Environment = "dev",
  [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

function Write-Info($m){ Write-Host $m -ForegroundColor Cyan }
function Write-Ok($m){ Write-Host $m -ForegroundColor Green }
function Write-Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Write-Err($m){ Write-Host $m -ForegroundColor Red }

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $Here

try {
  if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) { throw "Terraform is not installed" }

  Write-Info "Initializing Terraform..."
  terraform init -upgrade
  terraform validate

  switch ($Action) {
    "plan" {
      Write-Info "Planning for environment: $Environment"
      terraform plan -var "environment=$Environment" -out tfplan
    }
    "apply" {
      Write-Info "Applying for environment: $Environment"
      if ($AutoApprove) { terraform apply -var "environment=$Environment" -auto-approve } else { terraform apply -var "environment=$Environment" }
      Write-Ok "ECS infrastructure provisioned."
      Write-Info "Outputs:"
      terraform output
    }
    "destroy" {
      Write-Warn "Destroying ECS infrastructure for $Environment"
      terraform destroy -var "environment=$Environment" -auto-approve
    }
  }
}
finally {
  Pop-Location
}
