---
name: buildkite-agent-infrastructure
description: >
  This skill should be used when the user asks to "create a cluster",
  "create a queue", "set up hosted agents", "configure agents",
  "right-size instance shapes", "scale queues", "manage cluster secrets",
  "create a pipeline template", "set up audit logging", "configure SSO",
  "set up SAML", "manage agent tokens", "optimize CI costs", or
  "standardize pipelines across teams".
  Also use when the user mentions buildkite-agent.cfg, agent tags, agent tokens,
  cluster queues, hosted agent instance shapes, pipeline templates, audit events,
  SSO/SAML providers, queue wait time, agent lifecycle hooks, or asks about
  Buildkite CI infrastructure provisioning, platform governance, or
  organization-level configuration.
---

# Buildkite Platform Engineering

Provision and govern Buildkite CI infrastructure at scale. This skill covers clusters, queues, hosted agent sizing, cluster secrets, agent tokens, self-hosted agent configuration, lifecycle hooks, pipeline templates, audit logging, SSO/SAML, and cost optimization — everything a platform team needs to run CI for the organization.

## Quick Start

Create a cluster with a hosted queue to get builds running immediately. Hosted queues use Buildkite-managed compute — agents are provisioned automatically. Self-hosted queues require provisioning your own agents; builds will hang in a "scheduled" state until agents connect.

**Start with hosted agents unless there is a specific reason to self-host** (e.g., GPU workloads, on-prem requirements, custom hardware).

All GraphQL mutations go to `https://graphql.buildkite.com/v1` with a Bearer token. The examples below show the GraphQL operations — execute them via curl:

```bash
curl -sS -X POST "https://graphql.buildkite.com/v1" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "<GRAPHQL_QUERY_OR_MUTATION>", "variables": { ... }}'
```

**Step 1: Get the organization ID** (required for all mutations):

```graphql
query {
  organization(slug: "my-org") {
    id
  }
}
```

**Step 2: Create a cluster:**

```graphql
mutation {
  clusterCreate(input: {
    organizationId: "org-id"
    name: "Production"
    description: "Production CI cluster"
    emoji: ":rocket:"
    color: "#14CC80"
  }) {
    cluster {
      id
      uuid
      name
      defaultQueue { id }
    }
  }
}
```

**Step 3: Create a hosted queue** with a specific instance shape:

```graphql
mutation {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "linux-large"
    description: "Linux 8 vCPU / 32 GB for heavy compilation"
    hostedAgents: {
      instanceShape: LINUX_AMD64_8X32
    }
  }) {
    clusterQueue {
      id
      uuid
      key
      hostedAgents { instanceShape { name size vcpu memory } }
    }
  }
}
```

**Step 4: Create a pipeline** in the cluster, then trigger a build:

```graphql
mutation {
  pipelineCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    name: "My Pipeline"
    repository: { url: "https://github.com/my-org/my-repo" }
    steps: { yaml: "steps:\n  - label: ':pipeline:'\n    command: 'buildkite-agent pipeline upload'" }
    defaultBranch: "main"
  }) {
    pipeline { id slug url }
  }
}
```

Target the queue from pipeline YAML with `agents: { queue: "linux-large" }`.

> For pipeline YAML syntax including `agents:` routing and `secrets:` access, see the **buildkite-pipelines** skill.
> For `bk cluster` CLI commands, see the **buildkite-cli** skill.

## Clusters

A cluster is the top-level container for queues, agent tokens, and secrets. Every organization starts with one default cluster; create additional clusters to isolate workloads (e.g., production vs. staging, team-specific).

### Create a cluster

**GraphQL:**

```graphql
mutation {
  clusterCreate(input: {
    organizationId: "org-id"
    name: "Backend"
    description: "Backend team CI cluster"
    emoji: ":gear:"
    color: "#0B79CE"
  }) {
    cluster { id uuid name }
  }
}
```

**REST API:**

