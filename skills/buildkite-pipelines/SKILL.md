---
name: buildkite-pipelines
description: >
  This skill should be used when the user asks to "write a pipeline",
  "add caching", "make this build faster", "show test failures in the build page",
  "add annotations", "only run tests when code changes", "set up dynamic pipelines",
  "add retry", "parallel steps", "matrix build", "add plugins", or
  "work with artifacts in pipeline YAML".
  Also use when the user mentions .buildkite/ directory, pipeline.yml,
  buildkite-agent pipeline upload, step types (command, wait, block, trigger,
  group, input), if_changed, notify, concurrency, or asks about Buildkite CI
  configuration.
---

# Buildkite Pipelines

Pipeline YAML is the core of Buildkite CI/CD. This skill covers writing, optimizing, and troubleshooting `.buildkite/pipeline.yml` — step types, caching, parallelism, annotations, retry, dynamic pipelines, matrix builds, plugins, notifications, artifacts, and concurrency.

## Quick Start

Create `.buildkite/pipeline.yml` in the repository root:

```yaml
steps:
  - label: ":hammer: Tests"
    command: "npm test"
    artifact_paths: "coverage/**/*"

  - wait

  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    branches: "main"
```

Set the pipeline's initial command in Buildkite to upload this file:

```yaml
steps:
  - label: ":pipeline: Upload"
    command: buildkite-agent pipeline upload
```

The agent reads `.buildkite/pipeline.yml` and uploads the steps to Buildkite for execution.

## Getting Started

### Directory structure

```
repo/
└── .buildkite/
    └── pipeline.yml    # Pipeline definition (required)
```

Buildkite looks for `.buildkite/pipeline.yml` by default. Override the path with `buildkite-agent pipeline upload path/to/other.yml`.

### How pipeline upload works

1. A build starts with a single step: `buildkite-agent pipeline upload`
2. The agent runs on the machine, reads `pipeline.yml`, and uploads steps to the Buildkite API
3. Buildkite schedules the uploaded steps across available agents
4. Steps run in parallel unless separated by `wait` steps or linked with `depends_on`

### First pipeline setup

1. Create a pipeline in Buildkite (UI or API)
2. Set the initial command to `buildkite-agent pipeline upload`
3. Commit `.buildkite/pipeline.yml` to the repository
4. Push — Buildkite triggers a build automatically via webhook

> For creating pipelines programmatically, see the **buildkite-api** skill.
> For agent and queue setup, see the **buildkite-platform-engineering** skill.

## Step Types

| Type | Purpose | Minimal syntax |
|------|---------|---------------|
| **command** | Run a shell command | `- command: "make test"` |
| **wait** | Block until all previous steps pass | `- wait` |
| **block** | Pause for manual approval | `- block: ":shipit: Release"` |
| **trigger** | Start a build on another pipeline | `- trigger: "deploy-pipeline"` |
| **group** | Visually group steps (collapsible) | `- group: "Tests"` with nested `steps:` |
| **input** | Collect user input before continuing | `- input: "Release version"` with `fields:` |

For detailed attributes and advanced examples of each step type, see `references/step-types-reference.md`.

## Caching

Caching dependencies is the single highest-impact optimization. Use the cache plugin with manifest-based invalidation:

```yaml
steps:
  - label: ":nodejs: Test"
    command: "npm ci && npm test"
    plugins:
      - cache#v1.8.1:
          paths:
            - "node_modules/"
          manifest: "package-lock.json"
```

The cache key derives from the manifest file hash. When `package-lock.json` changes, the cache rebuilds.

**Hosted agents** also support a built-in `cache` key (no plugin needed):

```yaml
steps:
  - label: ":nodejs: Test"
    command: "npm ci && npm test"
    cache:
      paths:
        - "node_modules/"
      key: "v1-deps-{{ checksum 'package-lock.json' }}"
```

> Hosted agent setup and instance shapes are covered by the **buildkite-platform-engineering** skill.

## Parallelism and Dependencies

### Parallel execution

Steps at the same level run in parallel by default. Use `parallelism` to fan out a single step:

```yaml
steps:
  - label: ":rspec: Tests %n"
    command: "bundle exec rspec"
    parallelism: 10
```

