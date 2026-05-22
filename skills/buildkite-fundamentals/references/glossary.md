# Extended Glossary

Alphabetical reference covering every Buildkite term an agent is likely to encounter. SKILL.md carries the short version; this file includes minor terms that did not earn an inline definition.

## A

- **agent** — Process running the `buildkite-agent` binary that polls Buildkite for work and executes jobs.
- **agent tags** — Key-value labels on an agent (e.g. `queue=ci-linux`, `os=linux`, `arch=amd64`). Pipeline `agents:` blocks match against these tags.
- **agent token** — Credential the `buildkite-agent` process uses to register with Buildkite. Cluster-scoped. Should never appear in pipeline YAML or repository files.
- **annotation** — Markdown or HTML block attached to a build via `buildkite-agent annotate`, surfaced in the build UI. See **buildkite-agent-runtime**.
- **API token** — Personal or organization access token for `api.buildkite.com` and `graphql.buildkite.com`. Different from agent tokens.
- **artifact** — File uploaded by a job, retrievable by later jobs (`buildkite-agent artifact download`) or via the REST API. See **buildkite-agent-runtime**.

## B

- **block step** — Step type that pauses the build until a human or API call unblocks it. Often used for production deploy gates.
- **build** — One execution of a pipeline against a specific commit, branch, and message. Identified by build number (per pipeline) and UUID (globally).
- **build number** — Monotonically increasing integer scoped to a pipeline. Reset semantics: never resets.
- **buildkite-agent** — The binary that runs as a process on an agent host. Also exposes in-job subcommands (`annotate`, `artifact`, `meta-data`, `pipeline upload`, `oidc`, `step`, `lock`, `env`, `secret`, `redactor`, `tool`).

## C

- **cluster** — Top-level container for queues and pipelines; the unit of permissions, isolation, and quota.
- **cluster queue** — A queue scoped to a cluster, replacing the legacy organization-wide queue model.
- **cluster secret** — Secret stored in Buildkite, scoped to a cluster, retrievable in a job via `buildkite-agent secret get`.
- **command step** — Step type that runs a shell command. The most common step type.
- **concurrency** — Step-level limit on simultaneous executions, paired with `concurrency_group`. See **buildkite-pipelines**.

## D

- **DAG mode** — Pipeline mode triggered by any `group:` step in which step ordering is fully described by `depends_on:` and `wait` becomes inapplicable.
- **dynamic pipeline** — Pipeline whose steps are generated at runtime, typically by a script that pipes YAML into `buildkite-agent pipeline upload`. See **buildkite-pipelines**.

## E

- **ephemeral agent** — Agent process configured to exit after completing one job. Standard for hosted agents and autoscaled fleets.
- **environment hook** — Lifecycle hook that runs before any user command. Often used to set or rewrite env vars.

## F

- **fork build** — Build triggered by a pull request from a fork of the repository. Often subject to tighter secret-access policy.

## G

- **group step** — Step type that visually groups nested steps. Adds DAG mode to the build. Cannot have `concurrency:` of its own.

## H

- **hook** — Script run by the agent at a defined lifecycle point. Common names: `environment`, `pre-checkout`, `checkout`, `post-checkout`, `pre-command`, `command`, `post-command`, `pre-exit`. See `hooks-lifecycle.md`.
- **hosted agent** — Agent managed by Buildkite on Buildkite-operated infrastructure. Contrast with self-hosted.

## I

- **input step** — Step type that collects user-supplied form fields before continuing. Field values become meta-data.

## J

- **job** — One execution of a step. Job state and job outcome are distinct enums; see `build-hierarchy.md`.
- **job state** — Where a job is in its lifecycle. Distinct from outcome.

## M

- **matrix** — Step attribute that expands a single step into one job per combination of declared dimensions, with optional `adjustments` for skips and per-combination overrides.
- **MCP server** — Remote `mcp.buildkite.com` server exposing Model Context Protocol tools. OAuth, no static token. Preferred for AI agents.
- **meta-data** — Build-wide key-value store readable by any later job in the same build. Set and get via `buildkite-agent meta-data`. Block step field values are stored as meta-data.

## O

- **OIDC subject** — Canonical string identifying a job to an external OIDC verifier. Format: `organization:<slug>:pipeline:<slug>:ref:<git_ref>:commit:<sha>:step:<step_key>`. See `oidc-subject-format.md`.
- **organization** — Top-level Buildkite tenant; contains clusters, members, billing, audit. Identified by slug.
- **organization slug** — URL-safe identifier for the organization, visible in `buildkite.com/<org-slug>/...`.

## P

- **pipeline** — Configuration template attached to a repository; defines steps. Identified by slug within an organization.
- **pipeline slug** — URL-safe identifier for the pipeline, visible in `buildkite.com/<org>/<pipeline>/...`.
- **plugin** — Reusable hook bundle referenced from a step's `plugins:` block; pinned to a version. See **buildkite-pipelines**.
- **public pipeline** — Pipeline whose build pages are visible to anonymous users. Subject to additional secret-access restrictions.

## Q

- **queue** — Pool of agents inside a cluster. Targeted by pipeline YAML via `agents: { queue: "<name>" }`.

## R

- **redactor** — Log-redaction subsystem in the agent. Values registered via `buildkite-agent redactor add` or auto-registered by `secret get` appear as `[REDACTED]` in subsequent log output.
- **REST API** — `api.buildkite.com`. Token-based, resource-oriented. The right surface for creating or updating resources.

## S

- **scheduled build** — Build triggered automatically by a pipeline schedule (cron expression configured in Buildkite).
- **self-hosted agent** — Agent running on customer-operated infrastructure. Contrast with hosted.
- **soft fail** — Step attribute marking specific non-zero exit codes as non-blocking. The job's `outcome` becomes `soft_failed`; the build is not failed by that job.
- **step** — Definition inside a pipeline. Step types: `command`, `wait`, `block`, `trigger`, `group`, `input`.
- **step state** — Aggregate state of a step's jobs.

## T

- **trigger build** — Build created by a `trigger:` step on a different pipeline, typically used to chain deploy pipelines after CI.
- **trigger step** — Step type that starts a build on another pipeline.

## W

- **wait step** — Synchronization barrier that blocks subsequent steps until all preceding steps complete. Has no associated job.
- **webhook** — HTTP POST sent by Buildkite to a configured URL when build, job, or agent events fire. Eventually consistent — treat the API as the source of truth.

## Owned by other skills

These appear in Buildkite contexts but are defined and taught elsewhere:

- **bktec** — Test Engine CLI. Planned **buildkite-test-engine**.
- **cache plugin** — `cache#v1.x.y` plugin. **buildkite-pipelines**.
- **Test Engine** — Test analytics, flaky detection, splitting. Planned **buildkite-test-engine**.
- **Package Registries** — Buildkite-hosted package storage with OIDC auth. **buildkite-secure-delivery**.
- **SLSA provenance** — Supply-chain attestation produced by signing-enabled pipelines. **buildkite-secure-delivery**.
- **agent-stack-k8s** — Kubernetes operator that schedules Buildkite jobs as pods. **buildkite-agent-infrastructure**.
