---
name: buildkite-cli
description: >
  This skill should be used when the user asks to "trigger a build",
  "check build status", "watch a build", "view build logs", "retry a build",
  "cancel a build", "list builds", "download artifacts", "upload artifacts",
  "manage secrets", "create a pipeline", "list pipelines", or
  "interact with Buildkite from the command line".
  Also use when the user mentions bk commands, bk build, bk job, bk pipeline,
  bk secret, bk artifact, bk cluster, bk package, bk auth, bk configure,
  bk use, bk init, bk api, or asks about Buildkite CLI installation,
  terminal-based Buildkite workflows, or command-line CI/CD operations.
---

# Buildkite CLI

The Buildkite CLI (`bk`) provides terminal access to builds, jobs, pipelines, secrets, artifacts, clusters, and packages. Use it to trigger builds, tail logs, manage secrets, and automate CI/CD workflows without leaving the command line.

## Quick Start

```bash
# Install
brew tap buildkite/buildkite && brew install buildkite/buildkite/bk

# Authenticate
bk configure

# Trigger a build on the current branch
bk build create --pipeline my-app

# Watch it run
bk build watch 42 --pipeline my-app

# View logs for a failed job
bk job log <job-id> --pipeline my-app --build 42
```

## Installation

### Homebrew (macOS and Linux)

```bash
brew tap buildkite/buildkite
brew install buildkite/buildkite/bk
```

### Binary download

