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

Provision and govern Buildkite CI infrastructure at scale: clusters, queues, hosted agent sizing, secrets, agent tokens, self-hosted configuration, lifecycle hooks, pipeline templates, audit logging, SSO/SAML, and cost optimization.

## Quick Start

Create a cluster with a hosted queue to get builds running immediately. **Start with hosted agents unless there is a specific reason to self-host** (GPU workloads, on-prem, custom hardware). Self-hosted queues require provisioning your own agents; builds hang "scheduled" until agents connect.

All GraphQL mutations go to `https://graphql.buildkite.com/v1` with a Bearer token:

```bash
curl -sS -X POST "https://graphql.buildkite.com/v1" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "<GRAPHQL_QUERY_OR_MUTATION>", "variables": { ... }}'
```

**Step 1:** Get the organization ID: `query { organization(slug: "my-org") { id } }`

**Step 2:** Create a cluster:

```graphql
mutation {
  clusterCreate(input: {
    organizationId: "org-id"
    name: "Production"
    description: "Production CI cluster"
    emoji: ":rocket:"
    color: "#14CC80"
  }) { cluster { id uuid name } }
}
```

**Step 3:** Create a hosted queue with a specific instance shape:

```graphql
mutation {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "linux-large"
    description: "Linux 8 vCPU / 32 GB for heavy compilation"
    hostedAgents: { instanceShape: LINUX_AMD64_8X32 }
  }) { clusterQueue { id key } }
}
```

**Step 4:** Create a pipeline in the cluster via GraphQL `pipelineCreate` or the REST API, then trigger a build.

> For pipeline creation via REST and GraphQL, see the **buildkite-api** skill.

> For pipeline YAML syntax including `agents:` routing and `secrets:` access, see the **buildkite-pipelines** skill.
> For `bk cluster` CLI commands, see the **buildkite-cli** skill.

## Clusters

A cluster is the top-level container for queues, agent tokens, and secrets. Every organization starts with one default cluster; create additional clusters to isolate workloads (e.g., production vs. staging, team-specific).

### Create a cluster

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

Fields: `name` (required), `description`, `emoji`, `color`, `default_queue_id` (optional).

> For full REST and GraphQL API reference, see the **buildkite-api** skill.

## Queues and Hosted Agents

Queues route builds to agents. **Hosted queues** (Buildkite-managed compute) are the recommended starting point — builds run immediately. **Self-hosted queues** require connecting your own agents; builds remain "scheduled" until agents connect.

Create queues with the `clusterQueueCreate` GraphQL mutation (shown in Quick Start above). To create a **self-hosted queue**, omit `hostedAgents`. Self-hosted agents connect by targeting the queue key in their configuration.

### Instance shapes and sizing guide

Full list: `references/instance-shapes.md`. Quick sizing:

| Workload | Shape |
|----------|-------|
| Linting, unit tests | `LINUX_AMD64_2X4` |
| Monorepos, multi-service | `LINUX_AMD64_4X16` |
| Heavy compilation (C++, Rust) | `LINUX_AMD64_8X32` |
| Docker builds, ML prep | `LINUX_AMD64_16X64` |
| iOS / macOS | `MACOS_M4_6X28` or `MACOS_M4_12X56` |

Start with the smallest shape that keeps builds under target time. Scale up if queue wait exceeds 2 minutes.

### Queue design patterns

- **Keep 1-2 static instances in the default queue** — avoids cold-start latency on pipeline uploads
- **Retire oldest agents first during scale-down** — preserves warm caches
- **Trial pattern** — test new shapes/architectures on a separate queue before migrating
- **Tag builds with metadata** for cost attribution by queue or team

Temporarily pause dispatch to a queue for maintenance or cost control using `clusterQueuePauseDispatch` / `clusterQueueResumeDispatch` GraphQL mutations. See `references/graphql-mutations.md` for examples.

## Cluster Secrets

Cluster secrets are encrypted, cluster-scoped values accessible from pipeline steps. They replace hardcoded credentials and environment-hook-based secret injection. Create, update, and rotate secrets via the REST API at `/v2/organizations/{org}/clusters/{cluster_id}/secrets`.

### Secret key constraints

| Rule | Detail |
|------|--------|
| Must start with | A letter (A-Z, a-z) |
| Allowed characters | Letters, numbers, underscores only |
| Prohibited prefixes | `buildkite`, `bk` (reserved) |
| Max key length | 255 characters |
| Max value size | 8 KB |

