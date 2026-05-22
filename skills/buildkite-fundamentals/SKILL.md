---
name: buildkite-fundamentals
description: >
  This skill should be used when the user asks "what is a Buildkite build",
  "what is a pipeline", "what is a job", "build vs step vs job",
  "what's the difference between a queue and a cluster", "agent vs queue",
  "hosted or self-hosted", "where do jobs run", "what's a hook",
  "what is an annotation", "what is meta-data", "what is OIDC in Buildkite",
  "what's a plugin", "MCP server or REST API", "how does Buildkite route work",
  "what does buildkite-agent do", "how should an AI agent talk to Buildkite",
  "which API should I use", "is this REST or GraphQL", or
  "what surface does Buildkite expose for agents".
  Also use when the user mentions buildkite-agent, mcp.buildkite.com,
  api.buildkite.com, graphql.buildkite.com, agent tokens, the .buildkite/ directory,
  build/job/step states, cluster queues, OIDC subjects, BUILDKITE_* env vars,
  pre-command/pre-exit/environment hooks, or asks any "what is X in Buildkite"
  orientation question before reaching for a deeper skill.
---

# Buildkite Fundamentals

Buildkite is a hybrid CI/CD platform: the control plane runs as SaaS while build compute runs on either Buildkite-hosted or self-hosted agents. This skill defines the core vocabulary every other Buildkite skill assumes — pipeline, build, step, job, agent, queue, cluster, hook, annotation, meta-data, OIDC subject — and the surface map (MCP, REST, GraphQL, `bk`, `buildkite-agent`) that tells an agent which channel to use for which intent. The four product pillars an agent will encounter are Pipelines (**buildkite-pipelines**), Test Engine (planned **buildkite-test-engine**), Package Registries (**buildkite-secure-delivery**), and Platform (**buildkite-agent-infrastructure**).

## Quick Start

A single annotated example showing the full mental hierarchy. The YAML below is a **pipeline definition**. Submitting it produces a **build**. Each `- label:` block is a **step**. Each step expands into one or more **jobs**, which are dispatched to **agents** via a **queue** inside a **cluster**.

```yaml
# .buildkite/pipeline.yml   <-- pipeline definition (template)
steps:
  - label: ":hammer: Tests"        # step definition
    command: "npm test"            # one job runs this command
    parallelism: 4                 # this step expands into 4 jobs
    agents:                        # routes to agents matching these tags
      queue: "ci-linux"            # queue inside the cluster

  - wait

  - label: ":rocket: Deploy"       # second step
    command: "scripts/deploy.sh"   # one job
    branches: "main"
```

Running this pipeline once creates a single **build**. The build contains two steps. The first step expands into 4 parallel jobs (because of `parallelism: 4`); the second produces 1 job. All 5 jobs are dispatched to whichever agents are polling the `ci-linux` queue. The cluster owns the queue, the queue owns the agents, the agents execute the jobs.

> For full pipeline authoring syntax, see the **buildkite-pipelines** skill.

## The Build Hierarchy

Four nouns, in containment order: **pipeline → build → step → job**.

- A **pipeline** is a configuration template attached to a repository, defining steps in YAML.
- A **build** is one execution of a pipeline against a specific commit, branch, and message.
- A **step** is a definition inside the pipeline. Step types: `command`, `wait`, `block`, `trigger`, `group`, `input`.
- A **job** is one execution of a step. One-to-many: a step can produce many jobs.

Two confusions worth calling out:

1. **A step is a definition; a job is its execution.** `parallelism: 10` produces one step but ten jobs. A matrix produces one step but N jobs. The count of `jobs` in a webhook or API response rarely equals the count of `steps`.
2. **Build state and job state are different enums.** Build state is `scheduled / running / passed / failed / canceled / blocked / not_run`. Job state is a longer list and pairs with a separate `outcome` field. See `references/build-hierarchy.md` for the diagram and full tables.

## Pipelines, Dynamic Pipelines, and Step Graphs

A static pipeline is YAML committed to `.buildkite/pipeline.yml`. A **dynamic pipeline** generates steps at runtime by piping YAML into `buildkite-agent pipeline upload`; generated steps are appended (or replaced with `--replace`). The implicit DAG formed when steps use `depends_on:` or `group:` is the **step graph**. Any `group:` step opts the whole build into DAG mode.

