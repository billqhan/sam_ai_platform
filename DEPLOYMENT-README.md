# Deployment Guide (UI + Java API Only)

## Scope

This guide documents only the deployment of:

- React UI (Vite) → S3 + CloudFront
- Java API (Spring Boot) → ECS (Fargate) or optional EKS via Helm

All former Lambda, SQS, DynamoDB, EventBridge, SAM.gov ingestion and related CloudFormation assets have been removed.

## Script Overview

`deploy-complete.sh` centralizes build, deployment, CloudFront distribution creation and verification. Former `deployment-verify.sh` functionality is fully inlined.

### Core Commands
```bash
# Full build & deploy (Java API → ECS + UI → S3 + CloudFront)
./deploy-complete.sh full

# Deploy Java API only
./deploy-complete.sh java-api

# Deploy UI only
./deploy-complete.sh ui

# Create/verify CloudFront distribution
./deploy-complete.sh cloudfront

# Verify prerequisites
./deploy-complete.sh verify

# Test deployed components
./deploy-complete.sh test
```

### Optional EKS
```bash
./deploy-complete.sh eks-cluster     # Create EKS cluster if absent
./deploy-complete.sh java-api-eks    # Deploy Java API via Helm chart
```

## Simplified Architecture

```
┌────────────┐      ┌──────────────┐      ┌──────────┐
│   React    │ ───▶ │  CloudFront  │ ───▶ │  Users    │
│   (S3)     │      │   CDN        │      │  Browser  │
└────────────┘      └──────────────┘      └──────────┘
   │ API Calls
   ▼
┌────────────────┐   (Fargate/EKS)
│  Java API      │
│  Spring Boot   │
└────────────────┘
```

## Environment Variables

Minimal required variables (see `.env.dev`):
```bash
export BUCKET_PREFIX="dev"
export ENVIRONMENT="dev"
export REGION="us-east-1"
export UI_BUCKET="dev-sam-website-dev"  # S3 bucket for built UI
```
Optional: EKS cluster name, Bedrock model IDs.

## Quick Start
```bash
# Verify tools & env vars
./deploy-complete.sh verify

# Full deployment
./deploy-complete.sh full

# UI only
./deploy-complete.sh ui

# Java API only (ECS)
./deploy-complete.sh java-api
```

## Prerequisites

- AWS CLI & valid credentials
- Java 17+, Maven 3.6+
- Node.js 18+, npm
- Docker (for ECS/EKS image builds)
- (Optional) helm, kubectl, eksctl

## Access URLs

After first successful full deployment the CloudFront URL will be printed by the script. Java API public IP/endpoint can be retrieved via ECS task network interface lookup.

## Verification Examples
```bash
# UI presence
aws s3 ls "s3://$UI_BUCKET/index.html"

# CloudFront domain
aws cloudfront list-distributions --query 'DistributionList.Items[].DomainName'

# ECS service status
aws ecs describe-services --cluster "${BUCKET_PREFIX}-ecs-cluster" --services "${BUCKET_PREFIX}-java-api-service" --region "$REGION"
```

## Troubleshooting
| Issue | Action |
|-------|--------|
| UI not updated | Re-run `./deploy-complete.sh ui`; invalidate CloudFront if cached. |
| CloudFront missing | Run `./deploy-complete.sh cloudfront` to create. |
| ECS task unhealthy | Check CloudWatch logs; verify security group allows 8080. |
| Multi-arch build fails | Remove buildx or create builder manually. |

## Next Steps
1. Wire UI to live Java API endpoints
2. Add custom domain + HTTPS (ACM + Route53)
3. CI/CD pipeline for automated image builds
4. CloudWatch alarms/dashboards for ECS performance

## Useful Commands
```bash
./deploy-complete.sh test
aws ecs list-tasks --cluster "${BUCKET_PREFIX}-ecs-cluster" --region "$REGION"
aws ec2 describe-network-interfaces --network-interface-ids <eni-id> --query 'NetworkInterfaces[0].Association.PublicIp' --output text
```

---

## Summary
Platform reduced to core components: React UI + Java API. Legacy serverless pipeline removed. Use `deploy-complete.sh` for all build/deploy operations.