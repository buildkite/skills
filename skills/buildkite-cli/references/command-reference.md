# CLI Command Reference

Detailed flags, examples, and usage for less-common `bk` CLI commands and full filter tables. For core commands (builds, jobs, pipelines, secrets, artifacts), see `SKILL.md`. Run `bk <command> --help` for the authoritative, version-specific flag list.

## Installation

### Homebrew (macOS and Linux)

```bash
brew install buildkite/buildkite/bk
```

### Binary download

Download pre-built binaries from the [GitHub releases page](https://github.com/buildkite/cli/releases). Extract and place the `bk` binary on the system PATH.

### Update and version

```bash
bk update      # updates in place, or prints the brew/mise command if managed
bk version     # print the installed version
bk --version   # same, top-level flag
```

## Authentication and Configuration

### `bk auth`

| Subcommand | Description |
|------------|-------------|
| `login` | OAuth login (or `--token` for token login); stores credentials in the keychain |
| `status` | Show the current session (`-o json` for structured output) |
| `token` | Print the stored API token to stdout |
| `switch` (alias `use`) | Switch the active organization |
| `logout` | Clear stored credentials (`--all` removes every org) |

`bk auth login` flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--scopes` | all available | OAuth scopes; supports the `read_only` group, e.g. `--scopes "read_only write_builds"` |
| `--org` | — | Organization slug or UUID to request access for |
| `--token` | — | API token for non-OAuth login (requires `--org`) |
| `--device` | `false` | Device authorization flow for headless machines |
| `--credential-store` | `auto` | Token store: `auto`, `keyring`, or `shm` (in-memory `/dev/shm`) |

### `bk configure`

Token-based config, used when OAuth is unavailable.

```bash
bk configure --org my-org --token my-token          # set the token
bk configure --force --org my-org --token my-token   # overwrite an existing token
bk configure add --org second-org --token other      # add another organization
```

### `bk config`

Persistent CLI settings. User config is global; `--local` writes `.bk.yaml` in the current directory.

```bash
bk config list                       # effective config (add --local or --global)
bk config get output_format
bk config set output_format json
bk config unset output_format
```

Valid keys: `selected_org`, `output_format` (`json`/`yaml`/`text`), `no_pager`, `quiet`, `no_input`, `pager`, `telemetry`, `credential_store` (`auto`/`keyring`/`shm`).

### Organizations

```bash
bk use my-other-org     # top-level alias for bk auth switch
bk organization list    # alias bk org list; JSON by default
```

## Builds — full filter tables

### `bk build list`

| Flag | Short | Default | Description | Side |
|------|-------|---------|-------------|------|
| `--pipeline` | `-p` | — (org-wide when omitted) | Pipeline slug or `{org}/{slug}` | server |
| `--state` | — | — | Filter by state (comma-separated) | server |
| `--branch` | — | — | Filter by branch (comma-separated) | server |
| `--since` | — | — | Created since (e.g. `1h`, `30m`) | server |
| `--until` | — | — | Created before (e.g. `1h`, `30m`) | server |
| `--creator` | — | — | Filter by creator email or user ID | server |
| `--commit` | — | — | Filter by commit SHA | server |
| `--meta-data` | — | — | Filter by `key=value` (repeatable) | server |
| `--duration` | — | — | Filter by duration with `>`, `<`, `>=`, `<=` (e.g. `">20m"`) | client |
| `--message` | — | — | Filter by message content | client |
| `--limit` | — | `50` | Maximum builds to return | — |
| `--no-limit` | — | `false` | Fetch all builds (overrides `--limit`) | — |
| `--output` | `-o` | `text` | Output format: `text`, `json`, `yaml` (or `--json`/`--yaml`/`--text`) | — |

Valid states: `running`, `scheduled`, `passed`, `failed`, `blocked`, `canceled`, `canceling`, `skipped`, `not_run`.

### `bk build view` / `rebuild` / `download`

These default to the most recent build on the current branch. Shared flags: `-p/--pipeline`, `-b/--branch`, `-u/--user`, `--mine`, `-w/--web` (view and rebuild). `bk build view` adds `-s/--job-states` (comma-separated: `running`, `scheduled`, `passed`, `failed`, `canceled`, `skipped`, `not_run`, `broken`) and output flags.

### `bk build watch`

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | auto-detected | Pipeline slug or `{org}/{slug}` |
| `--branch` | `-b` | current branch | Branch to watch builds for |
| `--interval` | — | `1` | Polling interval in seconds |

## Jobs — full filter tables

### `bk job list`

| Flag | Default | Description | Side |
|------|---------|-------------|------|
| `--pipeline` (`-p`) | — | Filter by pipeline slug | server |
| `--since` | — | Builds created since (e.g. `1h`) | server |
| `--until` | — | Builds created before (e.g. `1h`) | server |
| `--queue` | — | Filter by queue name | client |
| `--state` | — | Filter by job state (comma-separated) | client |
| `--duration` | — | Filter by duration (`>10m`, `<5m`, …) | client |
| `--order-by` | — | Order by `start_time` or `duration` | — |
| `--limit` | `100` | Maximum jobs to return | — |
| `--no-limit` | `false` | Fetch all matching jobs (scans up to 200 builds otherwise) | — |

Other job commands: `bk job retry <uuid>`, `bk job cancel <uuid> [-w]`, `bk job unblock <uuid> [--data '<json>']`, `bk job reprioritize <uuid> <priority>`. The `-p`/`-b` flags on `bk job log` and `bk job reprioritize` are deprecated and ignored — job UUIDs no longer need build context.

## Clusters

```bash
bk cluster list                                  # add -o json for structured output
bk cluster view <cluster-uuid>
bk cluster create --name "Production" --description "..." --emoji :rocket: --color "#00D974"
bk cluster update <cluster-uuid> --name "Renamed"
bk cluster delete <cluster-uuid>
```

### Queues

```bash
bk queue list <cluster-uuid>                     # --limit / --per-page for paging
bk queue view <cluster-uuid> <queue-uuid>
bk queue create <cluster-uuid> --key deploy --description "Deploy queue" \
  --retry-agent-affinity prefer-different        # or prefer-warmest
bk queue update <cluster-uuid> <queue-uuid> ...
bk queue delete <cluster-uuid> <queue-uuid>
bk queue pause <cluster-uuid> <queue-uuid>       # stop dispatching jobs
bk queue resume <cluster-uuid> <queue-uuid>
```

### Maintainers

```bash
bk maintainer list <cluster-uuid>
bk maintainer create <cluster-uuid> ...
bk maintainer delete <cluster-uuid> <maintainer-id>
```

> For cluster/queue strategy, hosted agent shapes, agent tokens, and infrastructure provisioning, see the **buildkite-agent-infrastructure** skill.

## Local Agent

```bash
# Run an ephemeral agent locally (downloads the binary, creates a temp token,
# cleans up on Ctrl+C)
bk agent run                          # latest version on the Default cluster
bk agent run --version 3.112.0 --queue deploy
bk agent run --cluster-uuid <uuid>

# Install the agent binary + a starter config
bk agent install --dest ~/.local/bin
bk agent install --no-token           # skip token/config creation

# Manage registered agents in the org
bk agent list
bk agent view <agent>
bk agent pause <agent-id>
bk agent resume <agent-id>
bk agent stop <agent-id> [<agent-id> ...]
```

## Packages

```bash
# Push from a file
bk package push <registry-slug> --file-path my-package.tar.gz

# Push via stdin (note the trailing hyphen)
cat my-package.tar.gz | bk package push <registry-slug> --stdin-file-name my-package.tar.gz -

# Open in the browser after pushing
bk package push <registry-slug> --file-path my-package.tar.gz -w
```

Supports Docker images, npm, Debian, RPM, and generic file uploads. Push to Buildkite Package Registries, ECR, GAR, Artifactory, and ACR.

> For OIDC-based authentication to package registries (no static credentials), see the **buildkite-secure-delivery** skill.

## Raw API Access

```bash
# REST GET (organization inferred from config)
bk api /pipelines/example-pipeline/builds/420

# REST POST
bk api --method POST /pipelines --data '{
  "name": "New Pipeline",
  "repository": "git@github.com:org/repo.git",
  "configuration": "steps:\n  - command: env"
}'

