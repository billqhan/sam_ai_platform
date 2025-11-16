terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "ai-rfp-terraform-state"
    key    = "ecs/terraform.tfstate"
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
      Component   = "ECS"
    }
  }
}

data "aws_caller_identity" "current" {}
