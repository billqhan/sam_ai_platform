# RFP Response Platform (UI + Java API Only)

This repository has been streamlined to contain only two deployable components:

1. **React UI (Vite)** – Static front‑end hosted in S3 and served via CloudFront.
2. **Java API (Spring Boot)** – Backend service deployed to ECS (Fargate) or optionally to EKS via Helm.

All former serverless pipeline assets (Lambda, SQS, DynamoDB event workflow, SAM.gov ingestion) have been removed. Documentation and scripts now focus solely on building and deploying the UI and Java API.

## Project Layout (Reduced)
```
README.md
deploy-complete.sh        # Unified build + deploy + verify script
.env.dev                  # Environment variables (UI + Java API)
java-api/                 # Spring Boot service (Docker/ECS/EKS deploy)
ui/                       # React (Vite) application
deployment/eks/           # Optional EKS helper scripts
deployment/charts/rfp-java-api/  # Helm chart for Java API
charts/                   # (If present) additional Helm resources
```

## Prerequisites

- AWS CLI configured (access to ECR, ECS, S3, CloudFront, IAM)
- Docker (for container builds & multi‑arch push)
- Java 17+ & Maven
- Node.js 18+ & npm
- (Optional) kubectl, eksctl, helm for EKS deploy

## Environment Configuration

Edit `.env.dev` to set core values:
```bash
export BUCKET_PREFIX="dev"   # Short project prefix
export ENVIRONMENT="dev"     # Environment label
export REGION="us-east-1"    # AWS region
export UI_BUCKET="dev-sam-website-dev"  # S3 bucket for UI assets
```
Other variables (EKS, Bedrock model IDs) are optional and can remain blank.

Source the file when working locally:
```bash
source .env.dev
```

## Deployment Script Overview

`deploy-complete.sh` handles build, containerization, S3 sync, CloudFront setup, and basic verification.

Common commands:
```bash
# Full build & deploy (Java API → ECS + UI → S3 + CloudFront)
./deploy-complete.sh full

# Build & deploy only Java API (ECS)
./deploy-complete.sh java-api

# Build & deploy only UI (S3 + CloudFront)
./deploy-complete.sh ui

# Create/verify CloudFront distribution only
./deploy-complete.sh cloudfront

# Run lightweight verification
./deploy-complete.sh verify

# Test deployed components (ECS service + UI presence)
./deploy-complete.sh test
```

Optional EKS flow:
```bash
# Create EKS cluster (if not existing)
./deploy-complete.sh eks-cluster

# Deploy Java API to EKS via Helm
./deploy-complete.sh java-api-eks
```

## Java API Local Development

Run locally without Docker:
```bash
cd java-api
mvn spring-boot:run
```
Or build the jar:
```bash
mvn clean package -DskipTests
java -jar target/rfp-response-agent-api-1.0.0.jar
```

## React UI Local Development
```bash
cd ui
npm install
npm run dev
```
Build for production:
```bash
npm run build
```

## Container Build (Manual Example)
```bash
cd java-api
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME="${BUCKET_PREFIX}-rfp-java-api"
IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest"
aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION" 2>/dev/null || true
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker build -t "$IMAGE_URI" .
docker push "$IMAGE_URI"
```

## Verification
```bash
# Check ECS service
aws ecs describe-services --cluster "${BUCKET_PREFIX}-ecs-cluster" --services "${BUCKET_PREFIX}-java-api-service" --region "$REGION"

# Confirm UI index present
aws s3 ls "s3://$UI_BUCKET/index.html"
```

## Troubleshooting (Focused)

| Issue | Resolution |
|-------|------------|
| UI not updating | Run `./deploy-complete.sh ui`; if cached, invalidate CloudFront via script or AWS Console. |
| ECS service failing health check | Check container logs in CloudWatch, ensure port 8080 open in security group. |
| Docker multi-arch build failure | Remove buildx usage or create builder manually. |
| Helm deploy fails | Confirm EKS cluster exists and kubeconfig updated (`aws eks update-kubeconfig`). |

## Removed Components

The following have been intentionally removed: Lambda functions, SQS queues, DynamoDB tables, EventBridge rules, legacy CloudFormation templates, serverless workflow scripts, SAM.gov ingestion jobs.

## Next Steps

- Add integration endpoints between UI and Java API
- Introduce CI/CD pipeline (GitHub Actions / Jenkins) for container builds
- Add CloudWatch alarms & dashboard for ECS service
- Configure custom domain + HTTPS for CloudFront

---
This repository now represents a lean deployment model for the RFP Response Platform focused on UI + Java API only.