# REST PUT
bk api --method PUT /clusters/CLUSTER_UUID --data '{ "name": "My Updated Cluster" }'

# Test Analytics endpoint
bk api --analytics /suites

# GraphQL (from a file)
bk api --file query.graphql
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--method` | `-X` | `GET` | HTTP method |
| `--data` | `-d` | — | Request body for REST requests |
| `--headers` | `-H` | — | Headers to include (repeatable) |
| `--file` | `-f` | — | File containing a GraphQL query |
| `--analytics` | — | `false` | Use the Test Analytics endpoint |
| `--verbose` | — | `false` | Verbose output (rate-limit retry info) |

> For comprehensive REST and GraphQL API documentation (endpoints, mutations, pagination, webhooks), see the **buildkite-api** skill.

## Browse

```bash
bk browse                        # open the current pipeline, filtered to the branch
bk browse 420                    # open a specific build
bk browse 420 -n                 # print the URL instead of opening a browser
bk browse -s                     # open the pipeline settings page
bk browse --all-branches         # builds list without a branch filter
```

## Users

```bash
bk user invite alice@example.com bob@example.com
```

Sends invitation emails. Users gain access based on the organization's default role and team assignments.

## Skills

`bk skill` installs Buildkite skills from `github.com/buildkite/skills` into a coding agent's skills directory.

```bash
bk skill add buildkite-api                 # auto-detects .claude or .cursor
bk skill add buildkite-api --agent claude
bk skill add buildkite-api --global        # install into ~/.claude or ~/.cursor
bk skill add buildkite-api --path ~/.amp/skills   # custom directory (Amp, Pi, …)
bk skill update [name]
bk skill delete <name>
```

## Pipeline Initialization

```bash
bk init     # scaffold a starter pipeline.yaml in the current directory
```

> For pipeline YAML syntax, step types, and configuration patterns, see the **buildkite-pipelines** skill.
