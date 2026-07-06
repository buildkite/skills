#!/usr/bin/env bash
#
# investigate-build.sh — gather everything Phase 1 (Orient) needs in one pass.
#
# Usage:
#   investigate-build.sh <build-url>
#   investigate-build.sh <pipeline-slug> <build-number>
#
# Examples:
#   investigate-build.sh https://buildkite.com/my-org/my-app/builds/42
#   investigate-build.sh my-org/my-app 42
#
# Output: a single Markdown bundle on stdout containing
#   1. Build state, branch, commit, creator, source, trigger relationship.
#   2. For every failed job: the last 100 lines of its log and its summary.
#   3. All annotations attached to the build.
#   4. All meta-data on the build.
#   5. The final state of the previous 10 builds on this pipeline (cohort signal).
#   6. A hint to fetch Kubernetes events if the agent stack is k8s.
#
# The script deliberately *gathers* — it does not diagnose. The SKILL.md body
# teaches the agent how to read the bundle.
#
# Requires: bk (https://github.com/buildkite/cli), jq.
#
# Exit codes:
#   0  bundle written
#   1  bad arguments
#   2  bk not authenticated / build not found

set -euo pipefail

usage() {
  cat >&2 <<EOF
Usage:
  $(basename "$0") <build-url>
  $(basename "$0") <pipeline-slug> <build-number>

The script gathers build context for Phase 1 (Orient) of the
buildkite-build-investigation skill. It does not diagnose.
EOF
  exit 1
}

LOG_TAIL_LINES="${LOG_TAIL_LINES:-100}"
COHORT_SIZE="${COHORT_SIZE:-10}"

# --- Parse arguments ------------------------------------------------------

