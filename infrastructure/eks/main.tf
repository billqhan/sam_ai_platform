terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }

  backend "s3" {
    bucket = "ai-rfp-terraform-state"
    key    = "eks/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "SAM-AI-Platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Component   = "EKS"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# Local variables
locals {
  cluster_name = "${var.environment}-sam-ai-eks"
  account_id   = data.aws_caller_identity.current.account_id
  
  azs = slice(data.aws_availability_zones.available.names, 0, 3)
  
  tags = {
    Project     = "SAM-AI-Platform"
    Environment = var.environment
    Terraform   = "true"
  }
}