> For pipeline authoring, step types, dynamic generation, `if_changed`, matrix, plugins, retry, and concurrency, see the **buildkite-pipelines** skill.

## Agents, Queues, and Clusters

Strict containment: organization > cluster > queue > agent.

- An **agent** is a process running the `buildkite-agent` binary that polls Buildkite for work and executes jobs.
- A **queue** is a named pool of agents inside a cluster. Jobs specifying `agents: { queue: "ci-linux" }` dispatch to an agent registered in that queue.
- A **cluster** groups queues with the pipelines authorized to target them. Clusters are the unit of permissions, isolation, and quota.

The routing key is the `agents:` block in pipeline YAML; tag values map to queue tags.

> For cluster setup, queue creation, agent installation, and scaling self-hosted fleets, see the **buildkite-agent-infrastructure** skill.
> For Buildkite-hosted agent image management, cache volumes, and macOS specifics, see the **buildkite-hosted-agents-operations** skill.

## Hosted vs Self-Hosted Agents

The architecture is hybrid by design. The control plane (`buildkite.com`, `api.buildkite.com`, `graphql.buildkite.com`, `mcp.buildkite.com`) is always Buildkite-managed regardless of where agents run. Agents can be Buildkite-hosted (managed Linux, macOS, or Windows runners) or self-hosted (anywhere the customer can run a binary).

| Situation | Use Buildkite-hosted | Use self-hosted |
|---|---|---|
| Source code or secrets must not leave the VPC | — | yes |
| Need GPU, large instance shapes, or custom OS image | — | yes |
| Getting started quickly with no infra | yes | — |
| Running on macOS for iOS builds | yes (managed) | yes (Mac mini fleet) |

