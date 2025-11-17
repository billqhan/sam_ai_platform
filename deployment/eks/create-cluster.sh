#!/usr/bin/env bash
set -euo pipefail

# Simple EKS cluster provisioning script using eksctl.
# Requires: eksctl, aws CLI, kubectl installed and AWS credentials with EKS permissions.
# Usage (defaults shown):
#   ./deployment/eks/create-cluster.sh
#   CLUSTER_NAME=rfp-prod-eks NODE_TYPE=t4g.medium MIN_NODES=3 MAX_NODES=9 ./deployment/eks/create-cluster.sh
# Variables:
CLUSTER_NAME=${CLUSTER_NAME:-rfp-dev-eks}
REGION=${REGION:-us-east-1}
VERSION=${VERSION:-1.29}
NODE_TYPE=${NODE_TYPE:-t3.medium}
MIN_NODES=${MIN_NODES:-2}
MAX_NODES=${MAX_NODES:-6}

echo "[INFO] Creating EKS cluster '${CLUSTER_NAME}' in ${REGION} (k8s ${VERSION})"

eksctl create cluster \
  --name "${CLUSTER_NAME}" \
  --region "${REGION}" \
  --version "${VERSION}" \
  --with-oidc \
  --managed \
  --nodegroup-name ng-general \
  --node-type "${NODE_TYPE}" \
  --nodes "${MIN_NODES}" \
  --nodes-min "${MIN_NODES}" \
  --nodes-max "${MAX_NODES}" \
  --tags project=rfp-ai,env=dev

echo "[INFO] Cluster created. Updating local kubeconfig..."
aws eks update-kubeconfig --name "${CLUSTER_NAME}" --region "${REGION}" --alias "${CLUSTER_NAME}" >/dev/null

kubectl get nodes

# Optional add-ons installation
echo "[INFO] Installing Metrics Server"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# AWS Load Balancer Controller IRSA setup
echo "[INFO] Setting up AWS Load Balancer Controller (IRSA)"
POLICY_FILE=$(mktemp)
curl -s -o "$POLICY_FILE" https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.8.1/docs/install/iam_policy.json
aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy --policy-document file://"$POLICY_FILE" 2>/dev/null || true

eksctl create iamserviceaccount \
  --cluster "${CLUSTER_NAME}" \
  --namespace kube-system \
  --name aws-load-balancer-controller \
  --attach-policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/AWSLoadBalancerControllerIAMPolicy \
  --approve \
  --override-existing-serviceaccounts

helm repo add eks https://aws.github.io/eks-charts >/dev/null
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName="${CLUSTER_NAME}" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

# Horizontal Pod Autoscaler already works with Metrics Server; Cluster Autoscaler follows.
echo "[INFO] (Optional) Install Cluster Autoscaler:"
echo "  kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler.yaml"

cat <<EOF
[INFO] Next steps:
1. Push Java API image to ECR with a tag (e.g., git SHA).
2. Deploy app: IMAGE_TAG=<tag> deployment/eks/deploy-java-api.sh
3. Configure ingress host & DNS (Route53) for external access.
4. Add HPA tuning & observability stack (Prometheus/Grafana if desired).
EOF
