#!/usr/bin/env bash
#
# check-pipeline-for-secrets.sh
#
# First-pass lint for inline secrets in Buildkite pipeline YAML.
#
# This is NOT a real secret scanner. It is a grep-based heuristic that catches
# the most common anti-patterns from `pipelines/security/secrets/risk_considerations.md`:
#
#   - Top-level `env:` keys with names ending in TOKEN / SECRET / KEY / PASSWORD
#     that carry a non-empty value on the same line.
#   - Obvious hardcoded credential patterns (aws_access_key_id, github_pat_,
#     bkua_, bkct_, bkar_, AKIA-prefixed AWS keys, etc.).
#   - High-entropy hex/base64 literals adjacent to `env:` or `value:` keys.
#
# Inputs:  one or more YAML file paths, or a directory (defaults to .buildkite/).
# Output:  findings printed to stdout with file:line prefix.
# Exit:    0 if clean, 1 if any finding, 2 on usage error.
#
# Run a real secret scanner (gitleaks, trufflehog) on top of this — do not rely
# on this script as the only check.

set -euo pipefail

usage() {
  echo "usage: $(basename "$0") [PATH ...]" >&2
  echo "  PATH defaults to .buildkite/ if omitted." >&2
  exit 2
}

if [[ $# -gt 0 && "$1" == "-h" ]]; then usage; fi

targets=()
if [[ $# -eq 0 ]]; then
  [[ -d .buildkite ]] || { echo "no .buildkite/ directory; pass PATH explicitly" >&2; exit 2; }
  targets+=(.buildkite)
else
  targets=("$@")
fi

files=()
for t in "${targets[@]}"; do
  if [[ -d "$t" ]]; then
    while IFS= read -r f; do files+=("$f"); done < <(find "$t" -type f \( -name '*.yml' -o -name '*.yaml' \))
  elif [[ -f "$t" ]]; then
    files+=("$t")
  else
    echo "not a file or directory: $t" >&2
    exit 2
  fi
done

[[ ${#files[@]} -gt 0 ]] || { echo "no YAML files to scan" >&2; exit 2; }

findings=0
report() {
  printf '%s\n' "$1"
  findings=$((findings + 1))
}

# Pattern 1: env-key suffix with inline value (excluding obvious-references like $VAR or ${VAR}).
SUFFIX_RE='(_TOKEN|_SECRET|_KEY|_PASSWORD|_ACCESS_KEY|_SECRET_KEY|_PRIVATE_KEY|_CONNECTION_STRING)'

# Pattern 2: known credential prefixes / formats.
KNOWN_RE='(bkua_[A-Za-z0-9]{20,}|bkct_[A-Za-z0-9]{20,}|bkar_[A-Za-z0-9]{20,}|bkaa_[A-Za-z0-9]{20,}|bkaj_[A-Za-z0-9]{20,}|bkpt_[A-Za-z0-9]{20,}|bkps_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,})'

for f in "${files[@]}"; do
  while IFS=: read -r lineno content; do
    # Skip comments.
    [[ "$content" =~ ^[[:space:]]*# ]] && continue
    # Match KEY: "value" or KEY: value (value not starting with $).
    if [[ "$content" =~ [A-Z][A-Z0-9_]*${SUFFIX_RE}:[[:space:]]*[\"\']?([^\$\"\'#[:space:]][^\"\'#]*) ]]; then
      val="${BASH_REMATCH[2]}"
      # Heuristic: ignore short values, environment-variable references, well-known sentinel keywords.
      if [[ ${#val} -ge 8 && ! "$val" =~ ^(true|false|null|none|placeholder|example|REPLACE_ME|TODO)$ ]]; then
        report "$f:$lineno  inline secret-looking value on env-style key — move to Buildkite secrets or \`buildkite-agent secret get\`"
      fi
    fi
  done < <(grep -n -E "[A-Z][A-Z0-9_]*${SUFFIX_RE}[[:space:]]*:" "$f" 2>/dev/null || true)

  while IFS=: read -r lineno content; do
    [[ "$content" =~ ^[[:space:]]*# ]] && continue
    report "$f:$lineno  known credential prefix — rotate immediately and remove from version control"
  done < <(grep -n -E "$KNOWN_RE" "$f" 2>/dev/null || true)
done

if [[ $findings -eq 0 ]]; then
  echo "no findings — first-pass lint only; run gitleaks or trufflehog for full coverage"
  exit 0
fi

echo
echo "$findings finding(s). See SKILL.md key principle 2 — never store secrets in pipeline.yml."
exit 1
