#!/usr/bin/env bash
#
# agent-stack-k8s-diagnose.sh
#
# One-shot diagnostic for the Buildkite Agent Stack for Kubernetes controller.
# Gathers: controller version, chart deployment metadata, controller logs,
# recent stalled Jobs, K8s events for the buildkite namespace, agent version
# distribution. Prints a structured report to stdout for cut/paste into a
# support ticket or incident channel.
#
# Inputs (positional or env):
#   NAMESPACE   — Kubernetes namespace (default: buildkite)
#   BUILD_ID    — optional Buildkite build ID; if set, narrows event/log search
#
# Usage:
#   ./agent-stack-k8s-diagnose.sh
#   ./agent-stack-k8s-diagnose.sh buildkite
#   NAMESPACE=ci-buildkite BUILD_ID=01900000-0000-0000-0000-000000000000 \
#     ./agent-stack-k8s-diagnose.sh
#
# Outputs:
#   Structured stdout sections (each prefixed with ====) covering controller
#   metadata, recent stalled job pods, controller logs (last 30 minutes), K8s
#   events sorted by timestamp, and agent version distribution.
#
# Non-goals:
#   This script is read-only. It does not restart pods, mutate resources, or
#   modify cluster state. It does not stream live logs; for live tailing use
#   `kubectl logs -f` directly.

set -euo pipefail

NAMESPACE="${1:-${NAMESPACE:-buildkite}}"
BUILD_ID="${BUILD_ID:-}"
SINCE="${SINCE:-30m}"

section() {
  printf '\n==== %s ====\n' "$1"
}

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'ERROR: required tool %q not found in PATH\n' "$1" >&2
    exit 2
  fi
}

require kubectl

if ! kubectl get ns "$NAMESPACE" >/dev/null 2>&1; then
  printf 'ERROR: namespace %q does not exist or is not accessible\n' "$NAMESPACE" >&2
  exit 3
fi

section "Diagnostic context"
printf 'Timestamp: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'Namespace: %s\n' "$NAMESPACE"
printf 'Build ID: %s\n' "${BUILD_ID:-<not set>}"
printf 'Log window: %s\n' "$SINCE"

section "Controller deployment metadata"
kubectl get deploy -n "$NAMESPACE" -l app=agent-stack-k8s \
  -o jsonpath='{range .items[*]}name={.metadata.name}{"\n"}image={.spec.template.spec.containers[0].image}{"\n"}replicas={.status.replicas}/{.status.readyReplicas}{"\n"}{end}' \
  2>/dev/null || printf 'WARN: no deployment with label app=agent-stack-k8s found\n'

section "Controller pods"
kubectl get pods -n "$NAMESPACE" -l app=agent-stack-k8s \
  -o wide 2>/dev/null || printf 'WARN: no controller pods found\n'

section "Controller config (values redacted)"
kubectl get configmap -n "$NAMESPACE" -l app=agent-stack-k8s \
  -o yaml 2>/dev/null \
  | sed -E 's/(token|secret|password|key)[[:space:]]*:[[:space:]]*.*/\1: <redacted>/I' \
  || printf 'WARN: no controller configmap found\n'

section "Controller logs (last $SINCE)"
if [[ -n "$BUILD_ID" ]]; then
  kubectl logs -n "$NAMESPACE" -l app=agent-stack-k8s --since="$SINCE" --tail=2000 2>/dev/null \
    | grep -i -E "(${BUILD_ID}|stalled|max-in-flight|FailedScheduling|ImagePullBackOff|error|warn)" \
    || printf '(no matching log lines)\n'
else
  kubectl logs -n "$NAMESPACE" -l app=agent-stack-k8s --since="$SINCE" --tail=500 2>/dev/null \
    || printf 'WARN: cannot read controller logs\n'
fi

section "Recent stalled / failed Jobs"
kubectl get jobs -n "$NAMESPACE" \
  --sort-by='.status.startTime' \
  -o custom-columns='NAME:.metadata.name,STARTED:.status.startTime,FAILED:.status.failed,COMPLETIONS:.status.succeeded,CONDITIONS:.status.conditions[*].type' \
  2>/dev/null | tail -n 30 || printf 'WARN: cannot list jobs\n'

section "Recent Pod statuses"
kubectl get pods -n "$NAMESPACE" \
  --sort-by='.status.startTime' \
  -o custom-columns='NAME:.metadata.name,PHASE:.status.phase,REASON:.status.reason,STARTED:.status.startTime' \
  2>/dev/null | tail -n 30 || printf 'WARN: cannot list pods\n'

section "K8s Events (sorted by lastTimestamp, last 50)"
if [[ -n "$BUILD_ID" ]]; then
  kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null \
    | grep -E "(${BUILD_ID}|FailedScheduling|ImagePullBackOff|OOMKilled|BackOff|FailedMount)" \
    || printf '(no matching events for build %s)\n' "$BUILD_ID"
else
  kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null \
    | tail -n 50 || printf 'WARN: cannot list events\n'
fi

section "Agent version distribution (across recent pods)"
kubectl get pods -n "$NAMESPACE" \
  -o jsonpath='{range .items[*]}{range .spec.containers[?(@.name=="agent")]}{.image}{"\n"}{end}{end}' \
  2>/dev/null \
  | sort | uniq -c | sort -rn \
  || printf 'WARN: cannot enumerate agent containers\n'

section "Known-gotcha quick check"
# Surface signals that map to the Phase 3 gotcha table.
LOGS_BUF=$(kubectl logs -n "$NAMESPACE" -l app=agent-stack-k8s --since="$SINCE" --tail=2000 2>/dev/null || true)
EVENTS_BUF=$(kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null || true)

check() {
  local label="$1"
  local pattern="$2"
  local source="$3"
  local buf
  case "$source" in
    logs)   buf="$LOGS_BUF" ;;
    events) buf="$EVENTS_BUF" ;;
    *)      buf="$LOGS_BUF$EVENTS_BUF" ;;
  esac
  if printf '%s' "$buf" | grep -qiE "$pattern"; then
    printf '  HIT: %s\n' "$label"
  fi
}

check "Possible 3.106.0 localHookPath regression — hooks not running" "localHookPath|hooks/(pre-command|pre-checkout) (skipped|not found)" logs
check "Possible hugepages lowercase serialization" "hugepages-2mi|invalid resource name" both
check "Possible chart workspace-dir change after upgrade" "BUILDKITE_BUILD_PATH|workspaceVolume|build-path" logs
check "Image pull failures (covers image-pull-policy gap)" "ImagePullBackOff|ErrImagePull" events
check "Stalled job with no actionable reason" "stalled|stale agent" logs
check "max-in-flight reached (controller pre-v0.27.0 bug)" "max-in-flight reached" logs
check "Missing queue tag on a scheduled job" "job missing 'queue' tag" logs
check "Init container exit code masking (pre-v0.29.0)" "ContainerStatusUnknown|stack_error" both

section "Done"
printf 'Capture the full stdout above when escalating to Buildkite Support.\n'
printf 'For the controller-provided log bundle, run:\n'
printf '  https://github.com/buildkite/agent-stack-k8s/blob/main/utils/log-collector\n'