```bash
curl -s -X POST "https://api.buildkite.com/v2/organizations/my-org/clusters" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backend",
    "description": "Backend team CI cluster",
    "emoji": ":gear:",
    "color": "#0B79CE"
  }'
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable cluster name |
| `description` | No | Purpose of the cluster |
| `emoji` | No | Emoji shortcode for UI display |
| `color` | No | Hex color for UI display |
| `default_queue_id` | No | UUID of the default queue for this cluster |

### Inspect clusters

Use the Buildkite MCP server's `list_clusters` and `get_cluster` tools to inspect clusters directly. To check cluster queues, use `list_cluster_queues` and `get_cluster_queue`.

> For full REST and GraphQL API reference, see the **buildkite-api** skill.

## Queues and Hosted Agents

Queues route builds to agents. Each queue runs either **hosted agents** (Buildkite-managed compute) or **self-hosted agents** (agents on your own infrastructure). Create specialized queues to isolate workloads by resource needs.

**Hosted queues** are the recommended starting point. Buildkite provisions and manages the compute — builds start running immediately after queue creation. **Self-hosted queues** require connecting your own agents; until agents connect, builds remain in "scheduled" state indefinitely.

### Create a hosted queue

```graphql
mutation {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "default"
    description: "General-purpose Linux queue"
    hostedAgents: {
      instanceShape: LINUX_AMD64_4X16
    }
  }) {
    clusterQueue {
      id
      key
      hostedAgents { instanceShape { name vcpu memory } }
    }
  }
}
```

### Create a self-hosted queue

Omit `hostedAgents` — self-hosted agents connect by targeting the queue key in their configuration:

```graphql
mutation {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "gpu-runners"
    description: "GPU-equipped self-hosted agents"
  }) {
    clusterQueue { id key }
  }
}
```

### Instance shapes

Hosted agent compute sizes available for queue creation:

**Linux AMD64:**

| Shape | vCPU | Memory |
|-------|------|--------|
| `LINUX_AMD64_2X4` | 2 | 4 GB |
| `LINUX_AMD64_4X16` | 4 | 16 GB |
| `LINUX_AMD64_8X32` | 8 | 32 GB |
| `LINUX_AMD64_16X64` | 16 | 64 GB |

**Linux ARM64:**

| Shape | vCPU | Memory |
|-------|------|--------|
| `LINUX_ARM64_2X4` | 2 | 4 GB |
| `LINUX_ARM64_4X16` | 4 | 16 GB |
| `LINUX_ARM64_8X32` | 8 | 32 GB |
| `LINUX_ARM64_16X64` | 16 | 64 GB |

**macOS M2:**

| Shape | vCPU | Memory |
|-------|------|--------|
| `MACOS_M2_4X7` | 4 | 7 GB |
| `MACOS_M2_6X14` | 6 | 14 GB |
| `MACOS_M2_12X28` | 12 | 28 GB |

**macOS M4:**

| Shape | vCPU | Memory |
|-------|------|--------|
| `MACOS_M4_6X28` | 6 | 28 GB |
| `MACOS_M4_12X56` | 12 | 56 GB |

macOS queues accept additional settings: `macosVersion` (`SONOMA`, `SEQUOIA`, `TAHOE`) and `xcodeVersion`. Linux queues accept `agentImageRef` for custom Docker images.

### Sizing guide

| Workload | Recommended shape | Why |
|----------|------------------|-----|
| Basic apps, linting, unit tests | `LINUX_AMD64_2X4` | Minimal resource needs, lowest cost |
| Monorepos, multi-service builds | `LINUX_AMD64_4X16` | Parallel compilation needs more memory |
| Heavy compilation (C++, Rust, large Java) | `LINUX_AMD64_8X32` | CPU-bound builds benefit from more cores |
| Docker image builds, ML training prep | `LINUX_AMD64_16X64` | Large images need disk I/O and memory |
| iOS / macOS builds | `MACOS_M4_6X28` | Native Apple Silicon for Xcode builds |
| iOS / macOS CI (large projects) | `MACOS_M4_12X56` | Full Xcode parallelism |

Start with the smallest shape that keeps builds under target time. Monitor queue wait time — if consistently above 2 minutes, either scale up or add more queue capacity.

### Pause and resume queue dispatch

Temporarily stop dispatching jobs to a queue (maintenance, cost control):

```graphql
mutation {
  clusterQueuePauseDispatch(input: {
    organizationId: "org-id"
    id: "queue-id"
    note: "Maintenance window 2026-03-26 22:00-23:00 UTC"
  }) {
    clusterQueue { id dispatchPaused }
  }
}

mutation {
  clusterQueueResumeDispatch(input: {
    organizationId: "org-id"
    id: "queue-id"
  }) {
    clusterQueue { id dispatchPaused }
  }
}
```

### Queue routing from pipelines

Pipelines target queues using the `agents` block:

```yaml
steps:
  - label: ":hammer: Build"
    command: "make build"
    agents:
      queue: "linux-large"
