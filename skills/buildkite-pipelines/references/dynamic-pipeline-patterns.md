# Dynamic Pipeline Patterns

Patterns for generating pipeline steps at runtime that go beyond the basic monorepo and `if_changed` patterns covered in `references/advanced-patterns.md`. This reference focuses on fan-out/fan-in, SDK-based generation, runtime decision-making, and finalizer patterns.

For monorepo change detection, basic `if_changed`, and matrix builds, see `references/advanced-patterns.md`.
For group step behaviour in dynamic pipelines, see `references/group-steps.md`.
For common failure modes, see `references/dynamic-pipeline-troubleshooting.md`.

## Contents

1. [Fan-out and fan-in with depends_on](#fan-out-and-fan-in-with-depends_on)
2. [SDK-based pipeline generation](#sdk-based-pipeline-generation)
3. [The handler pattern: read state, decide, upload](#the-handler-pattern-read-state-decide-upload)
4. [Finalizer and always-run steps](#finalizer-and-always-run-steps)
5. [Branch-based routing](#branch-based-routing)
6. [Serial gate chains](#serial-gate-chains)
7. [Trigger-based fan-out for large workloads](#trigger-based-fan-out-for-large-workloads)
8. [Centralised pipeline generation](#centralised-pipeline-generation)

## Fan-out and fan-in with depends_on

Dynamic generation plus `depends_on` produces fan-out/fan-in graphs that do not fit in a single `parallelism:` step or a static matrix. The pattern: emit one step per work item with a stable `key:`, then emit a single downstream step that depends on every upstream key.

```bash
#!/bin/bash
set -euo pipefail

SERVICES="api web worker payments notifications"

echo "steps:"

# Fan out: one test step per service
for svc in $SERVICES; do
  cat <<YAML
  - label: ":test_tube: Test ${svc}"
    command: "make test -C services/${svc}"
    key: "test-${svc}"
    retry:
      automatic:
        - exit_status: -1
          limit: 2
YAML
done

# Fan in: single step that waits for every upstream key
FAN_IN_DEPS=$(for svc in $SERVICES; do echo "      - \"test-${svc}\""; done)
cat <<YAML
  - label: ":white_check_mark: All services passed"
    command: "echo 'all green'"
    key: "tests-complete"
    depends_on:
${FAN_IN_DEPS}
YAML
```

Use this instead of `wait` when some downstream work can start before every upstream finishes. `wait` blocks all prior steps; `depends_on` expresses exact dependencies, letting unrelated steps run in parallel. Combine with `allow_dependency_failure: true` on the fan-in step to report partial success rather than block.

## SDK-based pipeline generation

Any language that emits valid YAML or JSON on stdout works as a generator. Shell and Python are the most common. For type checking, IDE support, and unit-testable generators, use the [Buildkite SDK](https://github.com/buildkite/buildkite-sdk) — available for JavaScript/TypeScript, Python, Go, and Ruby.

```python
#!/usr/bin/env python3
"""Generate test steps programmatically with the Buildkite SDK."""
from buildkite_sdk import Pipeline, CommandStep

pipeline = Pipeline()

services = ["api", "web", "worker"]
retry_policy = {
    "automatic": [
        {"exit_status": -1, "limit": 2},
        {"exit_status": 143, "limit": 1},
    ]
}

# Fan out
for svc in services:
    step = CommandStep()
    step.label = f":test_tube: Test {svc}"
    step.command = [f"make test -C services/{svc}"]
    step.key = f"test-{svc}"
    step.retry = retry_policy
    pipeline.add_step(step)

# Fan in
fan_in = CommandStep()
fan_in.label = ":white_check_mark: All services passed"
fan_in.command = ["echo 'all green'"]
fan_in.key = "tests-complete"
fan_in.depends_on = [f"test-{svc}" for svc in services]
pipeline.add_step(fan_in)

print(pipeline.to_yaml())
```

Use in the pipeline:

```yaml
steps:
  - label: ":pipeline: Generate"
    command: "python .buildkite/generate.py | buildkite-agent pipeline upload"
```

Reach for the SDK when generators need:

- Dependency resolution across many steps (computing `depends_on` from a graph).
- Shared retry / timeout / queue policies applied consistently across every step.
- Conditional logic that becomes hard to read in bash heredocs.
- Unit tests for the generator itself.

Plain shell is still the right choice when the generator is short and produces a small number of steps.

## The handler pattern: read state, decide, upload

The core dynamic pipeline archetype: a step reads runtime state (meta-data, artifacts, API responses, git diff), decides what to do, and uploads the next phase of the pipeline. This pattern underpins multi-stage pipelines that adapt mid-flight.

```bash
#!/bin/bash
# .buildkite/scripts/phase2-deploy.sh
# Runs after an earlier "build" step uploaded a manifest artifact.
set -euo pipefail

# Read runtime state: what did the build produce?
buildkite-agent artifact download "build-manifest.json" .
SERVICES=$(jq -r '.services[]' build-manifest.json)

# Read runtime state: did a previous step flag a hotfix deploy?
DEPLOY_MODE=$(buildkite-agent meta-data get "deploy-mode" --default "standard")

# Decide and generate
STEPS="steps:\n"
for svc in $SERVICES; do
  if [[ "$DEPLOY_MODE" == "hotfix" ]]; then
    # Hotfix: skip staging, deploy direct to production
    STEPS+="  - label: \":fire: Hotfix deploy ${svc}\"\n"
    STEPS+="    command: \"make deploy-production SERVICE=${svc}\"\n"
    STEPS+="    key: \"deploy-${svc}\"\n"
    STEPS+="    concurrency: 1\n"
    STEPS+="    concurrency_group: \"deploy/${svc}/production\"\n"
  else
    STEPS+="  - label: \":rocket: Deploy ${svc} to staging\"\n"
    STEPS+="    command: \"make deploy-staging SERVICE=${svc}\"\n"
    STEPS+="    key: \"deploy-staging-${svc}\"\n"
    STEPS+="    concurrency: 1\n"
    STEPS+="    concurrency_group: \"deploy/${svc}/staging\"\n"
  fi
done

echo -e "$STEPS" | buildkite-agent pipeline upload
```

The inputs available to a handler step:

| Source | Use for | Access via |
|--------|---------|-----------|
| Build meta-data | Small key/value decisions set by earlier steps | `buildkite-agent meta-data get KEY` |
| Artifacts | Files produced by earlier steps (manifests, test reports) | `buildkite-agent artifact download 'path'` |
| Environment variables | Build-level context (`BUILDKITE_BRANCH`, `BUILDKITE_MESSAGE`, …) | Shell `$VAR` |
| Git state | Changed files, tags, commit metadata | `git diff`, `git log`, `git describe` |
| External APIs | Feature flags, deployment approvals, issue tracker state | `curl`, language HTTP clients |

See the **buildkite-agent-runtime** skill for the full `meta-data` and `artifact` subcommand reference.

### Replace pattern for clean build pages

A variant of the handler pattern uses `--replace` to swap the bootstrap step with the real pipeline before the UI settles:

```yaml
# .buildkite/pipeline.yml (gets replaced)
steps:
  - label: ":pipeline: Setup"
    command: ".buildkite/generate.sh | buildkite-agent pipeline upload --replace"
```

`--replace` removes all pending steps before inserting the new ones. Jobs already running are not affected. The build page shows only the generated pipeline, not the bootstrap step.

**Caution.** If the generator fails after `--replace` removes the existing steps but before new steps are uploaded, the build has no steps. Always pair with `set -euo pipefail` and consider `--dry-run` validation before calling the real upload.

Do not use `--replace` when multiple steps each upload their own portion of the pipeline — a retry of one step would wipe steps uploaded by others.

## Finalizer and always-run steps

Built-in pipeline primitives do not have an "always run, regardless of earlier failures" step type. The `pre-exit` agent hook fills that gap: it runs after every step, including failed ones, and can call `pipeline upload` to inject a finalizer step.

### Cleanup that runs even after failure

```bash
# .buildkite/hooks/pre-exit
#!/bin/bash

# Only inject the cleanup once per build
if [[ "${BUILDKITE_STEP_KEY:-}" == "deploy" ]]; then
  buildkite-agent pipeline upload <<'YAML'
steps:
  - label: ":broom: Cleanup deploy artifacts"
    command: ".buildkite/scripts/cleanup.sh"
    key: "cleanup"
    allow_dependency_failure: true
YAML
fi
```

`allow_dependency_failure: true` on the cleanup step lets it run even when the deploy failed. Without it, a failed upstream step would block the cleanup.

### Fallback step when the primary step fails

```bash
# .buildkite/hooks/pre-exit
#!/bin/bash

if [[ "$BUILDKITE_COMMAND_EXIT_STATUS" -ne 0 ]] && \
   [[ "${BUILDKITE_STEP_KEY:-}" == "primary-deploy" ]]; then
  buildkite-agent pipeline upload <<YAML
steps:
  - label: ":rewind: Rollback ${BUILDKITE_LABEL}"
    command: "make rollback"
    agents:
      queue: "${BUILDKITE_AGENT_META_DATA_QUEUE:-default}"
    retry:
      automatic:
        - exit_status: "*"
          limit: 1
YAML
fi
```

The unquoted heredoc (`<<YAML`) expands `${BUILDKITE_LABEL}` at upload time — intentional here because the label identifies the failed step.

### Retry on different infrastructure (OOM, spot preemption)

Built-in `retry: automatic` retries on the **same queue**. For failures caused by resource constraints (OOM, disk exhaustion, spot preemption), the same queue does not help. Use a `pre-exit` hook to detect the failure and upload a new step targeting a bigger queue:

```bash
# .buildkite/hooks/pre-exit
#!/bin/bash

if [[ "$BUILDKITE_COMMAND_EXIT_STATUS" == "137" ]]; then
  echo "OOM detected. Retrying on memory-optimised agent."
  buildkite-agent pipeline upload <<YAML
steps:
  - label: ":repeat: Retry ${BUILDKITE_LABEL} (memory-optimised)"
    command: "${BUILDKITE_COMMAND}"
    agents:
      queue: "memory-optimised"
    retry:
      automatic:
        - exit_status: 137
          limit: 1
YAML
fi
```

Two important notes:

- **Unquoted heredoc (`<<YAML`)** is correct here — `${BUILDKITE_LABEL}` and `${BUILDKITE_COMMAND}` need to expand at upload time.
- **`limit: 1`** on the uploaded retry step prevents infinite retry loops when the bigger agent also runs out of memory.

This pattern works for any infrastructure-class failure where a different queue would help. For exit code reference, see `references/retry-and-error-codes.md`. For agent hook configuration, see the **buildkite-agent-infrastructure** skill.

## Branch-based routing

Generate different pipelines per branch. Common shape for repos where `main`, `release/*`, and feature branches have very different needs:

```bash
#!/bin/bash
set -euo pipefail

BRANCH="$BUILDKITE_BRANCH"

case "$BRANCH" in
  main)
    cat <<'YAML' | buildkite-agent pipeline upload
steps:
  - group: ":test_tube: Tests"
    key: "tests"
    steps:
      - label: ":rspec: Unit"
        command: "make test-unit"
        key: "unit"
      - label: ":earth_americas: Integration"
        command: "make test-integration"
        key: "integration"
  - wait
  - group: ":rocket: Deploy"
    key: "deploy"
    steps:
      - label: ":rocket: Deploy staging"
        command: "make deploy-staging"
        key: "deploy-staging"
      - wait
      - label: ":rocket: Deploy production"
        command: "make deploy-production"
        key: "deploy-prod"
        concurrency: 1
        concurrency_group: "deploy/production"
YAML
    ;;
  release/*)
    cat <<'YAML' | buildkite-agent pipeline upload
steps:
  - label: ":test_tube: Full test suite"
    command: "make test-all"
    key: "full-tests"
    parallelism: 10
  - wait
  - block: ":shipit: Approve release"
    key: "approve"
  - wait
  - label: ":rocket: Deploy production"
    command: "make deploy-production"
    depends_on: "approve"
    concurrency: 1
    concurrency_group: "deploy/production"
YAML
    ;;
  *)
    # PR and feature branches: just lint and test
    cat <<'YAML' | buildkite-agent pipeline upload
steps:
  - label: ":lint-roller: Lint"
    command: "make lint"
    key: "lint"
  - label: ":rspec: Tests"
    command: "make test"
    key: "tests"
YAML
    ;;
esac
```

Use `<<'YAML'` (quoted heredoc) to prevent shell expansion of `$` characters in the YAML. Use `<<YAML` (unquoted) only when shell variable expansion in the template is intentional.

This pattern is the upgrade path when `if: build.branch == "main"` filters on individual steps become unreadable or when per-branch step counts diverge enough that one static pipeline can't express them cleanly.

## Serial gate chains

Chain multiple phases, where each phase generates the next based on its output. Useful when later steps genuinely depend on what earlier steps produced — not just their success.

Phase 1 builds and uploads a manifest:

```yaml
# .buildkite/pipeline.yml — phase 1
steps:
  - label: ":hammer: Build"
    command: "make build && buildkite-agent artifact upload 'dist/*'"
    key: "build"
  - wait
  - label: ":test_tube: Generate test plan"
    command: ".buildkite/generate-tests.sh | buildkite-agent pipeline upload"
    key: "gen-tests"
```

Phase 2 reads the manifest and emits per-component test steps plus a deploy gate:

```bash
#!/bin/bash
# .buildkite/generate-tests.sh — phase 2
set -euo pipefail

# Download the build manifest to see what was built
buildkite-agent artifact download "dist/manifest.json" .
COMPONENTS=$(jq -r '.components[]' dist/manifest.json)

STEPS="steps:\n"
for component in $COMPONENTS; do
  STEPS+="  - label: \":test_tube: Test ${component}\"\n"
  STEPS+="    command: \"make test-${component}\"\n"
  STEPS+="    key: \"test-${component}\"\n"
done

# Gate for deployment
STEPS+="  - wait\n"
STEPS+="  - block: \":shipit: Deploy?\"\n"
STEPS+="    key: \"deploy-gate\"\n"
STEPS+="  - wait\n"
STEPS+="  - label: \":rocket: Deploy\"\n"
STEPS+="    command: \"make deploy\"\n"
STEPS+="    concurrency: 1\n"
STEPS+="    concurrency_group: \"deploy/production\"\n"

echo -e "$STEPS" | buildkite-agent pipeline upload
```

Each phase has full access to what prior phases produced (artifacts, meta-data, API state), so the pipeline shape can adapt mid-flight. Pair with `--replace` on the bootstrap step only when a single uploader owns the entire downstream pipeline.

## Trigger-based fan-out for large workloads

Workloads that exceed a single build's limits can fan out across separate builds using trigger steps:

```bash
#!/bin/bash
set -euo pipefail

CHANGED_SERVICES=$(git diff --name-only HEAD~1 | grep '^services/' | cut -d/ -f2 | sort -u)

STEPS="steps:\n"
for svc in $CHANGED_SERVICES; do
  STEPS+="  - trigger: \"service-${svc}-tests\"\n"
  STEPS+="    label: \":rocket: Test ${svc}\"\n"
  STEPS+="    build:\n"
  STEPS+="      branch: \"${BUILDKITE_BRANCH}\"\n"
  STEPS+="      commit: \"${BUILDKITE_COMMIT}\"\n"
  STEPS+="      message: \"Tests for ${svc} (triggered by ${BUILDKITE_BUILD_NUMBER})\"\n"
done

echo -e "$STEPS" | buildkite-agent pipeline upload
```

Each triggered build has its own upload and job limits. A monorepo with 20 services × 100 steps each would need 2,000 jobs in one build — with triggers, the parent build has only 20 trigger steps and each service build handles its own 100 steps independently.

## Centralised pipeline generation

Large organisations often centralise generator logic so every team gets consistent pipeline patterns:

```text
infra-repo/
├── pipeline-generator/
│   ├── generate.py          # Main generator
│   ├── templates/
│   │   ├── standard.yml     # Standard test + deploy
│   │   ├── monorepo.yml     # Monorepo with change detection
│   │   └── ml-training.yml  # ML training pipeline
│   └── config/
│       └── defaults.yml     # Org-wide defaults (retry, queues, timeouts)
```

Each service repo's `.buildkite/pipeline.yml` calls the centralised generator:

```yaml
steps:
  - label: ":pipeline: Generate"
    command: |
      git clone git@github.com:example-org/infra-repo.git /tmp/infra
      python /tmp/infra/pipeline-generator/generate.py \
        --config .buildkite/service-config.yml \
        | buildkite-agent pipeline upload
```

The centralised generator applies org-wide defaults (retry policies, queue targeting, timeout limits) while letting each service override specifics. This pattern prevents every team from independently rediscovering the same pitfalls.

## Breaking the implicit dependency on the calling step

In DAG mode (any pipeline that contains a group step, or any pipeline using `depends_on`), steps uploaded by `buildkite-agent pipeline upload` inherit an implicit dependency on the step that uploaded them. They wait until the upload step finishes before becoming runnable.

Sometimes that's not what you want. A finalizer step uploaded from a `pre-exit` hook needs to run regardless; a sibling step generated to run alongside the calling step shouldn't wait. To remove the implicit dependency, set `depends_on: ~` (or the equivalent `depends_on: []`):

```yaml
# Generated by an upload step that should NOT block this work
- label: ":wave: Independent of the uploader"
  command: "make independent-task"
  depends_on: ~
```

`~` is YAML for null. `[]` is an empty list. Both clear the implicit dependency. The same pattern unblocks an uploaded step from any otherwise-implicit `wait` ahead of it:

```yaml
- wait: ~

- label: ":fire: Run before the wait above"
  command: "make hotfix"
  depends_on: ~
```

This is documented on the [dependencies page](https://buildkite.com/docs/pipelines/configure/dependencies) — the dynamic-pipelines case (uploaded steps inheriting a wait on the calling step) is the most common reason to reach for it. Use this when:

- A `pre-exit` hook uploads a finalizer / cleanup step that must run regardless of the calling step's outcome (combine with `allow_dependency_failure: true` if it depends on other failing steps).
- A generator emits steps that should start in parallel with later siblings of the calling step rather than waiting for it.
- A bootstrap pipeline contains a barrier `wait` that an uploaded step needs to bypass.

## Merge-queue conditional generator

GitHub merge queue builds are created from `merge_group` webhook events and carry the merge group's base commit in `BUILDKITE_MERGE_QUEUE_BASE_COMMIT`. On every other build (regular branch builds, PR builds, manually triggered builds) the variable is unset. Use it as a conditional gate to emit different steps for merge-queue builds versus everything else:

```bash
#!/bin/bash
set -euo pipefail

if [ -n "${BUILDKITE_MERGE_QUEUE_BASE_COMMIT:-}" ]; then
  # Merge-queue build: full integration suite + deploy gate
  cat <<YAML | buildkite-agent pipeline upload
steps:
  - label: ":test_tube: Full integration suite"
    command: "make test-all"
    key: "test-all"
  - wait
  - label: ":rocket: Deploy"
    command: "make deploy"
    key: "deploy"
    concurrency: 1
    concurrency_group: "deploy/production"
YAML
else
  # Regular branch build: just lint + unit tests
  cat <<YAML | buildkite-agent pipeline upload
steps:
  - label: ":lint-roller: Lint"
    command: "make lint"
    key: "lint"
  - label: ":rspec: Unit tests"
    command: "make test-unit"
    key: "unit"
YAML
fi
```

Use `[ -n "${BUILDKITE_MERGE_QUEUE_BASE_COMMIT:-}" ]` (with the `:-` default) so the test works when the variable is unset and `set -u` is active.

When pairing this with `if_changed`, enable the **Use base commit when making `if_changed` comparisons** setting in the pipeline's GitHub configuration. Without it, `if_changed` for merge-queue builds compares HEAD against the previous merge group rather than against the merge group's base commit, which over-includes file changes from merge groups ahead in the queue. With it, `if_changed` only considers files in the PR the merge group represents.

This pattern is the standard upgrade path when the merge-queue build needs to do meaningfully more (or less) than a regular branch build, and a single static pipeline with `if:` conditionals on every step has become unreadable.

See the [GitHub merge queue tutorial](https://buildkite.com/docs/pipelines/tutorials/github-merge-queue) for the full set of merge-queue properties (`build.merge_queue.base_commit`, `build.merge_queue.base_branch`) and the conditional/env-var mapping.

## Further Reading

- [Dynamic pipelines overview](https://buildkite.com/docs/pipelines/configure/dynamic-pipelines.md)
- [`pipeline upload` CLI reference](https://buildkite.com/docs/agent/v3/cli-pipeline.md)
- [Buildkite SDK](https://github.com/buildkite/buildkite-sdk)
- [Agent hooks](https://buildkite.com/docs/agent/v3/hooks.md)
- [Build meta-data](https://buildkite.com/docs/pipelines/configure/build-meta-data.md)
- [`depends_on` and empty dependencies](https://buildkite.com/docs/pipelines/configure/dependencies)
- [GitHub merge queue tutorial](https://buildkite.com/docs/pipelines/tutorials/github-merge-queue)
