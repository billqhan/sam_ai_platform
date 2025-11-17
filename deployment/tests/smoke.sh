#!/usr/bin/env bash
set -euo pipefail

# Simple smoke tests for UI and API after deployment
# Env vars:
# - UI_URL: CloudFront/UI base URL, e.g., https://d8bbmb3a6jev2.cloudfront.net
# - API_BASE: API Gateway base URL, e.g., https://3cvymua5c8.execute-api.us-east-1.amazonaws.com/dev

UI_URL=${UI_URL:-}
API_BASE=${API_BASE:-}

if [[ -z "${UI_URL}" || -z "${API_BASE}" ]]; then
  echo "[ERROR] UI_URL and API_BASE must be set."
  echo "Example: UI_URL=https://d8bbmb3a6jev2.cloudfront.net API_BASE=https://3cvymua5c8.execute-api.us-east-1.amazonaws.com/dev bash deployment/tests/smoke.sh"
  exit 2
fi

blue() { echo -e "\033[0;34m$1\033[0m"; }
green() { echo -e "\033[0;32m$1\033[0m"; }
red() { echo -e "\033[0;31m$1\033[0m"; }
yellow() { echo -e "\033[1;33m$1\033[0m"; }

req() {
  local method=$1
  local url=$2
  shift 2
  curl -fsSL -X "$method" "$url" -H 'Accept: */*' -m 20 -w '\n%{http_code}\n' -o /tmp/smoke_body "$@"
}

assert_status() {
  local want=$1
  local got=$2
  if [[ "$want" != "$got" ]]; then
    red "[FAIL] expected status $want, got $got"
    echo "Response body (first 400 chars):"
    head -c 400 /tmp/smoke_body || true
    echo
    exit 1
  fi
}

assert_body_contains() {
  local needle=$1
  if ! grep -qi -- "$needle" /tmp/smoke_body; then
    red "[FAIL] response body missing: $needle"
    head -c 400 /tmp/smoke_body || true
    echo
    exit 1
  fi
}

blue "[SMOKE] UI root loads"
code=$(req GET "$UI_URL/")
status=$(tail -n1 <<<"$code")
assert_status 200 "$status"
assert_body_contains "<html"

green "[OK] UI root responded 200 with HTML"

blue "[SMOKE] Reports page endpoint returns HTML"
code=$(req GET "$API_BASE/reports/index/view")
status=$(tail -n1 <<<"$code")
assert_status 200 "$status"
assert_body_contains "<html"

green "[OK] Reports HTML retrieved"

blue "[SMOKE] Dashboard opportunities chart returns JSON"
code=$(req GET "$API_BASE/dashboard/charts/opportunities?period=7d")
status=$(tail -n1 <<<"$code")
assert_status 200 "$status"
# Basic JSON heuristic: starts with [ or {
if ! head -c 1 /tmp/smoke_body | grep -qE '[\[{]'; then
  red "[FAIL] dashboard API did not return JSON"
  head -c 200 /tmp/smoke_body || true
  echo
  exit 1
fi

green "[OK] Dashboard data looks like JSON"

blue "[SMOKE] Matches trigger is reachable (dry check)"
# We won't actually trigger here; just check method allowed or 4xx expected
if curl -sI -X OPTIONS "$API_BASE/matches/trigger" | grep -q "HTTP/"; then
  green "[OK] Matches trigger endpoint reachable"
else
  yellow "[WARN] Could not reach matches trigger endpoint headers"
fi


green "[SMOKE] All checks passed"