---
name: depot-ci
description: >
  Configures and manages Depot CI, a drop-in replacement for GitHub Actions that runs workflows
  entirely within Depot. Use when migrating GitHub Actions workflows to Depot CI, running
  `depot ci migrate`, managing Depot CI secrets and variables, running workflows with
  `depot ci run`, debugging Depot CI runs with `depot ci run list`, `depot ci status`,
  `depot ci logs`, or `depot ci ssh`, checking
  workflow compatibility, or understanding Depot CI capabilities. Also use when the user
  mentions .depot/ directory, depot ci commands, or asks about running GitHub Actions workflows
  on Depot's infrastructure without GitHub-hosted runners.
---

# Depot CI

Depot CI is a programmable CI system for engineers and agents. Workflows in Depot CI run entirely on Depot compute with built-in job visibility, debuggability, and control. GitHub Actions is the first syntax Depot CI supports: migrate your existing GitHub Actions workflows, and get fast, reliable runs on optimized infrastructure.

## Architecture

Three subsystems: **compute** (provisions and executes work), **orchestrator** (schedules multi-step workflows, handles dependencies), **GitHub Actions parser** (translates Actions YAML into orchestrator workflows). The system is fully programmable.

## Getting Started

### 1. Install the Depot Code Access GitHub App

Depot dashboard → Settings → GitHub Code Access → Connect to GitHub

