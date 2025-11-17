#!/usr/bin/env bash
set -euo pipefail

# Deploy Java API to EKS using Helm
# Requirements: kubectl context set to target cluster; helm installed
# Env vars (or flags):
#   NAMESPACE (default: rfp-platform-dev)
#   RELEASE (default: rfp-java-api)
#   IMAGE_REPO (default from values.yaml)
#   IMAGE_TAG  (required)
#   HOST (optional: ingress host override)

NAMESPACE=${NAMESPACE:-rfp-platform-dev}
RELEASE=${RELEASE:-rfp-java-api}
CHART_DIR=$(cd "$(dirname "$0")/../../charts/rfp-java-api" && pwd)

: "${IMAGE_TAG:?Set IMAGE_TAG}"

set -x

helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" --create-namespace \
  --set image.tag="$IMAGE_TAG" \
  ${HOST:+--set ingress.hosts[0].host="$HOST"}

kubectl rollout status deploy/"$RELEASE" -n "$NAMESPACE" --timeout=180s

set +x

echo "Deployed $RELEASE:$IMAGE_TAG to namespace $NAMESPACE"
