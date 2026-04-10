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

Buildkite looks for `.buildkite/pipeline.yml` by default. Override the path with `buildkite-agent pipeline upload path/to/other.yml`.

> For creating pipelines programmatically, see the **buildkite-api** skill.
> For agent and queue setup, see the **buildkite-agent-infrastructure** skill.

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

> Hosted agent setup and instance shapes are covered by the **buildkite-agent-infrastructure** skill.

## Fast-Fail and Non-Blocking Steps

Cancel remaining jobs immediately when any job fails:

```yaml
steps:
  - label: ":rspec: Tests"
    command: "bundle exec rspec"
    cancel_on_build_failing: true
```

Use `soft_fail` for steps that should not block the build (security scans, linting, coverage):

```yaml
steps:
  - label: ":shield: Security Scan"
    command: "scripts/security-scan.sh"
    soft_fail:
      - exit_status: 1
```

A soft-failed step shows as a warning in the UI but does not fail the build. Combine with `continue_on_failure: true` on a wait step to let downstream steps run regardless.

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

For debugging, upload the generated YAML as an artifact before piping to upload:

```yaml
steps:
  - label: ":pipeline: Generate"
    command: |
      .buildkite/generate-pipeline.sh | tee generated-pipeline.yml
      buildkite-agent artifact upload generated-pipeline.yml
      cat generated-pipeline.yml | buildkite-agent pipeline upload
```

Keep dynamically generated pipelines under **~500 steps** for optimal UI and processing performance. For larger monorepos, use orchestrator pipelines with trigger steps to spawn child pipelines.

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