```

> For full `agents:` syntax and queue routing patterns, see the **buildkite-pipelines** skill.

## Cluster Secrets

Cluster secrets are encrypted, cluster-scoped values accessible from pipeline steps. They replace hardcoded credentials and environment-hook-based secret injection.

### Create a secret

**REST API:**

```bash
curl -s -X POST "https://api.buildkite.com/v2/organizations/my-org/clusters/$CLUSTER_ID/secrets" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "NPM_TOKEN",
    "value": "'"$NPM_TOKEN"'",
    "description": "npm registry authentication token"
  }'
```

### Secret key constraints

| Rule | Detail |
|------|--------|
| Must start with | A letter (A-Z, a-z) |
| Allowed characters | Letters, numbers, underscores only |
| Prohibited prefixes | `buildkite`, `bk` (reserved) |
| Max key length | 255 characters |
| Max value size | 8 KB |

### Access policies

Restrict which pipelines and branches can access a secret using policy claims:

```json
{
  "key": "DEPLOY_KEY",
  "value": "...",
  "description": "Production deploy key",
  "policy": {
    "claims": {
      "pipeline_slug": ["deploy-*"],
      "build_branch": ["main", "release/*"]
    }
  }
}
```

| Claim | Description |
|-------|-------------|
| `pipeline_slug` | Pipeline slug patterns (supports `*` wildcard) |
| `build_branch` | Branch patterns that can access this secret |
| `build_creator` | UUIDs of users allowed to trigger builds accessing this secret |
| `build_source` | Build sources (`ui`, `api`, `webhook`, `schedule`, `trigger_job`) |
| `build_creator_team` | Team UUIDs whose members can access this secret |
| `cluster_queue_key` | Queue keys where jobs can access this secret |

### Update a secret

Description and policy updates are separate from value updates:

```bash
# Update description and policy
curl -s -X PUT "https://api.buildkite.com/v2/organizations/my-org/clusters/$CLUSTER_ID/secrets/$SECRET_ID" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description", "policy": {"claims": {"build_branch": ["main"]}}}'

# Rotate the secret value (separate endpoint)
curl -s -X PUT "https://api.buildkite.com/v2/organizations/my-org/clusters/$CLUSTER_ID/secrets/$SECRET_ID/value" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": "'"$NEW_SECRET_VALUE"'"}'
```

### Access secrets in pipeline YAML

```yaml
steps:
  - label: ":npm: Publish"
    command: "npm publish"
    secrets:
      NPM_TOKEN: "npm-registry-token"
```

The secret is exposed as the environment variable `NPM_TOKEN` during the step. The value on the right (`npm-registry-token`) is the secret key name in the cluster.

> For `secrets:` YAML syntax, see the **buildkite-pipelines** skill. For programmatic secret retrieval inside steps with `buildkite-agent secret get`, see the **buildkite-agent-runtime** skill.

## Agent Tokens

Agent tokens authenticate agents connecting to a cluster. Each token is scoped to a single cluster.

### Create a token

**GraphQL (clustered):**

```graphql
mutation {
  clusterAgentTokenCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    description: "Backend CI agents - production"
    allowedIpAddresses: "10.0.0.0/8,172.16.0.0/12"
  }) {
    clusterAgentTokenEdge {
      node {
        id
        description
        token  # Only returned on creation — store securely
      }
    }
  }
}
```

**REST API:**

```bash
curl -s -X POST "https://api.buildkite.com/v2/organizations/my-org/clusters/$CLUSTER_ID/tokens" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Backend CI agents - production",
    "allowed_ip_addresses": "10.0.0.0/8"
  }'
```

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | Human-readable token description |
| `allowed_ip_addresses` | No | Comma-separated CIDR ranges restricting agent connections |
| `expires_at` | No | ISO 8601 expiry timestamp |

The token value is only returned at creation time. Store it in a secrets manager immediately.

### Token security practices

- Rotate tokens on a regular schedule (quarterly recommended)
- Use IP restrictions (`allowed_ip_addresses`) to limit where agents can connect from
- Set `expires_at` for temporary or contractor agent pools
- Create separate tokens per environment (staging vs. production)
- Revoke compromised tokens immediately — agents reconnect with the new token

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

### Hosted agent custom hooks

Hosted agents support custom hooks via a custom agent image. Add hooks in a Dockerfile:

```dockerfile
FROM buildkite/agent:latest

