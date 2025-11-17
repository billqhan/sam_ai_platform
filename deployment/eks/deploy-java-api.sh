#!/usr/bin/env bash
set -euo pipefail

# Deploy Java API to EKS using Helm
# Requirements: kubectl context set to target cluster; helm installed
# Env vars (or flags):
#   NAMESPACE (default: rfp-platform-dev)
#   RELEASE (default: rfp-java-api)
#   IMAGE_REPO (default from values.yaml, can override via env)
#   IMAGE_TAG  (required)
#   HOST (optional: ingress host override)

if ! command -v helm >/dev/null 2>&1; then
  echo "helm not found. Please install Helm (e.g., brew install helm)" >&2
  exit 127
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found. Please install kubectl (e.g., brew install kubectl)" >&2
  exit 127
fi

NAMESPACE=${NAMESPACE:-rfp-platform-dev}
RELEASE=${RELEASE:-rfp-java-api}

CHART_ROOT="$(dirname "$0")/../../charts/rfp-java-api"
if [ ! -d "$CHART_ROOT" ]; then
  echo "Helm chart directory not found: $CHART_ROOT" >&2
  exit 1
fi
CHART_DIR=$(cd "$CHART_ROOT" && pwd)

: "${IMAGE_TAG:?Set IMAGE_TAG}"

set -x

HELM_ARGS=(
  --namespace "$NAMESPACE" --create-namespace
  --set image.tag="$IMAGE_TAG"
)

if [ -n "${IMAGE_REPO:-}" ]; then
  HELM_ARGS+=(--set image.repository="$IMAGE_REPO")
fi

if [ -n "${HOST:-}" ]; then
  HELM_ARGS+=(--set ingress.hosts[0].host="$HOST")
fi

helm upgrade --install "$RELEASE" "$CHART_DIR" "${HELM_ARGS[@]}"

# Determine the actual Deployment name by selector labels
DEPLOY_NAME=$(kubectl get deploy -n "$NAMESPACE" -l app.kubernetes.io/instance="$RELEASE" \
  -o jsonpath='{.items[0].metadata.name}')
if [ -z "${DEPLOY_NAME:-}" ]; then
  echo "Unable to determine Deployment name for release $RELEASE in namespace $NAMESPACE" >&2
  exit 1
fi

kubectl rollout status deploy/"$DEPLOY_NAME" -n "$NAMESPACE" --timeout=180s

set +x

echo "Deployed $RELEASE:$IMAGE_TAG to namespace $NAMESPACE (deployment: $DEPLOY_NAME)"