### Access policies

Restrict which pipelines and branches can access a secret by adding a `policy` object with `claims`. Available claim types: `pipeline_slug`, `build_branch`, `build_creator`, `build_source`, `build_creator_team`, `cluster_queue_key`. Claims support `*` wildcards. See [Buildkite Secrets docs](https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets.md) for policy examples.

Value rotation uses a separate endpoint (`PUT .../secrets/{id}/value`) from description/policy updates (`PUT .../secrets/{id}`).

> For `secrets:` YAML syntax, see the **buildkite-pipelines** skill. For `buildkite-agent secret get`, see the **buildkite-agent-runtime** skill.

## Agent Tokens

Agent tokens authenticate agents connecting to a cluster. Each token is scoped to a single cluster.

### Create a token

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

## Self-Hosted Agents and Lifecycle Hooks

Self-hosted agents run on your own infrastructure, configured via `buildkite-agent.cfg`. Prefer clustered agents for new deployments — they provide secret scoping, queue isolation, and better organizational control. For full configuration reference, `buildkite-agent.cfg` examples, and clustered vs. unclustered agent details, see `references/self-hosted-agents.md`.

Agent lifecycle hooks execute at specific points during job execution: `environment` → `pre-checkout` → `checkout` → `post-checkout` → `pre-command` → `command` → `post-command` → `pre-exit` → `pre-artifact`. Agent-level hooks run first, then repository hooks, then plugin hooks. For hook details and examples, see `references/self-hosted-agents.md`.

### Hosted agent caching behavior

**Cache volumes on hosted agents are non-deterministic** — jobs may or may not get a warm cache. Treat cache volumes as performance accelerators, not guarantees. Cache volumes are **pipeline-scoped** (not shared across pipelines). For deterministic caching, use Docker images with pre-built dependencies instead. Git mirrors can be enabled via cache volumes to accelerate checkout; mount `.git/lfs/objects` in cache volumes and pre-install `git-lfs` in the agent image.

### Hosted agent checkout performance

Buildkite's default checkout **prioritizes completeness over speed** — it may be noticeably slower than GitHub Actions for the same repo. Optimize with the Sparse Checkout plugin (monorepos), Git mirrors (frequent builds), or the Git Shallow Clone plugin (repos where full history is unnecessary).

### Hosted agent custom hooks

Hosted agents support custom hooks via a custom agent image. Add hooks in a Dockerfile:

```dockerfile
FROM buildkite/agent:latest

ENV BUILDKITE_ADDITIONAL_HOOKS_PATHS=/custom/hooks
COPY ./hooks/*.sh /custom/hooks/
RUN chmod +x /custom/hooks/*.sh
```

### Hosted agent pre-installed tools

Linux hosted agents include: `bash`, `curl`, `wget`, `git`, `docker`, `python3`, `jq`.

**`nvm` is NOT pre-installed.** Do not source `~/.nvm/nvm.sh` — it will fail silently or exit 127. Use `fnm` instead:

```bash
curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir "$HOME/.fnm" --skip-shell
export PATH="$HOME/.fnm:$PATH" && eval "$(fnm env --use-on-cd)"
fnm install 20 && fnm use 20
```

`fnm` downloads from `nodejs.org` directly and works for all versions including EOL.

**GitHub release asset downloads may be blocked.** `release-assets.githubusercontent.com` is unreachable from hosted agents. Pre-install tools distributed as GitHub release binaries (CodeQL, Scorecard, Trivy) in a custom agent image using `agentImageRef`.

**Always verify queue creation** after a GraphQL mutation by listing queues via `GET /v2/organizations/{org}/clusters/{cluster_id}/queues`. Silent GraphQL errors can leave the cluster without a hosted queue — if the list is empty, retry via the REST API.

## Plugin Security Controls

Restrict which plugins agents can run:

- **Agent-level allowlisting** — use `allowed-plugins` in `buildkite-agent.cfg` to restrict to approved plugins
- **`no-plugins=true`** — disable all plugins on sensitive agents
- **Cluster-based policies** — apply different plugin restrictions per cluster based on security requirements

Audit plugin repositories proactively — Buildkite does not automatically alert to plugin vulnerabilities.

