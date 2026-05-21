---
name: buildkite
displayName: Buildkite
description: Buildkite CI/CD — author pipelines, run builds, manage agents and artifacts, and call the Buildkite API via the Buildkite MCP server. Bundles workflows for pipelines, migration, preflight, the agent runtime, the bk CLI, and the REST/GraphQL API.
keywords:
  - buildkite
  - ci
  - cd
  - pipeline
  - build
  - agent
  - artifact
  - annotation
  - preflight
  - bk
  - graphql
  - webhook
author: Buildkite
---

# Buildkite

This power gives Kiro authoritative knowledge of Buildkite — pipelines, the agent runtime, the `bk` CLI, the REST/GraphQL API, migrations from other CI providers, and running preflight builds against local changes — together with the Buildkite MCP server for live access to your builds, pipelines, agents, artifacts, and logs.

## Setup

The Buildkite MCP server (configured in `mcp.json`) connects to `https://mcp.buildkite.com/mcp`. Authenticate when prompted on first use.

For pipeline-side work, install the `bk` CLI and authenticate:

```bash
brew install buildkite/buildkite/bk   # or see https://github.com/buildkite/cli
bk configure
```

## Workflows

Six steering files in `steering/` cover the full surface area. Kiro loads each one automatically when a request matches its description:

- **`steering/pipelines.md`** — Pipeline YAML, step types, plugins, caching, parallelism, dynamic pipelines, matrix builds, conditionals, annotations, artifacts.
- **`steering/migration.md`** — Converting from Jenkins, GitHub Actions, CircleCI, Bitbucket Pipelines, or GitLab CI with `bk pipeline convert`.
- **`steering/preflight.md`** — Running CI builds against the local working tree before pushing.
- **`steering/agent-runtime.md`** — `buildkite-agent` subcommands used inside job steps: annotate, artifact, meta-data, pipeline upload, oidc, lock, secret, redactor.
- **`steering/cli.md`** — `bk` command-line operations: builds, jobs, pipelines, secrets, artifacts, clusters, packages, API access.
- **`steering/api.md`** — REST, GraphQL, webhooks, authentication, pagination, common automation patterns.

Each steering file's bundled references and examples are available under `steering/<topic>/`.

## Source

This power is generated from the upstream Buildkite skills at <https://github.com/buildkite/skills>. The same workflows are available standalone as Kiro skills if you'd prefer to install them individually.
