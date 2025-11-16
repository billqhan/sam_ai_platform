#!/bin/bash
# Deploy Java API to EKS
# Usage: ./deploy-eks.sh [environment] [image-tag]

set -e

# Configuration
ENVIRONMENT=${1:-dev}
IMAGE_TAG=${2:-latest}
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="sam-ai-java-api"
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
CLUSTER_NAME="${ENVIRONMENT}-sam-ai-eks"
FULL_IMAGE="${ECR_URL}:${ENVIRONMENT}-${IMAGE_TAG}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}=== EKS Deployment Configuration ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Image: $FULL_IMAGE"
echo ""

# Check prerequisites
echo -e "${CYAN}Checking prerequisites...${NC}"
for cmd in docker kubectl aws; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ Prerequisites OK${NC}"

# Build Docker image
echo -e "${CYAN}Building Docker image...${NC}"
cd "$(dirname "$0")"

# Build with Maven
echo "Running Maven build..."
./build.sh

# Build Docker image
echo "Building Docker image: $FULL_IMAGE"
docker build -t "$FULL_IMAGE" .

# Also tag as latest
docker tag "$FULL_IMAGE" "${ECR_URL}:dev-latest"

echo -e "${GREEN}✓ Build complete${NC}"

# Push to ECR
echo -e "${CYAN}Pushing image to ECR...${NC}"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

# Push image
echo "Pushing $FULL_IMAGE..."
docker push "$FULL_IMAGE"
docker push "${ECR_URL}:dev-latest"

echo -e "${GREEN}✓ Image pushed to ECR${NC}"

# Deploy to EKS
echo -e "${CYAN}Deploying to EKS...${NC}"

# Update kubeconfig
echo "Updating kubeconfig for cluster $CLUSTER_NAME..."
aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME

# Verify cluster access
echo "Verifying cluster access..."
kubectl cluster-info

# Create namespace if not exists
echo "Creating namespace sam-ai..."
kubectl create namespace sam-ai --dry-run=client -o yaml | kubectl apply -f -

# Apply Kubernetes manifests
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/deployment.yaml

# Update image (force rollout)
echo "Updating deployment image..."
kubectl set image deployment/java-api java-api=$FULL_IMAGE -n sam-ai
kubectl rollout restart deployment/java-api -n sam-ai

# Wait for rollout
echo "Waiting for rollout to complete..."
kubectl rollout status deployment/java-api -n sam-ai --timeout=5m

echo -e "${GREEN}✓ Deployment complete${NC}"

# Show deployment status
echo ""
echo -e "${CYAN}=== Deployment Status ===${NC}"
kubectl get pods -n sam-ai -l app=java-api
kubectl get svc -n sam-ai -l app=java-api

# Get service endpoint
echo ""
echo -e "${CYAN}=== Service Endpoint ===${NC}"
SVC_URL=$(kubectl get svc java-api -n sam-ai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
if [ -n "$SVC_URL" ]; then
    echo -e "${GREEN}Load Balancer URL: http://$SVC_URL${NC}"
    echo "Health Check: http://$SVC_URL:8081/actuator/health"
else
    echo -e "${YELLOW}Load Balancer is still provisioning. Check status with: kubectl get svc -n sam-ai${NC}"
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Useful commands:"
echo "  View pods:        kubectl get pods -n sam-ai"
echo "  View logs:        kubectl logs -f deployment/java-api -n sam-ai"
echo "  View services:    kubectl get svc -n sam-ai"
echo "  Describe pod:     kubectl describe pod <pod-name> -n sam-ai"
echo "  Port forward:     kubectl port-forward svc/java-api-internal 8080:8080 -n sam-ai"
echo "  Scale deployment: kubectl scale deployment/java-api --replicas=3 -n sam-ai"
echo ""
