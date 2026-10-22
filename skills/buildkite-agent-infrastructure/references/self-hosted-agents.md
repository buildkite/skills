# Self-Hosted Agent Configuration and Lifecycle Hooks

## Self-Hosted Agent Configuration

Self-hosted agents run on your own infrastructure and connect to Buildkite using an agent token. Configure them via `buildkite-agent.cfg` or environment variables.

### Key configuration settings

```ini
# /etc/buildkite-agent/buildkite-agent.cfg

# Authentication
token="your-agent-token"

# Agent identity
name="backend-agent-%hostname-%n"
tags="queue=linux-large,team=backend,os=linux"
priority=1

# Job execution
build-path="/var/lib/buildkite-agent/builds"
hooks-path="/etc/buildkite-agent/hooks"
plugins-path="/etc/buildkite-agent/plugins"

# Concurrency
spawn=4

# Security
no-command-eval=true
no-local-hooks=false
no-plugins=false
allowed-repositories="git@github.com:my-org/*"

# Lifecycle
disconnect-after-job=true
cancel-grace-period=30

# Experiments
experiment="normalised-upload-paths,resolve-commit-after-checkout"
```

| Setting | Default | Description |
|---------|---------|-------------|
| `token` | — | Agent registration token (required) |
| `name` | `%hostname-%n` | Agent name template (`%hostname`, `%n` for spawn index) |
| `tags` | — | Comma-separated `key=value` pairs for routing |
| `priority` | `0` | Higher priority agents pick up jobs first |
| `spawn` | `1` | Number of parallel agents to run |
| `build-path` | varies | Directory where builds execute |
| `hooks-path` | varies | Path to agent-level hook scripts |
| `disconnect-after-job` | `false` | Disconnect after each job (for ephemeral/autoscaled agents) |
| `cancel-grace-period` | `10` | Seconds to wait for graceful shutdown |
| `no-command-eval` | `false` | Restrict to script-only execution (security hardening) |
| `allowed-repositories` | — | Glob patterns for repos this agent can build |

### Clustered vs. unclustered agents

**Clustered agents** belong to a cluster and target a single queue:

```ini
token="cluster-agent-token"
tags="queue=linux-large"
```

Clustered agents use a cluster-scoped token and can only have one `queue` tag.

**Unclustered agents** use an organization-level token and can have multiple tags:

```ini
token="org-agent-token"
tags="queue=default,os=linux,size=large"
```

Prefer clustered agents for new deployments. Clusters provide secret scoping, queue isolation, and better organizational control.

## Agent Lifecycle Hooks

Hooks are shell scripts that execute at specific points during the agent and job lifecycle. Use them for secret injection, environment setup, security validation, and cleanup.

### Hook execution order (per job)

```
environment        → Set environment variables for the job
pre-checkout       → Runs before git checkout
checkout           → The git checkout itself (override to customize)
post-checkout      → Runs after git checkout (e.g., submodule init)
pre-command        → Runs before the step command (secret injection, validation)
command            → The step command itself (override to customize execution)
post-command       → Runs after the step command (cleanup, notifications)
pre-exit           → Runs before the agent exits the job (final cleanup)
pre-artifact       → Runs before artifact upload
```

### Hook scopes

| Scope | Location | Applies to |
|-------|----------|------------|
| Agent-level | `hooks-path` in `buildkite-agent.cfg` | All jobs on this agent |
| Repository-level | `.buildkite/hooks/` in the repo | Jobs from this repo only |
| Plugin-level | Inside the plugin directory | Jobs using the plugin |

Agent-level hooks run first, then repository hooks, then plugin hooks.

### Environment hook — secret injection

The `environment` hook is the most common agent-level hook. Use it to inject secrets from external providers:

```bash
#!/bin/bash
# /etc/buildkite-agent/hooks/environment

set -euo pipefail

# Inject secrets from AWS Secrets Manager
if [[ "${BUILDKITE_PIPELINE_SLUG}" == "deploy-"* ]]; then
  export AWS_ACCESS_KEY_ID=$(aws secretsmanager get-secret-value \
    --secret-id "buildkite/deploy/aws-key" --query SecretString --output text)
fi
```

### Environment hook — security validation

Lock down which repositories, commands, and plugins agents execute:

```bash
#!/bin/bash
# /etc/buildkite-agent/hooks/environment

set -euo pipefail

# Restrict to allowed repositories
ALLOWED_REPOS="^git@github\.com:my-org/"
if [[ ! "${BUILDKITE_REPO}" =~ ${ALLOWED_REPOS} ]]; then
  echo "Unauthorized repository: ${BUILDKITE_REPO}"
  exit 1
fi
```