if [ "$#" -eq 1 ]; then
  URL="$1"
  # Expect https://buildkite.com/<org>/<pipe>/builds/<n>
  if ! [[ "$URL" =~ ^https?://[^/]+/([^/]+)/([^/]+)/builds/([0-9]+) ]]; then
    echo "Could not parse build URL: $URL" >&2
    usage
  fi
  ORG="${BASH_REMATCH[1]}"
  PIPE="${BASH_REMATCH[2]}"
  NUM="${BASH_REMATCH[3]}"
  SLUG="${ORG}/${PIPE}"
elif [ "$#" -eq 2 ]; then
  SLUG="$1"
  NUM="$2"
  if ! [[ "$NUM" =~ ^[0-9]+$ ]]; then
    echo "Build number must be numeric: $NUM" >&2
    usage
  fi
else
  usage
fi

# --- Preflight ------------------------------------------------------------

command -v bk >/dev/null 2>&1 || { echo "bk not installed" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "jq not installed" >&2; exit 2; }

BUILD_JSON=$(bk build view "$NUM" --pipeline "$SLUG" --output json 2>/dev/null) || {
  echo "Could not fetch build $SLUG #$NUM. Run 'bk configure' or check the URL." >&2
  exit 2
}

# --- Header ---------------------------------------------------------------

printf '# Investigation bundle — %s #%s\n\n' "$SLUG" "$NUM"
printf 'Generated at: %s\n\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- 1. Build summary -----------------------------------------------------

printf '## 1. Build context\n\n'
printf '```json\n'
printf '%s\n' "$BUILD_JSON" | jq '{
  number, state, branch, commit, message,
  source, creator: .creator.name,
  started_at, finished_at, canceled_at,
  triggered_from,
  pipeline: .pipeline.slug,
  jobs_total: (.jobs | length),
  jobs_failed: ([.jobs[] | select(.state=="failed")] | length),
  jobs_passed: ([.jobs[] | select(.state=="passed")] | length)
}'
printf '```\n\n'

# --- 2. Failed-job logs and summaries ------------------------------------

printf '## 2. Failed jobs\n\n'
FAILED_JOBS=$(printf '%s\n' "$BUILD_JSON" | jq -r '.jobs[] | select(.state=="failed") | .id')

if [ -z "$FAILED_JOBS" ]; then
  printf '_No jobs in `failed` state. Check for `canceled` or stalled `running` jobs in section 1._\n\n'
else
  while IFS= read -r JOB_ID; do
    JOB_META=$(printf '%s\n' "$BUILD_JSON" | jq --arg id "$JOB_ID" '.jobs[] | select(.id==$id) | {name, label, exit_status, agent: .agent.name, started_at, finished_at}')
    printf '### Job `%s`\n\n' "$JOB_ID"
    printf '```json\n%s\n```\n\n' "$JOB_META"

    printf '**Summary:**\n\n```\n'
    bk job log "$JOB_ID" --pipeline "$SLUG" --build "$NUM" --print-job-summary 2>/dev/null || printf '(no summary available)\n'
    printf '```\n\n'

    printf '**Log tail (last %s lines):**\n\n```\n' "$LOG_TAIL_LINES"
    bk job log "$JOB_ID" --pipeline "$SLUG" --build "$NUM" 2>/dev/null | tail -n "$LOG_TAIL_LINES" || printf '(no log available)\n'
    printf '```\n\n'
  done <<< "$FAILED_JOBS"
fi

# --- 3. Annotations -------------------------------------------------------

printf '## 3. Annotations\n\n'
ANNOTATIONS=$(bk api "/organizations/${SLUG%/*}/pipelines/${SLUG#*/}/builds/${NUM}/annotations" 2>/dev/null || echo '[]')
ANN_COUNT=$(printf '%s\n' "$ANNOTATIONS" | jq 'length')
if [ "$ANN_COUNT" = "0" ]; then
  printf '_No annotations on this build._\n\n'
else
  printf '%s annotation(s):\n\n' "$ANN_COUNT"
  printf '```json\n'
  printf '%s\n' "$ANNOTATIONS" | jq '[.[] | {context, style, body_html_preview: (.body_html // "" | .[0:300])}]'
  printf '```\n\n'
fi

# --- 4. Meta-data ---------------------------------------------------------

printf '## 4. Meta-data\n\n'
META=$(bk api "/organizations/${SLUG%/*}/pipelines/${SLUG#*/}/builds/${NUM}/meta_data" 2>/dev/null || echo '{}')
META_COUNT=$(printf '%s\n' "$META" | jq 'length')
if [ "$META_COUNT" = "0" ]; then
  printf '_No meta-data set on this build._\n\n'
else
  printf '```json\n%s\n```\n\n' "$META"
fi

# --- 5. Cohort ------------------------------------------------------------

printf '## 5. Cohort — last %s builds on this pipeline\n\n' "$COHORT_SIZE"
COHORT=$(bk build list --pipeline "$SLUG" --output json 2>/dev/null | jq --argjson n "$COHORT_SIZE" '.[0:$n] | [.[] | {number, state, branch, finished_at, message: (.message // "")[0:80]}]' || echo '[]')
printf '```json\n%s\n```\n\n' "$COHORT"
FAIL_RATE=$(printf '%s\n' "$COHORT" | jq '[.[] | select(.state=="failed")] | length')
printf '_%s of the last %s builds failed._\n\n' "$FAIL_RATE" "$COHORT_SIZE"

# --- 6. K8s hint ----------------------------------------------------------

printf '## 6. Kubernetes events (if agent-stack-k8s)\n\n'
cat <<'EOF'
If the agent for any failed job ran on agent-stack-k8s, the platform
does not currently surface Kubernetes events into the build UI (A-1110).
Fetch them directly:

```bash
# Find the pod for the job
kubectl get pods -l buildkite.com/job-id=<job-id>

# Read events filtered to that pod
kubectl get events --field-selector involvedObject.name=<pod-name>
```

Look for `FailedScheduling`, `ImagePullBackOff`, `OOMKilled`, or pod-spec
rejection events. See `references/agent-disconnect-diagnostics.md`.
EOF
printf '\n'