Architectural diagram: [Pipelines architecture](https://buildkite.com/docs/pipelines/architecture.md).

## How an Agent Should Talk to Buildkite

Five surfaces. Map intent to surface, then route to the sibling skill that owns it.

| Intent | Surface | Skill |
|---|---|---|
| Read a build, list jobs, fetch logs, post an annotation from outside a running build | MCP server (`mcp.buildkite.com`) — OAuth, self-documenting | **buildkite-api** |
| Complex query: filter pipelines, count builds, fetch build environment | GraphQL (`graphql.buildkite.com`) | **buildkite-api** |
| Create or update a resource: pipelines, builds, schedules, provider settings | REST (`api.buildkite.com`) | **buildkite-api** |
| Drive a build from a developer machine | `bk` CLI | **buildkite-cli** |
| Act *inside* a running job — annotate, upload artifacts, set meta-data, request an OIDC token | `buildkite-agent` subcommands | **buildkite-agent-runtime** |

Two rules:

1. **For AI agents driving CI from outside, prefer MCP over REST or GraphQL.** MCP tools document their own parameters, manage auth via OAuth, and have a separate rate-limit quota from org REST traffic. Reach for REST or GraphQL only when MCP does not expose the operation.
2. **`buildkite-agent` is not for outside-of-job use.** Its subcommands depend on `BUILDKITE_AGENT_ACCESS_TOKEN` in the job environment. From outside a job, use `bk` or the API.

See `references/surface-map.md` for the full matrix and auth models.

## Core Glossary

- **agent** — process running `buildkite-agent` that polls for and executes jobs.
- **annotation** — Markdown or HTML block attached to a build, surfaced in the UI. See **buildkite-agent-runtime**.
- **artifact** — file uploaded by a job, downloadable by later jobs or via the API. See **buildkite-agent-runtime**.
- **block step** — pauses the build until a human or API call unblocks it.
- **build** — one execution of a pipeline.
- **cluster** — container for queues and pipelines; the permissions and isolation unit.
- **cluster queue** — a queue scoped to a cluster (versus the legacy org-wide queue model).
- **dynamic pipeline** — pipeline whose steps are generated at runtime via `buildkite-agent pipeline upload`. See **buildkite-pipelines**.
- **ephemeral agent** — agent that exits after one job; common with hosted and autoscaled fleets.
- **hook** — script run by the agent at a defined lifecycle point. The three most common names are `environment`, `pre-command`, `pre-exit`. See `references/hooks-lifecycle.md`.
- **job** — one execution of a step.
- **job state** — enum describing where the job is in its lifecycle. See `references/build-hierarchy.md`.
- **meta-data** — build-wide key-value store readable by any later job. See **buildkite-agent-runtime**.
- **OIDC subject** — canonical string `organization:<slug>:pipeline:<slug>:ref:<git_ref>:commit:<sha>:step:<step_key>`. See `references/oidc-subject-format.md`.
- **pipeline** — template attached to a repo; defines steps.
- **plugin** — reusable hook bundle referenced from a step's `plugins:` block. See **buildkite-pipelines**.
- **queue** — pool of agents inside a cluster.
- **step** — a definition inside a pipeline.
- **step state** — current state of a step's jobs in aggregate.
- **trigger build** — a build created by a `trigger` step on a different pipeline.
- **wait step** — barrier that blocks until all preceding steps complete.

Owned by another skill — not redefined here: `bktec`, `cache plugin`, Test Engine, Package Registries, SLSA provenance, agent stack k8s.

## Common Mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Treating step and job as synonyms | Misreads `parallelism` and matrix output; job count mismatches step count | A step is a definition; a job is one execution. `parallelism: N` produces 1 step and N jobs |
| Calling the REST API to read build state from an AI agent | Token management complexity, rate-limit collisions with org REST traffic | Prefer the remote MCP server (`mcp.buildkite.com`) — OAuth, separate rate quota |
| Running `buildkite-agent` from outside a running job | Command exits with token error | `buildkite-agent` subcommands only run inside a job; from outside, use the `bk` CLI or the API |
| Confusing cluster with organization | Permissions and routing look wrong | An organization contains clusters; a cluster contains queues; a queue contains agents |
| Assuming hosted and self-hosted agents are configured the same way | Setup steps copied across don't apply | They share pipeline YAML semantics but diverge entirely on install, scaling, image, and networking — see **buildkite-agent-infrastructure** |
| Using "pipeline" to mean "build" | Triggers and conditions written against the wrong object | A pipeline is the template; a build is one run of it |
| Treating webhook `build.finished` as authoritative for state | Race conditions — jobs may still be settling when the event fires | Webhooks are eventually consistent; the API is the source of truth |
| Quoting an OIDC subject from training-data assumptions | Audience or claim mismatch rejects the token | The canonical subject format is `organization:<slug>:pipeline:<slug>:ref:<git_ref>:commit:<sha>:step:<step_key>` — see **buildkite-secure-delivery** |

## Additional Resources

### Reference Files
- **`references/build-hierarchy.md`** — Mermaid diagram and full state tables for builds and jobs.
- **`references/glossary.md`** — Extended alphabetical glossary, including minor terms (agent token, agent tags, build number, organization slug, pipeline slug, fork build, scheduled build, public pipeline).
- **`references/surface-map.md`** — MCP / REST / GraphQL / CLI / `buildkite-agent` decision matrix with example operations and auth models per surface.
- **`references/oidc-subject-format.md`** — Canonical OIDC subject string and the full claim list.
- **`references/hooks-lifecycle.md`** — Diagram of agent and job lifecycle hooks and where each fires.

### Sibling Skills

- **Authoring** — **buildkite-pipelines**, **buildkite-migration**, **buildkite-secure-delivery**
- **Operating** — **buildkite-cli**, **buildkite-agent-runtime**, **buildkite-build-investigation**, **buildkite-preflight**
- **Integrating** — **buildkite-api**, planned **buildkite-webhooks**
- **Infrastructure** — **buildkite-agent-infrastructure**, **buildkite-hosted-agents-operations**, planned **buildkite-test-engine**

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Pipelines glossary](https://buildkite.com/docs/pipelines/glossary.md)
- [Pipelines architecture](https://buildkite.com/docs/pipelines/architecture.md)
- [MCP server overview](https://buildkite.com/docs/apis/mcp-server.md)
- [API differences between REST and GraphQL](https://buildkite.com/docs/apis/api-differences.md)
