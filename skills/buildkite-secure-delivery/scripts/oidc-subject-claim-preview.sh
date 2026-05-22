#!/usr/bin/env bash
#
# oidc-subject-claim-preview.sh
#
# Render the OIDC `sub` claim string a Buildkite agent would issue for a given
# job, without booting an agent. Useful for pasting into an AWS / Azure / GCP
# trust-policy condition.
#
# Inputs (CLI flags, with env-var fallbacks):
#   --org           BUILDKITE_ORGANIZATION_SLUG
#   --pipeline      BUILDKITE_PIPELINE_SLUG
#   --branch        BUILDKITE_BRANCH
#   --commit        BUILDKITE_COMMIT
#   --step          BUILDKITE_STEP_KEY
#
# Output: the default sub claim string on stdout. Format matches
#   `organization:ORG:pipeline:PIPELINE:ref:refs/heads/BRANCH:commit:COMMIT:step:STEP`
# as documented in `pipelines/security/oidc/aws.md`.
#
# Exit: 0 on success, 2 on missing input.

set -euo pipefail

org="${BUILDKITE_ORGANIZATION_SLUG:-}"
pipeline="${BUILDKITE_PIPELINE_SLUG:-}"
branch="${BUILDKITE_BRANCH:-}"
commit="${BUILDKITE_COMMIT:-}"
step="${BUILDKITE_STEP_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --org) org="$2"; shift 2 ;;
    --pipeline) pipeline="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --commit) commit="$2"; shift 2 ;;
    --step) step="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

missing=()
[[ -n "$org" ]] || missing+=("--org")
[[ -n "$pipeline" ]] || missing+=("--pipeline")
[[ -n "$branch" ]] || missing+=("--branch")
[[ -n "$commit" ]] || missing+=("--commit")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "missing required input(s): ${missing[*]}" >&2
  echo "pass via flag or set BUILDKITE_* env var" >&2
  exit 2
fi

# Branches are expressed as full Git refs in the sub claim.
if [[ "$branch" == refs/* ]]; then
  ref="$branch"
else
  ref="refs/heads/$branch"
fi

sub="organization:${org}:pipeline:${pipeline}:ref:${ref}:commit:${commit}:step:${step}"
printf '%s\n' "$sub"
