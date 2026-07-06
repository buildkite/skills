#!/usr/bin/env bash
#
# hosted-image-build-and-push.sh
#
# Builds a user-supplied Dockerfile, tags the resulting image with both a
# timestamp+SHA immutable tag and a rolling tag, and pushes both to the
# Buildkite hosted-agents internal container registry. Prints the resulting
# image references for use in a hosted queue's "Image URL" setting or in a
# pipeline.yml `image:` attribute.
#
# Fills the workflow gap surfaced by Linear A-500 (Groq): the only blessed
# image-update path was the Buildkite UI Dockerfile editor, which is
# non-iterative and breaks auth-bootstrap flows. This script provides the
# CLI alternative the docs sketch in YAML but do not ship as a runnable.
#
# Inputs (positional or env):
#   DOCKERFILE      — path to Dockerfile (default: ./Dockerfile)
#   IMAGE_NAME      — image name within the registry (default: base)
#   ROLLING_TAG     — rolling tag to also push (default: latest)
#   PLATFORM        — buildx platform spec (default: linux/amd64)
#   BUILD_CONTEXT   — Docker build context directory (default: current dir)
#
# Required environment:
#   BUILDKITE_HOSTED_REGISTRY_URL — set automatically inside a hosted-agent job;
#                                   must be exported when running locally.
#
# Outputs (stdout):
#   IMMUTABLE_REF=<registry>/<image>:<timestamp>-<sha>
#   ROLLING_REF=<registry>/<image>:<rolling-tag>
#
# Non-interactive. Exits non-zero on any failure. Validates required tools
# (`docker`, `git`) are present, validates Dockerfile contains the three
# required packages (`git`, `ca-certificates`, `bash`), and refuses to run
# without `BUILDKITE_HOSTED_REGISTRY_URL`.
#
# Usage examples:
#   ./hosted-image-build-and-push.sh
#   ./hosted-image-build-and-push.sh .buildkite/Dockerfile.build
#   DOCKERFILE=Dockerfile.ci IMAGE_NAME=ci-base ./hosted-image-build-and-push.sh

set -euo pipefail

DOCKERFILE="${1:-${DOCKERFILE:-./Dockerfile}}"
IMAGE_NAME="${IMAGE_NAME:-base}"
ROLLING_TAG="${ROLLING_TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
BUILD_CONTEXT="${BUILD_CONTEXT:-$(dirname "$DOCKERFILE")}"

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require() {
  command -v "$1" >/dev/null 2>&1 || die "required tool '$1' not found in PATH"
}

require docker
require git

if [[ -z "${BUILDKITE_HOSTED_REGISTRY_URL:-}" ]]; then
  die "BUILDKITE_HOSTED_REGISTRY_URL is not set. Inside a hosted-agent job it is provided automatically; locally, export it before running this script."
fi

if [[ ! -f "$DOCKERFILE" ]]; then
  die "Dockerfile not found at: $DOCKERFILE"
fi

if [[ ! -d "$BUILD_CONTEXT" ]]; then
  die "build context directory not found: $BUILD_CONTEXT"
fi

# Validate the three required tools appear in the Dockerfile. The agent fails
# silently at TLS handshake when ca-certificates is missing (see A-500 and
# linux/custom_agent_images.md). Catch the omission before pushing.
check_required_package() {
  local pkg="$1"
  if ! grep -Eq "(^|[^[:alnum:]_-])${pkg}([^[:alnum:]_-]|$)" "$DOCKERFILE"; then
    printf 'WARNING: %q not found in %s. The Buildkite-hosted agent requires git, ca-certificates, and bash in the image; omitting any will cause silent job-startup failures.\n' "$pkg" "$DOCKERFILE" >&2
  fi
}
check_required_package git
check_required_package ca-certificates
check_required_package bash

# Derive an immutable tag from current timestamp and short git SHA. Falls back
# to "nogit" when the build context is outside any git repo.
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if SHA="$(git -C "$BUILD_CONTEXT" rev-parse --short=12 HEAD 2>/dev/null)"; then
  IMMUTABLE_SUFFIX="${TIMESTAMP}-${SHA}"
else
  IMMUTABLE_SUFFIX="${TIMESTAMP}-nogit"
fi

IMMUTABLE_REF="${BUILDKITE_HOSTED_REGISTRY_URL}/${IMAGE_NAME}:${IMMUTABLE_SUFFIX}"
ROLLING_REF="${BUILDKITE_HOSTED_REGISTRY_URL}/${IMAGE_NAME}:${ROLLING_TAG}"

printf '==> Building %s\n' "$DOCKERFILE" >&2
printf '    Platform:   %s\n' "$PLATFORM" >&2
printf '    Context:    %s\n' "$BUILD_CONTEXT" >&2
printf '    Immutable:  %s\n' "$IMMUTABLE_REF" >&2
printf '    Rolling:    %s\n' "$ROLLING_REF" >&2

# Ensure buildx is available; create a builder if none configured.
if ! docker buildx inspect >/dev/null 2>&1; then
  docker buildx create --use --name buildkite-hosted-image-builder >/dev/null
fi

docker buildx build \
  --file "$DOCKERFILE" \
  --platform "$PLATFORM" \
  --tag "$IMMUTABLE_REF" \
  --tag "$ROLLING_REF" \
  --progress plain \
  --push \
  "$BUILD_CONTEXT"

printf '==> Push complete.\n' >&2
printf '\n'
printf 'IMMUTABLE_REF=%s\n' "$IMMUTABLE_REF"
printf 'ROLLING_REF=%s\n' "$ROLLING_REF"
printf '\n'
printf '# Set the queue Image URL to the immutable ref for reproducible builds:\n' >&2
printf '#   Agents -> cluster -> queue -> Base image -> Image URL\n' >&2
printf '#   %s\n' "$IMMUTABLE_REF" >&2
printf '# Or reference per-step in pipeline.yml:\n' >&2
printf '#   agents:\n' >&2
printf '#     image: "%s"\n' "$IMMUTABLE_REF" >&2