This creates 10 parallel jobs. Each receives `BUILDKITE_PARALLEL_JOB` (0-9) and `BUILDKITE_PARALLEL_JOB_COUNT` (10) as environment variables for splitting work.

> For intelligent test splitting based on timing data, see the **buildkite-test-engine** skill.

### Explicit dependencies

Use `depends_on` to express step-level dependencies without `wait`:

```yaml
steps:
  - label: "Build"
    key: "build"
    command: "make build"

  - label: "Unit Tests"
    depends_on: "build"
    command: "make test-unit"

  - label: "Integration Tests"
    depends_on: "build"
    command: "make test-integration"
```

Unit and integration tests run in parallel after build completes — no `wait` step needed.

## Annotations

Surface build results directly on the build page using `buildkite-agent annotate`. Supports Markdown and HTML.

```yaml
steps:
  - label: ":test_tube: Tests"
    command: |
      if ! make test 2>&1 | tee test-output.txt; then
        buildkite-agent annotate --style "error" --context "test-failures" < test-output.txt
        exit 1
      fi
      buildkite-agent annotate "All tests passed :white_check_mark:" --style "success" --context "test-results"
```

| Flag | Default | Description |
|------|---------|-------------|
| `--style` | `default` | Visual style: `default`, `info`, `warning`, `error`, `success` |
| `--context` | random | Unique ID — reusing a context replaces the annotation |
| `--append` | `false` | Append to existing annotation with same context |

Link to uploaded artifacts in annotations:

```yaml
- command: |
    buildkite-agent artifact upload "coverage/*"
    buildkite-agent annotate --style "info" 'Coverage: <a href="artifact://coverage/index.html">view report</a>'
```

## Retry

### Automatic retry

Retry transient failures by exit status:

```yaml
steps:
  - label: ":hammer: Build"
    command: "make build"
    retry:
      automatic:
        - exit_status: -1    # Agent lost
          limit: 2
        - exit_status: 143   # SIGTERM (spot instance termination)
          limit: 2
        - exit_status: 255   # Timeout or SSH failure
          limit: 2
        - exit_status: "*"   # Any non-zero exit
          limit: 1
```

### Manual retry

Control whether manual retries are allowed:

```yaml
retry:
  manual:
    allowed: false
    reason: "Deployment steps cannot be retried"
```

For comprehensive exit code tables and retry strategy recommendations, see `references/retry-and-error-codes.md`.

## Dynamic Pipelines

Generate pipeline steps at runtime based on repository state. Upload generated YAML with `buildkite-agent pipeline upload`:

```yaml
steps:
  - label: ":pipeline: Generate"
    command: |
      .buildkite/generate-pipeline.sh | buildkite-agent pipeline upload
```

Example generator script that runs tests only for changed services:

```bash
#!/bin/bash
set -euo pipefail
CHANGED=$(git diff --name-only HEAD~1)
cat <<YAML
steps:
YAML
for dir in services/*/; do
  svc=$(basename "$dir")
  if echo "$CHANGED" | grep -q "^services/$svc/"; then
    cat <<YAML
  - label: ":test_tube: $svc"
    command: "cd services/$svc && make test"
YAML
  fi
done
```

For advanced generator patterns (Python, monorepo, multi-stage), see `references/advanced-patterns.md`.

## Conditional Execution

### Step-level conditions

Use `if` to conditionally run steps based on build state:

```yaml
steps:
  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    if: build.branch == "main" && build.message !~ /\[skip deploy\]/
```

Common expressions: `build.branch`, `build.tag`, `build.message`, `build.source`, `build.env("VAR")`, `pipeline.default_branch`.

### Conditionally running plugins

Step-level `if` does **not** prevent plugins from executing. Wrap steps in a `group` to skip plugins entirely:

```yaml
steps:
  - group: ":docker: Build"
    if: build.env("DOCKER_PASSWORD") != null
    steps:
      - label: "Build image"
        command: "docker build -t myapp ."
        plugins:
          - docker-login#v2.1.0:
              username: myuser
              password-env: DOCKER_PASSWORD
```

## Matrix Builds

Run the same step across multiple configurations:

```yaml
steps:
  - label: "Test {{matrix.ruby}} on {{matrix.os}}"
    command: "bundle exec rake test"
    matrix:
      setup:
        ruby:
          - "3.2"
          - "3.3"
        os:
          - "ubuntu"
          - "alpine"
      adjustments:
        - with:
            ruby: "3.2"
            os: "alpine"
          skip: true  # Known incompatible
```

