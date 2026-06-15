# CLI Command Reference

Detailed flags, examples, and usage for less-common `bk` CLI commands. For core commands (builds, jobs, pipelines, secrets, artifacts), see `SKILL.md`.

## Installation

### Homebrew (macOS and Linux)

```bash
brew tap buildkite/buildkite
brew install buildkite/buildkite/bk
```

### Binary download

Download pre-built binaries from the [GitHub releases page](https://github.com/buildkite/cli/releases). Extract and place the `bk` binary on the system PATH.

### Verify installation

```bash
bk --version
```

## Auth Commands (v3.31+)

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

## Clusters

Manage organization clusters from the terminal.

```bash
# List clusters
bk cluster list

# View cluster details
bk cluster view <cluster-uuid>
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--output` | `-o` | `text` | Output format: `text`, `json` |

> For cluster creation, queue management, hosted agent configuration, and infrastructure provisioning, see the **buildkite-agent-infrastructure** skill.

## Packages

Manage packages in Buildkite Package Registries.

```bash
# Push a package from a file
bk package push <registry-slug> --file-path my-package.tar.gz

# Push a package via stdin
cat my-package.tar.gz | bk package push <registry-slug> --stdin-file-name my-package.tar.gz -
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `<registry-slug>` | — | — | Registry slug (positional arg, required) |
| `--file-path` | — | — | Path to the package file |
| `--stdin-file-name` | — | — | Filename when reading from stdin |
| `--web` | `-w` | `false` | Open in browser after push |

Supports Docker images, npm packages, Debian packages, RPM packages, and generic file uploads. Push to Buildkite Package Registries, ECR, GAR, Artifactory, and ACR.

> For OIDC-based authentication to package registries (no static credentials), see the **buildkite-secure-delivery** skill.

## Raw API Access

Make direct REST or GraphQL API calls from the terminal using `bk api`. Useful for operations not covered by dedicated subcommands.

### REST API

```bash
# GET request (organization is inferred from config)
bk api /pipelines/example-pipeline/builds/420

# POST request with JSON body
bk api --method POST /pipelines --data '{
  "name": "New Pipeline",
  "repository": "git@github.com:org/repo.git"
}'

# PUT request
bk api --method PUT /clusters/CLUSTER_UUID --data '{
  "name": "My Updated Cluster"
}'
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--method` | `-X` | — | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |
| `--data` | `-d` | — | Request body (JSON string) |
| `--headers` | `-H` | — | Headers to include (repeatable) |
| `--file` | `-f` | — | File containing a GraphQL query |
| `--analytics` | — | `false` | Use the Test Analytics endpoint |
| `--verbose` | — | `false` | Enable verbose output |

### GraphQL API

GraphQL requests are sent by providing a query via `--data` or `--file` without a REST endpoint:

```bash
# Inline query
bk api --data '{ "query": "{ viewer { user { name email } } }" }'

# Query from file
bk api --file query.graphql
```

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