ENV BUILDKITE_ADDITIONAL_HOOKS_PATHS=/custom/hooks
COPY ./hooks/*.sh /custom/hooks/
RUN chmod +x /custom/hooks/*.sh
```

Set the custom image on the queue with `agentImageRef` in the `clusterQueueCreate` mutation's `hostedAgents` input.

## Pipeline Templates

Pipeline templates (Enterprise-only) standardize pipeline YAML across the organization. Templates define a base configuration that pipelines inherit, ensuring consistency for security, compliance, or organizational standards.

### Create a template

```graphql
mutation {
  pipelineTemplateCreate(input: {
    organizationId: "org-id"
    name: "Standard CI Template"
    description: "Organization-standard CI pipeline with security scanning and artifact signing"
    available: true
    configuration: """
steps:
  - label: ":pipeline: Upload"
    command: buildkite-agent pipeline upload

  - wait

  - label: ":shield: Security Scan"
    command: "scripts/security-scan.sh"
    agents:
      queue: "security-scanners"

  - wait

  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    branches: "main"
    concurrency: 1
    concurrency_group: "deploy/production"
"""
  }) {
    pipelineTemplate {
      id
      uuid
      name
      available
    }
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `organizationId` | Yes | Organization GraphQL ID |
| `name` | Yes | Template name |
| `description` | No | What this template provides |
| `configuration` | Yes | Pipeline YAML string |
| `available` | No | Whether teams can select this template (default: `false`) |

### Update a template

```graphql
mutation {
  pipelineTemplateUpdate(input: {
    id: "template-id"
    name: "Standard CI Template v2"
    configuration: "..."
    available: true
  }) {
    pipelineTemplate { id name }
  }
}
```

### Template strategy

- Create a small number of templates (3-5) covering common patterns: basic CI, CI + deploy, CI + security scan + deploy
- Set `available: true` only for templates ready for teams to adopt
- Templates use standard pipeline YAML — test the YAML as a regular pipeline before promoting to a template
- Assign templates to pipelines via the Buildkite UI or API

## Audit Logging

Audit logging (Enterprise-only) tracks organization-level events for compliance and security monitoring.

### Query audit events

```graphql
query {
  organization(slug: "my-org") {
    auditEvents(
      first: 50
      occurredAtFrom: "2026-03-01T00:00:00Z"
      occurredAtTo: "2026-03-26T23:59:59Z"
    ) {
      edges {
        node {
          type
          occurredAt
          actor { name type uuid }
          subject { name type uuid }
          data
        }
      }
    }
  }
}
```

| Filter | Description |
|--------|-------------|
| `occurredAtFrom` / `occurredAtTo` | ISO 8601 time range |
| `type` | Specific audit event type (e.g., `ORGANIZATION_UPDATED`) |
| `subjectType` | Filter by subject type (e.g., `PIPELINE`, `AGENT_TOKEN`) |
| `subjectUUID` | Filter by specific subject |
| `order` | `RECENTLY_OCCURRED` (default) or `OLDEST_OCCURRED` |

### High-severity events to monitor

| Event type | Why it matters |
|------------|---------------|
| `agent_token.created` / `.deleted` | Agent authentication changes |
| `member.invited` / `.removed` | Team membership changes |
| `sso_provider.created` / `.updated` | SSO configuration changes |
| `pipeline_schedule.created` | New automated triggers |
| `cluster_secret.created` / `.deleted` | Secret management changes |
| `organization.updated` | Org-level setting changes |

### SIEM integration via Amazon EventBridge

Stream audit events to a SIEM in real time using EventBridge:

- **Source:** `aws.partner/buildkite.com/buildkite/<partner-event-source-id>`
- **Detail type:** `"Audit Event Logged"`

Event payload structure:

```json
{
  "organization": {
    "uuid": "org-uuid",
    "graphql_id": "T3JnYW5pemF0aW9u...",
    "slug": "my-org"
  },
  "event": {
    "uuid": "event-uuid",
    "occurred_at": "2026-03-26T14:30:00Z",
    "type": "agent_token.created",
    "data": { },
    "subject_type": "AgentToken",
    "subject_uuid": "token-uuid",
    "subject_name": "Production agents",
    "context": {
      "request_id": "req-uuid",
      "request_ip": "203.0.113.42",
      "session_user_uuid": "user-uuid",
      "request_user_agent": "Mozilla/5.0..."
    }
  },
  "actor": {
    "name": "Jane Engineer",
    "type": "USER",
    "uuid": "user-uuid"
  }
}
```

Route high-severity events to PagerDuty, Splunk, or Datadog via EventBridge rules matching on `detail.event.type`.

## SSO/SAML

Configure SSO to centralize authentication for the organization. Buildkite supports SAML 2.0 providers (Okta, Azure AD, Google Workspace, OneLogin, etc.).

### Set up a SAML provider

**Step 1 — Create the provider:**

```graphql
mutation {
  ssoProviderCreate(input: {
    organizationId: "org-id"
    type: SAML
    emailDomain: "example.com"
    emailDomainVerificationAddress: "admin@example.com"
  }) {
    ssoProvider {
      id
      state
      serviceProvider {
        metadata { url }
        ssoURL     # ACS URL — configure in IdP
        issuer     # Entity ID — configure in IdP
      }
    }
  }
}
```

**Step 2 — Configure the IdP** with the returned `ssoURL` (ACS URL) and `issuer` (Entity ID).

**Step 3 — Update with IdP metadata:**

```graphql
# Option A: Metadata URL (preferred — auto-updates)
mutation {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      metadata: { url: "https://idp.example.com/saml/metadata" }
    }
  }) {
    ssoProvider { id state }
  }
}

# Option B: Manual configuration
mutation {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      ssoURL: "https://idp.example.com/saml/sso"
      issuer: "https://idp.example.com"
      certificate: "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
    }
  }) {
    ssoProvider { id state }
  }
}
```

**Step 4 — Verify the email domain** (Buildkite sends a verification email to the address specified).

**Step 5 — Enable the provider** once verification completes and IdP is configured.

### Query SSO providers

```graphql
query {
  organization(slug: "my-org") {
    ssoProviders(first: 10) {
      edges {
        node {
          id
          type
          state
          emailDomain
          enabledAt
          ... on SSOProviderSAML {
            identityProvider { ssoURL issuer certificate metadata { url xml } }
          }
          ... on SSOProviderGoogleGSuite {
            googleHostedDomain
          }
        }
      }
    }
  }
}
```

Provider states: `PENDING` (created, awaiting config), `DISABLED` (configured but off), `ENABLED` (active).

## Cost Optimization

CI costs are driven by three factors: instance shape size, job duration, and queue utilization. Optimize by right-sizing queues, reducing idle time, and matching workloads to appropriate shapes.

### Right-sizing queues

1. **Identify over-provisioned queues** — If average CPU utilization is below 30%, drop to a smaller instance shape
2. **Identify under-provisioned queues** — If p95 wait time exceeds 2 minutes, scale up or add capacity
3. **Separate workload types** — Light jobs (linting, formatting) on `2X4`; heavy compilation on `8X32` or `16X64`

Use the Buildkite MCP server's `get_cluster_queue` tool to check queue metrics and dispatch status.

### Queue utilization analysis

```graphql
query {
  organization(slug: "my-org") {
    pipelines(first: 50) {
      edges {
        node {
          name
          slug
          metrics {
            edges {
              node { label value }
            }
          }
        }
      }
    }
  }
}
```

Review pipeline metrics to identify:
- Pipelines with consistently long build times (candidates for larger shapes)
- Pipelines with very short builds on large shapes (candidates for downsizing)
- Low-frequency pipelines that could share a queue instead of having dedicated capacity

### Cost reduction patterns

| Pattern | Savings | How |
|---------|---------|-----|
| Right-size instance shapes | 20-40% | Match shape to actual resource needs |
| Use `disconnect-after-job` for self-hosted | 10-20% | Ephemeral agents don't idle between jobs |
| Pause queues during off-hours | 10-30% | `clusterQueuePauseDispatch` on nights/weekends |
| Skip unnecessary work with `if_changed` | 10-30% | Only run tests for changed code paths |
| Use `priority` to run critical jobs first | Indirect | Reduces developer wait time for important builds |

> For `if_changed` and pipeline optimization patterns, see the **buildkite-pipelines** skill.

## Queue Monitoring

Monitor queue health to maintain fast feedback loops. Target: queue wait time under 2 minutes.

### Diagnose queue wait time

Use the Buildkite MCP server to inspect queue state:

- **`list_cluster_queues`** — Overview of all queues in a cluster, including dispatch status
- **`get_cluster_queue`** — Detailed queue metrics (jobs waiting, agents available)
- **`list_builds`** — Check for build volume spikes causing congestion

### Scaling decision flow

```
Queue wait > 2 min?
├── Yes → Check agent count
│   ├── Agents maxed out → Scale up (add agents or increase shape)
│   ├── Agents idle → Check for job distribution issues (tags, queue routing)
│   └── No agents → Check token, connectivity, agent health
└── No → Queue is healthy
```

### Pause dispatch for maintenance

When performing agent maintenance or infrastructure changes, pause dispatch to drain the queue gracefully:

```graphql
mutation {
  clusterQueuePauseDispatch(input: {
    organizationId: "org-id"
    id: "queue-id"
    note: "Agent OS upgrade - ETA 30 min"
  }) {
    clusterQueue { id dispatchPaused }
  }
}
```

Jobs already running continue. New jobs queue until dispatch resumes.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Secret key starting with `buildkite` or `bk` | API rejects the secret with a validation error | Use a different prefix — these are reserved for Buildkite internal use |
| Secret key with special characters (dashes, dots) | API rejects — only letters, numbers, and underscores allowed | Use underscores: `MY_SECRET_KEY` not `my-secret-key` |
| Not storing agent token at creation time | Token value is never shown again | Store in secrets manager immediately on creation |
| Using organization-level tokens for clustered agents | Agent connects but cannot access cluster queues or secrets | Use cluster-scoped tokens created via `clusterAgentTokenCreate` |
| Over-provisioning instance shapes "just in case" | 2-4x higher compute costs with no performance benefit | Start small, monitor, scale up only if builds are slow |
| Deploying without `disconnect-after-job` on autoscaled agents | Agents idle between jobs, consuming resources | Set `disconnect-after-job=true` for ephemeral agent pools |
| Skipping IP restrictions on agent tokens | Any machine with the token can connect as an agent | Use `allowed_ip_addresses` to restrict to known CIDR ranges |
| Creating one large queue for all workloads | Light jobs wait behind heavy jobs; no cost optimization | Create specialized queues per workload type |
| Editing pipeline template YAML without testing | Broken template affects all pipelines using it | Test YAML as a regular pipeline first, then promote to template |
| Cluster creation returns HTTP 500 or GraphQL "unknown error" | Cannot create a new cluster; repeated retries also fail | List existing clusters first (`GET /v2/organizations/{org}/clusters`); rename the Default cluster via `PATCH /v2/organizations/{org}/clusters/{id}` with `{"name": "desired-name"}` as a reliable workaround |
| Hosted queue creation fails with "Upgrade to Platform Pro to access hosted agents" | Plan tier does not include hosted agents; mutation returns an error | Fall back immediately: create a self-hosted queue (omit `hostedAgents`), install `buildkite-agent` locally, and start it with `--token <cluster-token> --tags "queue=default" --spawn 3` |
| Jobs hang indefinitely in "scheduled" state with self-hosted agents connected | The cluster's `default_queue_id` points to a different queue key than the one in the agent's `queue` tag | Check which queue key the agent uses (`queue=default` → queue with key `default`); update the cluster: `PATCH /v2/organizations/{org}/clusters/{id}` with `{"default_queue_id": "<uuid-of-matching-queue>"}` |

## Additional Resources

### Reference Files
- **`references/graphql-mutations.md`** — Complete GraphQL mutation examples for clusters, queues, tokens, templates, SSO, and audit events

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Manage clusters](https://buildkite.com/docs/clusters/manage-clusters)
- [Manage cluster queues](https://buildkite.com/docs/clusters/manage-queues)
- [Manage cluster agent tokens](https://buildkite.com/docs/clusters/manage-cluster-agent-tokens)
- [Manage cluster secrets](https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets)
- [Pipeline templates](https://buildkite.com/docs/pipelines/configure/templates)
- [SSO/SAML configuration](https://buildkite.com/docs/integrations/sso)
- [Audit logging](https://buildkite.com/docs/apis/graphql/schemas/query/organization-audit-events)
- [Agent configuration](https://buildkite.com/docs/agent/v3/configuration)
- [Agent hooks](https://buildkite.com/docs/agent/v3/hooks)