(If you've used Claude Code on Depot, this may already be installed.)

### 2. Migrate workflows

```bash
depot ci migrate
```

This interactive wizard:

1. Checks that the Depot Code Access app is installed and configured.
1. Discovers all workflows in `.github/workflows/` and analyzes each for Depot CI compatibility.
1. Copies selected workflows to `.depot/workflows/` with inline corrections and comments.
1. Copies local actions from `.github/actions/` to `.depot/actions/`.
1. Detects secrets and variables referenced in workflows and prints next steps for importing them.

Your `.github/` directory is untouched, so workflows run in both GitHub and Depot simultaneously.

**Warning:** Workflows that cause side effects (deploys, artifact updates) will execute twice.

#### Migrate subcommands

The migrate command can also be run as individual steps:

```bash
# Check installation and auth
depot ci migrate preflight

# Copy and transform workflows to .depot/workflows/
depot ci migrate workflows

# Import GitHub Actions secrets and variables into Depot CI
depot ci migrate secrets-and-vars
```

#### Migrate flags

|Flag                |Description                                |
|--------------------|-------------------------------------------|
|`-y, --yes`         |Non-interactive, migrate all workflows     |
|`--overwrite`       |Overwrite existing `.depot/` directory     |
|`--org <id>`        |Organization ID (required if multiple orgs)|
|`--token <token>`   |Depot API token                            |

### 3. Import secrets and variables

```bash
depot ci migrate secrets-and-vars
```

This creates and runs a one-shot GitHub Actions workflow on a temporary branch that reads your existing secrets and variables and imports them into Depot CI. The branch is safe to delete afterwards.

You can also add secrets and variables manually with `depot ci secrets add` and `depot ci vars add` (see below).

### 4. Manual setup (without migrate command)

Create `.depot/workflows/` and `.depot/actions/` directories manually. Copy workflow files from `.github/workflows/`. Configure secrets via the CLI.

## Managing Secrets

Secrets can be org-wide or scoped to a specific repository. Repository-scoped secrets override org-wide secrets with the same name.

```bash
# Add (prompts for value securely if --value omitted)
depot ci secrets add SECRET_NAME
depot ci secrets add SECRET_NAME --value "$NPM_TOKEN" --description "NPM auth token"

# Add repo-scoped secret
depot ci secrets add SECRET_NAME --repo owner/repo --value "$NPM_TOKEN"

# List (names and metadata only, no values)
depot ci secrets list
depot ci secrets list --output json
depot ci secrets list --repo owner/repo    # Also show repo-specific secrets

# Remove
depot ci secrets remove SECRET_NAME
depot ci secrets remove SECRET_NAME --force          # Skip confirmation
depot ci secrets remove SECRET_NAME --repo owner/repo  # Remove repo-scoped secret
```

## Credential Safety Guardrails

Treat credentials as sensitive input and never echo them back in outputs.

- For non-interactive flows, pass secret values via environment variables (for example: `--value "$NPM_TOKEN"`), not literals.
- Prefer interactive secret prompts (`depot ci secrets add SECRET_NAME`) over command-line secret values.
- Do not hardcode secrets or tokens in commands, scripts, workflow YAML, logs, or examples.
- Use CI secret stores for `DEPOT_TOKEN` and other credentials; pass at runtime only.
- Avoid force/non-interactive destructive flags unless explicitly requested by the user.
- Before running credential-affecting commands, confirm scope (org, repo, workflow) and intended target.

## Managing Variables

Non-secret config values accessible as `${{ vars.VARIABLE_NAME }}`. Unlike secrets, values can be read back. Variables can be org-wide or scoped to a specific repository, just like secrets.

```bash
# Add org-wide variable
depot ci vars add VAR_NAME --value "some-value"

# Add repo-scoped variable
depot ci vars add VAR_NAME --value "some-value" --repo owner/repo

# List
depot ci vars list
depot ci vars list --output json
depot ci vars list --repo owner/repo    # Also show repo-specific variables

# Remove
depot ci vars remove VAR_NAME
depot ci vars remove VAR_NAME --force
depot ci vars remove VAR_NAME --repo owner/repo
```

## Running Workflows

```bash
# Run a workflow
depot ci run --workflow .depot/workflows/ci.yml

# Run specific jobs only
depot ci run --workflow .depot/workflows/ci.yml --job build --job test

# Run a job and connect via SSH
depot ci run --workflow .depot/workflows/ci.yml --job build --ssh

# Debug with tmate session after step N (requires single --job)
depot ci run --workflow .depot/workflows/ci.yml --job build --ssh-after-step 3
```

The CLI auto-detects uncommitted changes vs. the default branch, uploads a patch to Depot Cache, and injects a step to apply it after checkout, so your local working state runs without needing a push.

Use `--ssh` or `--ssh-after-step` on `depot ci run` to start a debug session when launching a new run. Use `depot ci ssh` (below) to connect to an already-running job.

## Custom Images

Build a custom image once and reuse it across jobs to skip repeated setup steps.

### Build the image

Use `depot/snapshot-action` (Depot CI only, not compatible with GitHub Actions):
```yaml
jobs:
  build-image:
    runs-on: depot-ubuntu-latest
    steps:
      - run: sudo apt-get install -y your-tool
      - uses: depot/snapshot-action@v1
        with:
          image: <org-id>.registry.depot.dev/my-ci-image:latest
```

### Use the image

Reference it in any Depot CI job with the `runs-on` object syntax:
```yaml
jobs:
  test:
    runs-on:
      size: 2x8
      image: <org-id>.registry.depot.dev/my-ci-image:latest
    steps:
      - uses: actions/checkout@v4
```

Available sizes: `2x8`, `4x16`, `8x32`, `16x64`, `32x128` (CPUs x RAM in GB).

**Constraints:** Images get pushed to and must be pulled from the Depot registry (`registry.depot.dev`), external registries are not supported.

## SSH into Running Jobs

Connect to a running CI job via interactive terminal for debugging.

```bash
# Connect directly using a job ID
depot ci ssh <job-id>

# Connect to a specific job in a run
depot ci ssh <run-id> --job build

# Auto-select job when there's only one
depot ci ssh <run-id>

# Print SSH connection details for automation
depot ci ssh <run-id> --info --output json
```

The command waits up to 5 minutes for the job sandbox to be provisioned if it hasn't started yet.

### SSH flags

|Flag              |Description                                          |
|------------------|-----------------------------------------------------|
|`--job <key>`     |Job key to connect to (required for multi-job runs)  |
|`--info`          |Print SSH details instead of connecting interactively|
|`-o, --output`    |Output format for `--info` (`json`)                  |
|`--org <id>`      |Organization ID                                      |
|`--token <token>` |Depot API token                                      |

## Checking Status and Logs

```bash
# Check run status (shows workflows -> jobs -> attempts hierarchy)
depot ci status <run-id>

# Fetch logs (accepts run ID, job ID, or attempt ID)
depot ci logs <run-id>
depot ci logs <attempt-id>

# Specify a job when the run has multiple jobs
depot ci logs <run-id> --job test

# Disambiguate when multiple workflows share the same job key
depot ci logs <run-id> --job build --workflow ci.yml
```

When given a run or job ID, `depot ci logs` resolves to the latest attempt automatically.

### Logs flags

|Flag              |Description                                                    |
|------------------|---------------------------------------------------------------|
|`--job <key>`     |Job key to select (required when run has multiple jobs)        |
|`--workflow <path>`|Workflow path to filter jobs (for example, `ci.yml`)          |
|`--org <id>`      |Organization ID                                                |
|`--token <token>` |Depot API token                                                |

## Listing Runs and Triage Flow

`depot ci run list` is the primary entrypoint for debugging active/recent CI activity across workflows.

```bash
# List runs (defaults to queued + running)
depot ci run list

# Filter by status (repeatable)
depot ci run list --status failed
depot ci run list --status finished --status failed

# Limit number of results
depot ci run list -n 5

# Machine-readable output for tooling/agents
depot ci run list --output json
```

### `run list` flags

|Flag             |Description                                                                 |
|-----------------|----------------------------------------------------------------------------|
|`-n <int>`       |Number of runs to return (default `50`)                                     |
|`--status <name>`|Filter by status; repeatable: `queued`, `running`, `finished`, `failed`, `cancelled`|
|`-o, --output`   |Output format (`json`)                                                      |
|`--org <id>`     |Organization ID                                                             |
|`--token <token>`|Depot API token                                                             |

### Debugging failed runs

```bash
# Find failed runs
depot ci run list --status failed -n 10

# Pull logs directly (auto-selects job if only one)
depot ci logs <run-id>

# Specify job when there are multiple
depot ci logs <run-id> --job build

# Use status to inspect the full workflow/job/attempt hierarchy when needed
depot ci status <run-id>
```

Use `--output json` on `depot ci run list` for machine-readable output.

## Compatibility with GitHub Actions

### Supported

#### Workflow level
`name`, `run-name`, `on`, `env`, `concurrency`, `defaults`, `jobs`, `on.workflow_call` (with inputs, outputs, secrets)

#### Triggers
`push` (branches, tags, paths), `pull_request` (branches, paths), `pull_request_target`, `schedule`, `workflow_call`, `workflow_dispatch` (with inputs), `workflow_run`, `merge_group`

#### Job level
`name`, `needs`, `if`, `outputs`, `env`, `defaults`, `timeout-minutes`, `concurrency`, `strategy` (matrix, fail-fast, max-parallel), `continue-on-error`, `container`, `services`, `uses` (reusable workflows), `with`, `secrets`, `secrets.inherit`, `steps`

#### Step level
`id`, `name`, `if`, `uses`, `run`, `shell`, `with`, `env`, `working-directory`, `continue-on-error`, `timeout-minutes`

#### Permissions
`actions`, `checks`, `contents`, `id-token`, `metadata`, `pull_requests`, `statuses`, `workflows`

#### Expressions
`github`, `env`, `vars`, `secrets`, `needs`, `strategy`, `matrix`, `steps`, `job`, `runner`, `inputs` contexts. Functions: `always()`, `success()`, `failure()`, `cancelled()`, `contains()`, `startsWith()`, `endsWith()`, `format()`, `join()`, `toJSON()`, `fromJSON()`, `hashFiles()`

#### Action types
JavaScript (Node 12/16/20/24), Composite, Docker

### Not Supported

- **Cross-repo reusable workflows**: `uses` referencing workflows in other repositories is not supported. Local reusable workflows work.
- **Fork-triggered PRs**: `pull_request` and `pull_request_target` from forks not supported yet
- **Non-Ubuntu runner labels**: all non-Depot labels silently treated as `depot-ubuntu-latest` (no error, runs on Ubuntu)
- **Deployment environments**: the `environment` field is not supported
- **GitHub-specific event triggers**: `release`, `issues`, `issue_comment`, `deployment`, `create`, `delete`, and others

### Runner labels

Depot CI supports these runner labels:

|Label                    |CPUs |RAM    |
|-------------------------|-----|-------|
|`depot-ubuntu-latest`    |2    |8 GB   |
|`depot-ubuntu-24.04`     |2    |8 GB   |
|`depot-ubuntu-24.04-4`   |4    |16 GB  |
|`depot-ubuntu-24.04-8`   |8    |32 GB  |
|`depot-ubuntu-24.04-16`  |16   |64 GB  |
|`depot-ubuntu-24.04-32`  |32   |128 GB |

Any label Depot CI can't parse is silently treated as `depot-ubuntu-latest`.

## Directory Structure

```
your-repo/
├── .github/
│   ├── workflows/     # Original GHA workflows (keep running)
│   └── actions/       # Local composite actions
├── .depot/
│   ├── workflows/     # Depot CI copies of workflows
│   └── actions/       # Depot CI copies of local actions
```

## Common Mistakes

|Mistake                                      |Fix                                                       |
|---------------------------------------------|----------------------------------------------------------|
|Removing `.github/workflows/` after migration|Keep them during transition to verify Depot CI parity      |
|Using cross-repo reusable workflows          |Not supported yet, inline the workflow or copy it locally  |
|Setting secrets without `--repo` when needed |Use `--repo owner/repo` for repo-specific secret overrides |
|Forgetting `--org` flag with multiple orgs   |Migration will fail, always specify `--org <id>`           |
|Workflows with `runs-on: windows-latest`     |Treated as `depot-ubuntu-latest`, may fail                 |