## Plugins

Add capabilities with 3-line YAML blocks. Pin versions for reproducibility:

```yaml
plugins:
  - docker-compose#v5.5.0:
      run: app
      config: docker-compose.ci.yml
```

| Plugin | Purpose |
|--------|---------|
| `cache#v1.8.1` | Dependency caching with manifest-based invalidation |
| `docker#v5.12.0` | Run steps inside a Docker container |
| `docker-compose#v5.5.0` | Build and run with Docker Compose |
| `artifacts#v1.9.4` | Download artifacts between steps |
| `test-collector#v2.0.0` | Upload test results to Test Engine |

Always pin plugin versions (e.g., `docker#v5.12.0` not `docker#v5`). Unpinned versions can break builds when plugins release new major versions.

## Notifications and Artifacts

### Pipeline-level notifications

```yaml
notify:
  - slack:
      channels:
        - "#builds"
      message: "Build {{build.number}} {{build.state}}"
    if: build.state == "failed"

steps:
  - command: "make test"
```

### Artifact upload and download

Upload artifacts from steps, download in later steps:

```yaml
steps:
  - label: "Build"
    command: "make build"
    artifact_paths: "dist/**/*"

  - wait

  - label: "Package"
    command: |
      buildkite-agent artifact download "dist/*" .
      make package
```

## Concurrency

Limit parallel execution of steps sharing a resource:

```yaml
steps:
  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    concurrency: 1
    concurrency_group: "deploy/production"
    concurrency_method: "eager"
```

| Attribute | Default | Description |
|-----------|---------|-------------|
| `concurrency` | unlimited | Max parallel jobs in this group |
| `concurrency_group` | — | Shared name across pipelines (required with `concurrency`) |
| `concurrency_method` | `ordered` | `ordered` (FIFO) or `eager` (next available) |
| `priority` | `0` | Higher numbers run first when queued |

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Missing `wait` between dependent steps | Steps run in parallel, second step fails because first hasn't finished | Add `- wait` or use `depends_on` |
| Using step-level `if` to skip plugins | Plugins still execute (they run before `if` is evaluated) | Wrap in a `group` with the `if` condition |
| Not pinning plugin versions | Builds break when plugin releases breaking change | Always use full semver: `plugin#v1.2.3` |
| Forgetting `concurrency_group` with `concurrency` | `concurrency` is ignored without a group name | Always pair `concurrency` with `concurrency_group` |
| `artifact_paths` glob doesn't match output | Artifacts silently not uploaded, downstream steps fail | Test glob pattern locally; use `**/*` for nested directories |
| Hardcoding parallel job split logic | Uneven test distribution, one slow job blocks the build | Use `parallelism: N` with timing-based splitting via Test Engine |
| Inline secrets in pipeline YAML | Secrets visible in build logs and Buildkite UI | Use cluster secrets or agent environment hooks |
| Using `retry.automatic` with `exit_status: "*"` and high limit | Genuine bugs retry repeatedly, wasting compute | Target specific exit codes; keep wildcard limit at 1 |

## Additional Resources

### Reference Files
- **`references/step-types-reference.md`** — Detailed attribute tables for all step types
- **`references/advanced-patterns.md`** — Dynamic pipeline generators, matrix adjustments, monorepo patterns, multi-stage pipelines
- **`references/retry-and-error-codes.md`** — Comprehensive exit code table, retry strategies by failure type

### Examples
- **`examples/basic-pipeline.yml`** — Minimal working pipeline (test, wait, deploy)
- **`examples/optimized-pipeline.yml`** — Full-featured pipeline with caching, parallelism, annotations, retry, artifacts, and notifications

## Further Reading

- [Defining pipeline steps](https://buildkite.com/docs/pipelines/configure/defining-steps)
- [Step types reference](https://buildkite.com/docs/pipelines/configure/step-types)
- [Pipeline upload](https://buildkite.com/docs/agent/v3/cli-pipeline)
- [Conditionals](https://buildkite.com/docs/pipelines/configure/conditionals)
- [Managing pipeline secrets](https://buildkite.com/docs/pipelines/security/secrets/managing)