## Pipeline Templates

Pipeline templates (Enterprise-only) standardize pipeline YAML across the organization. See `references/pipeline-templates.md`.

## Audit Logging

Audit logging (Enterprise-only) tracks organization-level events for compliance. Query via GraphQL or stream to a SIEM via Amazon EventBridge. See `references/audit-logging.md`.

## SSO/SAML

Buildkite supports SAML 2.0 (Okta, Azure AD, Google Workspace, OneLogin). See `references/sso-saml.md` for setup flow.

## Cost Optimization

### Cost reduction patterns

| Pattern | Savings | How |
|---------|---------|-----|
| Right-size instance shapes | 20-40% | Match shape to actual resource needs |
| Use `disconnect-after-job` for self-hosted | 10-20% | Ephemeral agents don't idle between jobs |
| Pause queues during off-hours | 10-30% | `clusterQueuePauseDispatch` on nights/weekends |
| Skip unnecessary work with `if_changed` | 10-30% | Only run tests for changed code paths |
| Use `priority` to run critical jobs first | Indirect | Reduces developer wait time for important builds |

> For `if_changed` and pipeline optimization patterns, see the **buildkite-pipelines** skill.

## Observability and Queue Monitoring

| Tool | Purpose | How it works |
|------|---------|-------------|
| `buildkite-agent-metrics` | Fleet-level queue and job metrics | Polls the Buildkite API; emits to CloudWatch, Datadog, StatsD |
| Agent health check service | Per-agent process health | Exposes Prometheus endpoint; scrape from each agent host |

**Start with queue profiling** — wait time and checkout time are the biggest, cheapest wins. Target: queue wait time under 2 minutes.

### Scaling decision flow

```
Queue wait > 2 min?
├── Yes → Check agent count
│   ├── Agents maxed out → Scale up (add agents or increase shape)
│   ├── Agents idle → Check for job distribution issues (tags, queue routing)
│   └── No agents → Check token, connectivity, agent health
└── No → Queue is healthy
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Secret key starting with `buildkite` or `bk` | Use a different prefix — these are reserved |
| Secret key with dashes or dots | Only letters, numbers, underscores allowed: `MY_SECRET_KEY` not `my-secret-key` |
| Not storing agent token at creation time | Token is only shown once — store in secrets manager immediately |
| Org-level tokens for clustered agents | Use cluster-scoped tokens (`clusterAgentTokenCreate`) |
| Over-provisioning instance shapes | Start small, monitor, scale up only when builds are slow |
| No `disconnect-after-job` on autoscaled agents | Set `disconnect-after-job=true` for ephemeral pools |
| One large queue for all workloads | Create specialized queues per workload type |
| Cluster creation returns HTTP 500 | List existing clusters first; rename the Default cluster via PATCH as a workaround |
| "Upgrade to Platform Pro" on hosted queue creation | Fall back: create self-hosted queue, install `buildkite-agent` locally with `--spawn 3` |
| Expecting cache volumes to always be warm | Design builds to work without cache — volumes are non-deterministic |
| One IAM role for all queues | Assign different IAM roles per queue; scope secrets by `cluster_queue_key` |
| Scaling down newest agents first | Retire oldest agents first to preserve warm caches |
| Jobs hang "scheduled" with agents connected | Check `default_queue_id` matches the agent's queue tag; update via PATCH |

## Additional Resources

- **`references/graphql-mutations.md`** — GraphQL mutations for clusters, queues, tokens, templates, SSO, audit
- **`references/instance-shapes.md`** — All hosted agent instance shapes
- **`references/self-hosted-agents.md`** — Agent config, clustered vs. unclustered, lifecycle hooks
- **`references/pipeline-templates.md`** — Template mutations and strategy (Enterprise)
- **`references/audit-logging.md`** — Audit queries, SIEM/EventBridge integration (Enterprise)
- **`references/sso-saml.md`** — SSO/SAML provider setup

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Manage clusters](https://buildkite.com/docs/clusters/manage-clusters.md)
- [Manage cluster queues](https://buildkite.com/docs/clusters/manage-queues.md)
- [Manage cluster secrets](https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets.md)
- [Agent configuration](https://buildkite.com/docs/agent/v3/configuration.md)
- [Agent hooks](https://buildkite.com/docs/agent/v3/hooks.md)