For the full list of condition expressions, see [Conditionals](https://buildkite.com/docs/pipelines/configure/conditionals.md).

**`[skip ci]` gotcha:** Buildkite only checks the HEAD commit message for `[skip ci]` / `[ci skip]`. If the tag is in an earlier commit in a multi-commit push, the build still triggers.

### Directory-based step filtering (if_changed)

Skip steps when relevant files haven't changed. Only applied by the Buildkite agent when uploading a pipeline. See https://buildkite.com/docs/pipelines/configure/dynamic-pipelines/if-changed.md.

```yaml
steps:
  - label: ":nodejs: Frontend tests"
    command: "npm test"
    if_changed:
      - "src/frontend/**"
      - "package.json"
```

For exclude patterns and monorepo configurations, see `references/advanced-patterns.md`.

For large monorepos, use the [Sparse Checkout plugin](https://github.com/buildkite-plugins/sparse-checkout-buildkite-plugin) to check out only `.buildkite/` for the upload step — dramatically faster pipeline uploads.

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

Valid properties inside each `adjustments` entry: `with`, `skip`, `soft_fail`, `env`. The `agents:` key is **not valid** inside `adjustments` — Buildkite rejects the pipeline with "agents is not a valid property on the matrix.adjustments configuration". To route matrix combinations to different queues (e.g., Linux vs Windows agents), use separate steps or a dynamic pipeline generator.

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

For **private organizational plugins**, use full Git URLs — the shorthand syntax only works for public plugins:

```yaml
plugins:
  - ssh://git@github.com/my-org/my-plugin.git#v1.0.0:
      config: value
```

## Notifications and Artifacts

Add pipeline-level `notify:` above `steps:` to send Slack, email, or webhook notifications on build state changes. See [Notifications](https://buildkite.com/docs/pipelines/configure/notifications.md) for syntax.

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

When using artifacts in a Docker build, download artifacts before starting the Docker build since `buildkite-agent` is not available inside the container:

```yaml
steps:
  - label: "Docker build"
    command: |
      buildkite-agent artifact download "dist/*" .
      docker build -t myapp .
```

## Concurrency

Limit parallel execution of steps sharing a resource. Always pair `concurrency` with `concurrency_group` — without a group name, the limit is silently ignored.

```yaml
steps:
  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    concurrency: 1
    concurrency_group: "deploy/production"
    concurrency_method: "eager"
```

Use `concurrency_method: "eager"` (next available) for independent jobs like deploys. Use the default `"ordered"` (FIFO) when execution order matters. Set `priority` (default `0`, higher = first) to control which queued jobs run next.

For full concurrency configuration options, see [Controlling Concurrency](https://buildkite.com/docs/pipelines/configure/workflows/controlling-concurrency.md).

> For triggering, watching, and debugging pipelines from the terminal, see the **buildkite-cli** skill.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Missing `wait` between dependent steps | Steps run in parallel, second step fails because first hasn't finished | Add `- wait` or use `depends_on:` |
| Using only `wait` steps for all dependencies | Valid but non-idiomatic; `wait` blocks ALL prior steps, making it impossible to run independent steps in parallel | Give named steps a `key:` and use `depends_on: "key"` to express fine-grained dependencies; reserve `wait` for unconditional barriers |
| No `plugins:` in pipeline for package install steps | Dependencies reinstalled from scratch on every build, slowing builds and inflating costs | Add `cache` plugin (or the built-in `cache:` key for hosted agents) to cache `node_modules/`, `.gradle/`, etc. See the Caching section above |
| Using step-level `if` to skip plugins | Plugins still execute (they run before `if` is evaluated) | Wrap in a `group` with the `if` condition |
| Not pinning plugin versions | Builds break when plugin releases breaking change | Always use full semver: `plugin#v1.2.3` |
| Forgetting `concurrency_group` with `concurrency` | `concurrency` is ignored without a group name | Always pair `concurrency` with `concurrency_group` |
| `artifact_paths` glob doesn't match output | Artifacts silently not uploaded, downstream steps fail | Test glob pattern locally; use `**/*` for nested directories |
| Hardcoding parallel job split logic | Uneven test distribution, one slow job blocks the build | Use `parallelism: N` with timing-based splitting via Test Engine |
| Inline secrets in pipeline YAML | Secrets visible in build logs and Buildkite UI | Use cluster secrets or agent environment hooks |
| Using `retry.automatic` with `exit_status: "*"` and high limit | Genuine bugs retry repeatedly, wasting compute | Target specific exit codes; keep wildcard limit at 1 |
| Using `agents:` inside `matrix.adjustments` | Pipeline upload fails: "agents is not a valid property on the matrix.adjustments configuration" | Remove `agents:` from `adjustments`; use separate steps per platform or a dynamic pipeline generator for per-combination queue routing |
| Build fails but all visible steps passed | A trigger step started a child pipeline that failed, or a step was cancelled rather than unblocked | Check the triggered pipeline's build status; inspect block steps for cancellations |
| Pipeline upload fails with no clear error | YAML syntax error or agent-side issue not shown in build logs | Validate YAML locally; check agent logs on the host machine for detailed upload errors; run `buildkite-agent pipeline upload --debug` |
| Fork builds enabled on public pipelines | Contributors can modify `pipeline.yml` to extract secrets | Disable fork builds in pipeline settings for public repos; use a separate pipeline for external PRs with no secret access |
| Docker Compose steps produce artifacts but agent can't find them | Files created inside containers are invisible to the host agent | Mount the working directory as a volume in `docker-compose.yml` so container outputs are visible for `artifact_paths:` |
| Dynamic pipeline generates 1000+ steps | UI becomes slow, pipeline processing degrades | Keep generated pipelines under ~500 steps; use orchestrator pipelines with trigger steps for larger monorepos |

## Additional Resources

### Reference Files
- **`references/step-types-reference.md`** — Detailed attribute tables for all step types
- **`references/advanced-patterns.md`** — Dynamic pipeline generators, matrix adjustments, monorepo patterns, multi-stage pipelines
- **`references/retry-and-error-codes.md`** — Comprehensive exit code table, retry strategies by failure type

### Examples
- **`examples/basic-pipeline.yml`** — Minimal working pipeline (test, wait, deploy)
- **`examples/optimized-pipeline.yml`** — Full-featured pipeline with caching, parallelism, annotations, retry, artifacts, and notifications

> For migrating pipelines from other CI systems, see the **buildkite-migration** skill.

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Defining pipeline steps](https://buildkite.com/docs/pipelines/configure/defining-steps.md)
- [Step types reference](https://buildkite.com/docs/pipelines/configure/step-types.md)
- [Pipeline upload](https://buildkite.com/docs/agent/v3/cli-pipeline.md)
- [Conditionals](https://buildkite.com/docs/pipelines/configure/conditionals.md)
- [Managing pipeline secrets](https://buildkite.com/docs/pipelines/security/secrets/managing.md)
- [Pipeline design best practices](https://buildkite.com/docs/pipelines/best-practices/pipeline-design-and-structure.md)
