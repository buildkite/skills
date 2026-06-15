#!/usr/bin/env bash
set -euo pipefail

./scripts/build-power.sh

if [ -z "$(git status --porcelain -- steering)" ]; then
  exit 0
fi

annotate_drift() {
  {
    echo "The Kiro \`steering/\` files were out of date with the skills."
    echo
    echo "$1"
    echo
    echo "Status:"
    echo
    echo '```'
    git status --short -- steering
    echo '```'
    echo
    echo "Diff:"
    echo
    echo '```diff'
    git diff steering
    echo '```'
  } | if command -v buildkite-agent >/dev/null 2>&1; then
    buildkite-agent annotate --style "$2" --context kiro-drift
  else
    cat
  fi
}

repo_slug() {
  printf "%s" "$1" \
    | sed -E \
      -e 's#^git@github.com:##' \
      -e 's#^ssh://git@github.com/##' \
      -e 's#^https://[^/@]+@github.com/##' \
      -e 's#^https://github.com/##' \
      -e 's#^git://github.com/##' \
      -e 's#\.git$##'
}

if [ "${BUILDKITE_PULL_REQUEST:-false}" = "false" ]; then
  annotate_drift "Run \`./scripts/build-power.sh\` locally and commit the result." error
  exit 1
fi

pull_request_repo="$(repo_slug "${BUILDKITE_PULL_REQUEST_REPO:-}")"
pipeline_repo="$(repo_slug "${BUILDKITE_REPO:-}")"

if [ -z "$pull_request_repo" ] || [ "$pull_request_repo" != "$pipeline_repo" ]; then
  annotate_drift "This pull request is not from the pipeline repository, so CI will not push generated files back to the branch. Run \`./scripts/build-power.sh\` locally and commit the result." error
  exit 1
fi

git config user.name "${BUILDKITE_GIT_AUTHOR_NAME:-buildkite-agent}"
git config user.email "${BUILDKITE_GIT_AUTHOR_EMAIL:-buildkite-agent@users.noreply.github.com}"
git add steering
git commit -m "Regenerate Kiro steering" -- steering
git push origin "HEAD:${BUILDKITE_BRANCH}"

annotate_drift "CI regenerated and pushed the derived \`steering/\` files to this branch. A follow-up build should run on the new commit." info