Download pre-built binaries from the [GitHub releases page](https://github.com/buildkite/cli/releases). Extract and place the `bk` binary on the system PATH.

### Shell completion

Generate autocompletion scripts for the current shell:

```bash
# Bash
bk completion bash > /etc/bash_completion.d/bk

# Zsh
bk completion zsh > "${fpath[1]}/_bk"

# Fish
bk completion fish > ~/.config/fish/completions/bk.fish
```

### Verify installation

```bash
bk --version
```

## Authentication

### Initial setup

Run `bk configure` to set the organization slug and API access token. This creates `$HOME/.config/bk.yaml` on first run.

```bash
bk configure
```

Pass values non-interactively for CI, Docker, or headless environments:

```bash
bk configure --org my-org --token "$BUILDKITE_API_TOKEN" --no-input
```

The `--no-input` flag disables all interactive prompts (required in environments without a TTY). Other useful global flags: `--yes` (skip confirmations), `--quiet` (suppress progress output).

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--org` | | — | Organization slug |
| `--token` | | — | API access token (literal value or environment variable) |

### Token creation

1. Open Buildkite > user avatar > **Personal Settings** > **API Access Tokens**
2. Select **New API Access Token**
3. Grant scopes: `read_builds`, `write_builds`, `read_pipelines`, `read_artifacts` at minimum
4. Copy the token and pass it to `bk configure`

### Auth commands (v3.31+)

Starting in v3.31, `bk auth` provides structured authentication management with system keychain storage.

```bash
# Login (stores credentials in system keychain)
bk auth login

# Check current authentication status
bk auth status

# Switch between authenticated organizations
bk auth switch

# Clear keychain credentials
bk auth logout

# Clear all keychain configurations
bk auth logout --all
```

| Subcommand | Description |
|------------|-------------|
| `login` | Authenticate and store credentials in system keychain |
| `status` | Display current authentication state |
| `switch` | Switch between authenticated organizations |
| `logout` | Clear stored credentials (`--all` removes all) |

### Organization switching

Switch the active organization for subsequent commands:

```bash
# Switch to a specific org
bk use my-other-org

# Interactive selection (if multiple orgs configured)
bk use
```

## Builds

Manage pipeline builds — create, view, list, cancel, retry, and watch.

### Create a build

```bash
# Build the current branch and commit
bk build create --pipeline my-app

# Build a specific branch and commit
bk build create --pipeline my-app --branch feature/auth --commit abc1234

# Build with a custom message
bk build create --pipeline my-app --message "Deploy v2.1.0"

# Build with environment variables
bk build create --pipeline my-app --env "DEPLOY_ENV=staging"

# Build with metadata
bk build create --pipeline my-app --metadata "release-version=2.1.0"
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--branch` | `-b` | current branch | Git branch to build |
| `--commit` | `-c` | HEAD | Git commit SHA |
| `--message` | `-m` | — | Build message |
| `--env` | `-e` | — | Environment variables (repeatable: `-e K=V -e K2=V2`) |
| `--metadata` | | — | Build metadata key-value pairs (repeatable) |

> If the Buildkite MCP server is available, use the `create_build` tool instead for direct access without shell execution.

### View a build

```bash
# View build by number
bk build view 42 --pipeline my-app

# View the latest build
bk build view --pipeline my-app
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |

> If the Buildkite MCP server is available, use the `get_build` tool instead.

### List builds

```bash
# List recent builds for a pipeline
bk build list --pipeline my-app

# List only failed builds
bk build list --pipeline my-app --state failed

# List builds for a specific branch
bk build list --pipeline my-app --branch main

# List builds across the entire organization
bk build list

# Machine-readable output
bk build list --pipeline my-app --output json
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (omit for org-wide listing) |
| `--branch` | `-b` | — | Filter by branch |
| `--state` | `-s` | — | Filter by state: `running`, `scheduled`, `passed`, `failed`, `blocked`, `canceled`, `canceling`, `skipped`, `not_run`, `finished` |
| `--output` | `-o` | `text` | Output format: `text`, `json` |

> If the Buildkite MCP server is available, use the `list_builds` tool instead.

### Watch a build

Stream real-time build progress to the terminal. Blocks until the build completes or is canceled.

```bash
bk build watch 42 --pipeline my-app
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |

### Cancel a build

```bash
bk build cancel 42 --pipeline my-app
```

The build must be in a `scheduled`, `running`, or `failing` state. Attempting to cancel a completed build returns an error.

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |

### Retry a build

```bash
# Retry (rebuild) a specific build
bk build retry 42 --pipeline my-app
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |

### Download build resources

```bash
bk build download 42 --pipeline my-app
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |

### Build workflow: trigger and watch

Combine `create` and `watch` for a complete trigger-and-follow workflow:

```bash
# Trigger a build and immediately stream progress
bk build create --pipeline my-app --branch main && bk build watch --pipeline my-app
```

## Jobs

Manage individual jobs within a build — view logs, retry failures, cancel running jobs.

### View job logs

```bash
# View logs for a specific job
bk job log <job-id> --pipeline my-app --build 42

# Tail logs in real-time (follow mode)
bk job log <job-id> --pipeline my-app --build 42 --follow
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |
| `--follow` | `-f` | `false` | Stream logs in real-time |

> If the Buildkite MCP server is available, use the `read_logs` or `tail_logs` tools instead.

### Retry a job

Retry a failed, timed-out, or canceled job. Each job ID can only be retried once — subsequent retries must use the new job ID returned by the first retry.

```bash
bk job retry <job-id> --pipeline my-app --build 42
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |

The job must be in `failed`, `timed_out`, or `canceled` state (or have `permit_on_passed: true` in retry config).

### Cancel a job

```bash
bk job cancel <job-id> --pipeline my-app --build 42
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |

### Reprioritize a job

Change priority of a scheduled (not yet running) job:

```bash
bk job reprioritize <job-id> --pipeline my-app --build 42 --priority 10
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |
| `--priority` | | `0` | Priority value (higher runs first) |

### Debugging workflow: find failures and read logs

```bash
# Find failed builds
bk build list --pipeline my-app --state failed

# View the build to identify which jobs failed
bk build view 42 --pipeline my-app

# Read logs for the failed job
bk job log <job-id> --pipeline my-app --build 42
```

## Pipelines

Manage pipeline configuration — list, create, and update pipelines.

### List pipelines

```bash
# List all pipelines in the organization
bk pipeline list

# Machine-readable output
bk pipeline list --output json
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | `text` | Output format: `text`, `json` |

> If the Buildkite MCP server is available, use the `list_pipelines` tool instead.

### Create a pipeline

```bash
bk pipeline create --name "My App" --repository "git@github.com:org/my-app.git"
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--name` | `-n` | — | Pipeline name (required) |
| `--repository` | `-r` | — | Git repository URL (required) |
| `--cluster` | | — | Cluster UUID to assign the pipeline to |
| `--description` | `-d` | — | Pipeline description |

> If the Buildkite MCP server is available, use the `create_pipeline` tool instead.

> For pipeline YAML configuration after creation, see the **buildkite-pipelines** skill.

### Update a pipeline

```bash
bk pipeline update my-app --description "Production application pipeline"
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--description` | `-d` | — | Updated description |
| `--repository` | `-r` | — | Updated repository URL |

> If the Buildkite MCP server is available, use the `update_pipeline` tool instead.

## Secrets

Manage cluster-scoped secrets for pipelines. Secrets are encrypted and accessible to all agents within a cluster.

> For using secrets inside pipeline YAML (`secrets:` key) and inside job steps (`buildkite-agent secret get`), see the **buildkite-pipelines** skill and **buildkite-agent-runtime** skill respectively.

### Create a secret

```bash
# Create a secret (interactive prompt for value)
bk secret create MY_SECRET --cluster my-cluster

# Create with an inline value
bk secret create MY_SECRET --cluster my-cluster --value "$TOKEN"

# Create with a description
bk secret create DOCKER_PASSWORD --cluster my-cluster --value "$DOCKER_PWD" --description "Docker Hub credentials"
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--cluster` | | — | Cluster UUID or slug (required) |
| `--value` | | — | Secret value (omit for interactive prompt) |
| `--description` | `-d` | — | Human-readable description |

**Naming rules:**
- Keys must contain only letters, numbers, and underscores
- Keys cannot begin with `buildkite` or `bk` (case-insensitive)
- Exception: `BUILDKITE_API_TOKEN` is allowed

**Credential safety:** Prefer interactive prompts over inline `--value` flags. When automation requires inline values, pass via environment variable reference (`--value "$TOKEN"`) rather than literal strings. Never hardcode secrets in scripts or command history.

### List secrets

```bash
# List all secrets in a cluster
bk secret list --cluster my-cluster

# Machine-readable output
bk secret list --cluster my-cluster --output json
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--cluster` | | — | Cluster UUID or slug (required) |
| `--output` | `-o` | `text` | Output format: `text`, `json` |

Secret values are never displayed — only names, descriptions, and metadata.

### Update a secret

```bash
bk secret update MY_SECRET --cluster my-cluster --value "$NEW_TOKEN"
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--cluster` | | — | Cluster UUID or slug (required) |
| `--value` | | — | New secret value |
| `--description` | `-d` | — | Updated description |

### Delete a secret

```bash
bk secret delete MY_SECRET --cluster my-cluster
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--cluster` | | — | Cluster UUID or slug (required) |

### Secret access control

Secrets are scoped to a cluster. All agents and pipelines within that cluster can access the secret. Secrets created by cluster maintainers and organization administrators only. Control which pipelines can access specific secrets through agent access policies.

> For cluster creation and management, see the **buildkite-agent-infrastructure** skill.

## Artifacts

Upload and download build artifacts from the terminal.

### Download artifacts

```bash
# Download all artifacts from a build
bk artifact download --pipeline my-app --build 42

# Download artifacts matching a glob pattern
bk artifact download "dist/*.tar.gz" --pipeline my-app --build 42

# Download to a specific directory
bk artifact download "coverage/**/*" --pipeline my-app --build 42 --destination ./reports
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |
| `--destination` | `-d` | `.` | Download destination directory |
| `--job` | `-j` | — | Filter by job ID |

> If the Buildkite MCP server is available, use the `list_artifacts_for_build` and `get_artifact` tools instead.

### Upload artifacts

```bash
# Upload files matching a glob pattern
bk artifact upload "dist/**/*" --pipeline my-app --build 42 --job <job-id>
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline slug (required) |
| `--build` | `-b` | — | Build number (required) |
| `--job` | `-j` | — | Job ID (required) |

**Cluster constraint:** Pipelines associated with one cluster cannot access artifacts from another cluster unless explicitly allowed by cluster artifact access rules.

> For uploading artifacts from within a running job step, use `buildkite-agent artifact upload` — see the **buildkite-agent-runtime** skill. For declaring artifact paths in pipeline YAML (`artifact_paths:`), see the **buildkite-pipelines** skill.

## Clusters

Manage organization clusters from the terminal.

```bash
# List clusters
bk cluster list

# View cluster details
bk cluster view <cluster-slug>
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | `text` | Output format: `text`, `json` |

> For cluster creation, queue management, hosted agent configuration, and infrastructure provisioning, see the **buildkite-agent-infrastructure** skill.

## Packages

Manage packages in Buildkite Package Registries.

```bash
# List package registries
bk package list

# Push a package
bk package push <file> --registry my-registry
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--registry` | `-r` | — | Registry slug (required for push) |
| `--output` | `-o` | `text` | Output format: `text`, `json` |

Supports Docker images, npm packages, Debian packages, RPM packages, and generic file uploads. Push to Buildkite Package Registries, ECR, GAR, Artifactory, and ACR.

> For OIDC-based authentication to package registries (no static credentials), see the **buildkite-secure-delivery** skill.

## Raw API Access

Make direct REST or GraphQL API calls from the terminal using `bk api`. Useful for operations not covered by dedicated subcommands.

### REST API

```bash
# GET request
bk api /organizations/my-org/pipelines

# POST request with JSON body
bk api --method POST /organizations/my-org/pipelines --data '{
  "name": "New Pipeline",
  "repository": "git@github.com:org/repo.git"
}'

# PUT request
bk api --method PUT /organizations/my-org/pipelines/my-app --data '{
  "description": "Updated description"
}'
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--method` | `-X` | `GET` | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `--data` | `-d` | — | Request body (JSON string) |
| `--output` | `-o` | `text` | Output format: `text`, `json` |

### GraphQL API

```bash
bk api --graphql --data '{
  "query": "{ viewer { user { name email } } }"
}'
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--graphql` | | `false` | Send request to the GraphQL endpoint |
| `--data` | `-d` | — | GraphQL query as JSON string |

> For comprehensive REST and GraphQL API documentation (endpoints, mutations, pagination, webhooks), see the **buildkite-api** skill.

## Users

Invite users to the organization.

```bash
bk user invite user@example.com
```

Sends an invitation email to the specified address. The user gains access based on the organization's default role and team assignments.

## Pipeline Initialization

Scaffold a new `pipeline.yaml` in the current directory:

```bash
bk init
```

Creates a starter pipeline definition. Edit the generated file to define build steps.

> For pipeline YAML syntax, step types, and configuration patterns, see the **buildkite-pipelines** skill.

## MCP Server Alternatives

When the Buildkite MCP server is available, agents can use MCP tools for direct access without shell execution. The table below maps CLI commands to their MCP equivalents:

| CLI Command | MCP Tool | Notes |
|-------------|----------|-------|
| `bk build create` | `create_build` | MCP handles auth automatically |
| `bk build view` | `get_build` | MCP returns structured data |
| `bk build list` | `list_builds` | MCP supports the same filters |
| `bk job log` | `read_logs`, `tail_logs` | MCP supports streaming |
| `bk pipeline list` | `list_pipelines` | |
| `bk pipeline create` | `create_pipeline` | |
| `bk pipeline update` | `update_pipeline` | |
| `bk artifact download` | `list_artifacts_for_build`, `get_artifact` | |
| `bk cluster list` | `list_clusters` | |
| `bk auth status` | `current_user`, `access_token` | |
| `bk secret create/list/delete` | — | No MCP equivalent; CLI required |
| `bk package push` | — | No MCP equivalent; CLI required |
| `bk job retry` | — | No MCP equivalent; CLI required |
| `bk job cancel` | — | No MCP equivalent; CLI required |
| `bk build watch` | — | No MCP equivalent; CLI required |
| `bk api` | — | Use MCP tools for read operations; CLI for custom API calls |

**When to use CLI vs MCP:** Use MCP tools when available — they handle authentication, pagination, and response parsing automatically. Fall back to the CLI when MCP does not cover the operation (secrets, packages, job retry, build watch) or when the agent needs to execute commands in a Bash workflow.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Running `bk` commands before `bk configure` | Every command fails with authentication errors | Run `bk configure` or `bk auth login` first |
| Running `bk configure` in Docker/CI without `--no-input` | Hangs or fails trying to read from TTY or system keychain | Add `--no-input` flag: `bk configure --org my-org --token "$TOKEN" --no-input` |
| Omitting `--pipeline` on build commands | Command fails or targets the wrong pipeline | Always pass `--pipeline <slug>` explicitly |
| Retrying a job ID that was already retried | API returns 422 error — each job ID can only be retried once | Use the new job ID returned by the first retry |
| Creating secrets with keys starting with `buildkite` or `bk` | Creation fails — reserved prefix | Choose a different key name (exception: `BUILDKITE_API_TOKEN`) |
| Passing secret values as literal strings in `--value` | Values persist in shell history and process list | Use env var references (`--value "$TOKEN"`) or interactive prompts |
| Using `bk build cancel` on a completed build | API returns error — only `scheduled`, `running`, or `failing` builds can be canceled | Check build state with `bk build view` first |
| Expecting `bk artifact download` to work cross-cluster | Artifacts are cluster-scoped by default | Ensure both pipelines are in the same cluster or configure cross-cluster artifact access |
| Confusing `bk` CLI with `buildkite-agent` | `bk` runs on local machines to interact with the Buildkite API; `buildkite-agent` runs inside CI job steps | Use `bk` from terminal, `buildkite-agent` inside pipeline step commands |

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Buildkite CLI overview](https://buildkite.com/docs/platform/cli)
- [CLI command reference](https://buildkite.com/docs/platform/cli/reference)
- [CLI installation](https://buildkite.com/docs/platform/cli/installation)
- [CLI configuration and authentication](https://buildkite.com/docs/platform/cli/configuration)
- [Managing secrets](https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets)
