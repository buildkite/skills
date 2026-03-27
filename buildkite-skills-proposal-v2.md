# Buildkite Skills Proposal v2

## Skills overview

7 skills. 4 journey-based, 3 cross-cutting. Organized by what users are trying to accomplish, not Buildkite's product surface.

| Skill | Type | Persona | Scope |
|-------|------|---------|-------|
| **`buildkite-pipelines`** | Journey | Every developer | Pipeline YAML: caching, parallelism, retry, `if_changed`, dynamic pipelines, matrix, plugins, notifications, artifact paths, concurrency |
| **`buildkite-test-engine`** | Journey | Devs with slow/flaky tests | bktec CLI, test splitting, flaky detection, quarantine, collectors, suite setup, `BUILDKITE_TEST_ENGINE_*` env vars |
| **`buildkite-secure-delivery`** | Journey (Phase 2) | Devs shipping artifacts | OIDC auth, Package Registry, SLSA provenance, pipeline signing (JWKS), end-to-end secure publish flow |
| **`buildkite-agent-infrastructure`** | Journey | Platform teams | Clusters, queues, hosted agents, instance shapes, cluster secrets, agent config, templates, audit logging, SSO, cost optimization |
| **`buildkite-agent-runtime`** | Cross-cutting | Every developer (in-job) | `buildkite-agent` subcommands used inside job steps: annotate, artifact, meta-data, pipeline upload, oidc, step, lock, env, secret, redactor |
| **`buildkite-cli`** | Cross-cutting | Everyone (terminal) | `bk` CLI: builds, jobs, pipelines, secrets, artifacts, auth |
| **`buildkite-api`** | Cross-cutting | Automation engineers | REST API, GraphQL API, webhooks, authentication, pagination |

### Skill boundaries

Each skill owns specific topics. Others cross-reference with one sentence + pointer.

| Topic | Owner | Do NOT duplicate in |
|-------|-------|--------------------|
| `pipeline.yml` syntax, step types, caching, parallelism, retry, `if_changed`, dynamic pipelines, matrix, plugins, `notify:`, `artifact_paths:`, concurrency, `agents:` queue routing, `secrets:` | **buildkite-pipelines** | Any other skill |
| Test Engine suites, `bktec` CLI, test splitting, flaky detection, quarantine, test collectors, `BUILDKITE_TEST_ENGINE_*` env vars, reliability scores | **buildkite-test-engine** | Any other skill |
| End-to-end secure publish flows, Package Registry setup, SLSA provenance patterns, pipeline signing (JWKS) config, verification rollout strategy | **buildkite-secure-delivery** | Any other skill |
| Clusters, queues, hosted agent instance shapes, cluster secrets setup, `buildkite-agent.cfg`, agent tokens, agent lifecycle hooks, pipeline templates, audit logging, SSO/SAML, cost tracking, org settings | **buildkite-agent-infrastructure** | Any other skill |
| `buildkite-agent annotate`, `artifact upload/download/search/shasum`, `meta-data set/get/exists/keys`, `pipeline upload`, `oidc request-token`, `step get/update/cancel`, `lock acquire/release/get/do`, `env dump/get/set/unset`, `secret get`, `redactor add`, `tool sign/verify` — command syntax, flags, examples | **buildkite-agent-runtime** | Any other skill |
| `bk build`, `bk job`, `bk pipeline`, `bk secret`, `bk artifact`, `bk auth` — command syntax, flags, examples | **buildkite-cli** | Any other skill |
| REST API endpoints, GraphQL schema/mutations, webhook setup, API authentication, pagination | **buildkite-api** | Any other skill |

**Ambiguity rule — pipelines vs agent-runtime:** The pipeline YAML *concept* (when to annotate, why to use dynamic pipelines, artifact_paths syntax) belongs to **buildkite-pipelines**. The *command syntax* for executing it inside a step (`buildkite-agent annotate --style error`, `buildkite-agent pipeline upload`) belongs to **buildkite-agent-runtime**. Pipelines teaches the *what and why*. Agent-runtime teaches the *how to invoke*.

### Execution paths — skills vs MCP vs CLI vs API

Skills teach *knowledge*. The agent *acts* through different execution paths depending on context:

| Agent needs to... | Knowledge source | Executes via |
|-------------------|-----------------|--------------|
| Write or edit `pipeline.yml` | Journey skill | File edit |
| Write `buildkite-agent` commands inside step scripts | `buildkite-agent-runtime` | File edit (inline in step `command:`) |
| Inspect a build, read logs, check queue depth | Journey skill (for *why*) | **Buildkite MCP server** tools (direct access) |
| Run a `bk` command | `buildkite-cli` | Bash |
| Run `bktec` for test splitting | `buildkite-test-engine` | Bash |
| Write a script/integration calling the API | `buildkite-api` | Code generation (curl, SDK, etc.) |

---

## What changed from v1

v1 organized skills by **product surface** (pipeline YAML, agent binary, CLI tool, platform APIs). That mirrors Buildkite's internal org chart, not how users think.

v2 organizes by **user journey**. When someone asks an AI agent for help, they're in the middle of a job — not browsing a product catalog. The framework reveals 4 distinct journeys that users travel through, and 3 cross-cutting needs that show up throughout.

---

## Recommended skills at a glance

| Skill | Type | Jobs | Persona | What it teaches |
|-------|------|------|---------|-----------------|
| `buildkite-pipelines` | Journey | J1, J2, J3 | Every developer | Pipeline YAML: caching, parallelism, retry, if_changed, dynamic pipelines, matrix, plugins |
| `buildkite-test-engine` | Journey | J4, J5 | Developers with slow/flaky tests | Test Engine: bktec CLI, test splitting, flaky detection, quarantine, collectors |
| `buildkite-secure-delivery` | Journey (Phase 2) | J6, J7 | Developers shipping artifacts | OIDC auth, Package Registry, SLSA provenance, pipeline signing (JWKS) |
| `buildkite-agent-infrastructure` | Journey | J8, J9 | Platform teams | Clusters, queues, hosted agents, secrets, agent config, templates, audit, SSO, cost |
| `buildkite-agent-runtime` | Cross-cutting | All | Every developer (in-job) | `buildkite-agent` subcommands inside steps: annotate, artifact, meta-data, pipeline upload, oidc, step, lock, env, secret, redactor |
| `buildkite-cli` | Cross-cutting | All | Everyone (terminal) | `bk` CLI: builds, jobs, pipelines, secrets, artifacts, auth |
| `buildkite-api` | Cross-cutting | All | Automation engineers | REST API, GraphQL API, webhooks, authentication |

### Boundary summary

| What the agent needs to do | Skill teaches knowledge | Agent executes via |
|----------------------------|------------------------|--------------------|
| Write or edit `pipeline.yml` | `buildkite-pipelines` | File edit |
| Run `bktec` for test splitting | `buildkite-test-engine` | Bash |
| Run `bk build create` or other CLI commands | `buildkite-cli` | Bash |
| Call REST/GraphQL API (curl, SDK, scripts) | `buildkite-api` | Bash / code generation |
| Inspect a running build, read logs, list pipelines | Any skill can reference | **Buildkite MCP server** tools |

---

## How skills interact with the MCP server, CLI, and API

### Skills ↔ Buildkite MCP server

The Buildkite MCP server gives agents **direct read/write access** to Buildkite without constructing API calls. Skills should reference MCP tools where relevant — "To inspect a running build, use the Buildkite MCP server's `get_build` tool" — but should **not** re-document MCP tool parameters. That's the MCP server's job (it exposes its own tool schemas).

**MCP server tool categories:**

| Category | Tools | Skills that reference them |
|----------|-------|---------------------------|
| Builds | `list_builds`, `get_build`, `create_build`, `unblock_job` | pipelines, test-engine, cli |
| Logs | `search_logs`, `tail_logs`, `read_logs` | pipelines, test-engine |
| Pipelines | `list_pipelines`, `get_pipeline`, `create_pipeline`, `update_pipeline` | pipelines, agent-infrastructure |
| Test Engine | `list_test_runs`, `get_test_run`, `get_failed_executions`, `get_test` | test-engine |
| Clusters | `list_clusters`, `get_cluster`, `list_cluster_queues`, `get_cluster_queue` | agent-infrastructure |
| Artifacts & Annotations | `list_artifacts_for_build`, `list_artifacts_for_job`, `get_artifact`, `list_annotations` | pipelines, secure-delivery |
| User | `current_user`, `access_token` | all |

**The rule:** Skills teach *what to do and why*. The MCP server provides *the tool to do it*. A skill says "check queue depth to diagnose wait time" and points to `get_cluster_queue`. It does not document `get_cluster_queue`'s parameters.

### Skills ↔ `buildkite-agent` runtime commands

The `buildkite-agent-runtime` skill teaches agents the subcommands available *inside* a running job step — `annotate`, `artifact`, `meta-data`, `pipeline upload`, `oidc`, `step`, `lock`, `env`, `secret`, `redactor`, `tool`. These are commands that go inside your step's `command:` block.

Journey skills say *when and why* to use these commands ("add an annotation on test failure"). The agent-runtime skill documents *how* to invoke them (flags, arguments, patterns). A journey skill references agent-runtime: "to create an annotation, see the **buildkite-agent-runtime** skill for `buildkite-agent annotate` syntax."

### Skills ↔ `bk` CLI

The `buildkite-cli` skill teaches agents how to use the `bk` CLI — command syntax, flags, flag tables, examples. This is **core skill content, not duplication**. The skill teaches the knowledge; the agent executes via Bash.

Any journey skill can say "to trigger a rebuild, see the **buildkite-cli** skill" — but the actual command syntax, flags, and examples live in `buildkite-cli` only.

### Skills ↔ REST/GraphQL API

The `buildkite-api` skill teaches agents the REST and GraphQL API — endpoints, authentication, request/response shapes, pagination, webhooks. This is **knowledge the agent needs to construct correct API calls**. The skill doesn't make the calls — the agent does (via curl, fetch, SDK, etc.).

Journey skills reference the API skill when they need programmatic access: "to create queues programmatically, see the **buildkite-api** skill for the `clusterQueueCreate` GraphQL mutation."

### When to use which

| Agent needs to... | Use | Why |
|-------------------|-----|-----|
| Read build status, logs, annotations right now | MCP server (`get_build`, `read_logs`) | Direct access, no API call construction needed |
| Write pipeline YAML | Skill knowledge → file edit | Journey skills teach syntax, agent writes files |
| Write `buildkite-agent` commands inside step scripts | `buildkite-agent-runtime` → file edit | Agent-runtime teaches command syntax, agent writes it into step `command:` blocks |
| Run a `bk` CLI command | `buildkite-cli` → Bash | CLI skill teaches syntax, agent runs via shell |
| Write a script/integration that calls the API | `buildkite-api` → code generation | API skill teaches endpoints, agent writes code |
| Understand *why* to do something (caching strategy, retry patterns, splitting approach) | Journey skill | Skills teach the reasoning and patterns |

---

## Jobs-to-be-done

| # | Job | Who | When |
|---|-----|-----|------|
| J1 | "Make my build finish in under 10 minutes" | Every team | Day 1 |
| J2 | "Show me why it failed without scrolling logs" | Every developer | Every failure |
| J3 | "Don't run tests unrelated to my change" | Every developer | Every PR |
| J4 | "Split my test suite across machines" | Teams with >5min suites | Week 3-4 |
| J5 | "Tell me if this failure is real or flaky" | Every developer | Every red build |
| J6 | "Publish artifacts with no static credentials" | Deploy pipelines | Every release |
| J7 | "Prove our supply chain is secure" | Platform/security teams | Compliance reviews |
| J8 | "Standardize CI across 50 teams without blocking them" | Platform teams | At scale |
| J9 | "Set up the infrastructure my pipelines run on" | Platform teams / first-time setup | Day 1, then as needs change |

---

## 4 journey skills + 3 cross-cutting skills

### Journey 1: `buildkite-pipelines` — "Write and optimize my pipeline"

**Jobs served:** J1, J2, J3

**The user journey:** Someone has code. They need CI. They write `pipeline.yml`, watch it run, and immediately want it faster, more visible, and smarter about what it runs. This is one continuous journey — not three separate problems — because the fix for all three is editing the same YAML file.

**Why one skill, not three:**
- "Add caching" (J1), "add an annotation" (J2), and "add if_changed" (J3) all produce edits to `pipeline.yml`
- The user doesn't switch tools or mental models between these tasks
- The framework's first 3 phases (START, SURFACE, SKIP) all produce pipeline YAML changes
- Splitting them would force the agent to decide "is this a speed question or a visibility question?" — a distinction the user doesn't make

**What triggers this skill:**
- "write a pipeline", "add caching", "make this build faster"
- "show test failures in the build page", "add annotations"
- "only run tests when code changes", "dynamic pipeline", "if_changed"
- "add retry", "parallel steps", "matrix build", "plugins"
- Any mention of `pipeline.yml`, `.buildkite/`, step types

**Content outline:**

| Area | Job | Framework evidence |
|------|-----|--------------------|
| Step types (command, wait, block, trigger, group, input) | All | Foundation — every pipeline is made of steps |
| Caching — plugin (`cache#v1.8.1`) vs volumes (hosted-only `cache:`) | J1 | #1 complaint. Framework shows this decision confuses people. Manifest-based invalidation, S3 backend options. |
| Parallel steps + `depends_on` | J1 | "5+2+3=10 serial vs 5 parallel" — biggest quick win after caching |
| Annotations (`buildkite-agent annotate`) | J2 | Entire SURFACE phase. Markdown tables, failure summaries, triage checklists, links to Test Engine. The example pipeline's annotation patterns are the gold standard. |
| Retry (`retry.automatic` by exit_status) | J2 | Specific codes: 143 (spot termination), 125 (Docker), network patterns (ECONNRESET, ETIMEDOUT). Framework lists them all. |
| `if_changed` (include/exclude patterns) | J3 | "Changed README, ran 2000 tests" — 10-30% less unnecessary work |
| Dynamic pipeline generation (`pipeline upload`) | J3 | The Python generator pattern: analyze git diff, emit YAML. This is Buildkite's core differentiator vs GitHub Actions. |
| Matrix builds | J1 | Same step, multiple configs, all parallel |
| Plugins (cache, docker, test-collector, provenance) | All | 3-line YAML additions — the highest-leverage changes |
| Notifications (in-pipeline `notify:`) | J2 | Slack/email on failure |
| Artifacts (upload/download in YAML) | J2 | Test results, coverage reports |
| Concurrency + priority | J1 | Queue management from pipeline side |

---

### Journey 2: `buildkite-test-engine` — "Make my tests fast and trustworthy"

**Jobs served:** J4, J5

**The user journey:** Someone has a test suite that takes too long on one machine, or keeps failing for reasons that aren't real bugs. They need to split tests across machines AND identify which failures are flakes. These are the same journey because:
- Both require Test Engine (Buildkite's separate testing product)
- Both use `bktec` (its own CLI binary)
- Both depend on accumulated timing/reliability data (~2 weeks)
- The user experiencing J4 (slow tests) almost always also experiences J5 (flaky tests)

**Why separate from pipelines:**
- Test Engine is a separate Buildkite product with its own pricing
- `bktec` is its own CLI — not `bk`, not `buildkite-agent`
- The onboarding is sequential and timing-dependent (need data before splitting works)
- Two framework phases (SKIP + SCALE) are dedicated to it
- Token confusion (analytics token vs personal API token) is the #1 support issue
- "How do I split my tests" is a completely different intent than "how do I write a retry block"

**What triggers this skill:**
- "split tests", "test splitting", "bktec", "test engine"
- "flaky test", "quarantine", "test reliability"
- "tests take too long", "parallelize test suite"
- Any mention of `BUILDKITE_TEST_ENGINE_*` env vars, test suites, test collectors

**Content outline:**

| Area | Job | Framework evidence |
|------|-----|--------------------|
| Suite creation + the two token types | J4, J5 | Analytics token (data collection) vs personal API access token (bktec splitting). #1 confusion point — framework example pipeline shows the mapping (`BAF_TEST_SUITE_API_TOKEN` → `BUILDKITE_ANALYTICS_TOKEN` vs `BAF_TEST_ENGINE_API_TOKEN` → `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN`). |
| Test collectors (RSpec, Jest, pytest, JUnit, Go) | J5 | Each framework needs specific reporter setup. Framework covers RSpec and Jest in detail. |
| `bktec` CLI (install, configure, run) | J4 | 6 env vars: `API_ACCESS_TOKEN`, `SUITE_SLUG`, `TEST_RUNNER`, `RESULT_PATH`, `RETRY_COUNT`. Debian package install on hosted agents. Fallback pattern if bktec unavailable. |
| `parallelism: N` + bktec timing-based splitting | J4 | "1000 tests / 10 machines = ~100 each, balanced by runtime." Without bktec, splits by file count — one job gets all slow tests. |
| Flaky detection | J5 | "Wasted an hour debugging a failure that passes on re-run." Needs ~1 week of data. |
| Quarantine workflows | J5 | Isolate flakes so red = real. Target: <3% flaky rate. |
| `BUILDKITE_TEST_ENGINE_RETRY_COUNT` | J5 | Retry within test run to detect flakes. Framework recommends `"2"`. |
| Reliability scores + timing trends | J4, J5 | "Is our suite getting slower?" Suite-level analytics API. |

---

### Journey 3: `buildkite-secure-delivery` — "Ship artifacts safely and prove it" (Phase 2)

**Jobs served:** J6, J7

**The user journey:** Someone needs to publish a Docker image, npm package, or other artifact — with zero static credentials — AND prove the build chain is trustworthy. These are the same journey because:
- The same pipeline step that publishes (J6) also attests (J7)
- OIDC auth and SLSA provenance are part of the same "secure publish" flow
- Pipeline signing protects the pipeline that does the publishing
- The framework's SHARPEN phase covers both in one implementation sequence
- The user is usually the same person (platform engineer or security champion)

**Why separate from a generic "platform" skill:**
- v1's `buildkite-platform` was a grab-bag (APIs, webhooks, OIDC, SSO, Test Engine, packages, audit, templates). Too wide.
- "Publish my Docker image with OIDC" and "set up SSO" have nothing in common beyond both using APIs.
- The secure delivery flow is end-to-end: build → authenticate (OIDC) → push (Package Registry) → attest (SLSA) → sign (JWKS). One skill can teach the whole flow.

**What triggers this skill:**
- "publish to package registry", "docker push", "OIDC", "oidc token"
- "SLSA", "provenance", "supply chain", "attestation"
- "sign pipelines", "JWKS", "pipeline verification"
- "cosign", "artifact signing"
- Any mention of `packages.buildkite.com`, `buildkite-agent oidc`

**Content outline:**

| Area | Job | Framework evidence |
|------|-----|--------------------|
| OIDC token requests | J6 | `buildkite-agent oidc request-token --audience URL --lifetime 300` piped to `docker login --password-stdin`. Audience must match registry URL exactly. |
| Package Registry (Docker, npm, generic) | J6 | Regional co-location for faster pulls. OIDC-only auth — no static credentials ever. |
| SLSA provenance (`generate-provenance-attestation` plugin) | J7 | Build Level 1 attestation: what was built, when, by whom, from which source. Cryptographically signed. |
| Pipeline signing (JWKS) | J7 | Agent-side config: signing-jwks-file, verification-jwks-file, verification-failure-behavior. Gradual rollout with `warn` before `block`. |
| End-to-end secure publish flow | J6+J7 | The example pipeline's Docker step: build → OIDC auth → push → SLSA attest. One complete pattern to copy. |

---

### Journey 4: `buildkite-agent-infrastructure` — "Set up and govern the CI platform"

**Jobs served:** J8, J9

**The user journey:** A platform engineer doing two related jobs: (1) provisioning the infrastructure pipelines run on — clusters, queues, hosted agents, secrets — and (2) governing that infrastructure at scale — templates, audit, cost, compliance. These are the same person, often in the same session. "Create a queue for the backend team" and "create a template for the backend team" happen together.

**Why one skill for both infra + governance:**
- Same persona: the platform engineer responsible for CI infrastructure
- Same tools: GraphQL API for queue creation AND template creation, cluster settings for secrets AND agent config
- Same timing: initial setup (J9) evolves into ongoing governance (J8) — it's one continuous journey
- Framework confirms this: START phase sets up infrastructure, SHARPEN phase governs it. Same person, different weeks.

**Why separate from secure-delivery:**
- Secure delivery is about *a pipeline publishing safely*. Platform engineering is about *the organization running many pipelines*.
- Different persona overlap: the secure delivery user can be any developer shipping artifacts. The platform engineering user is specifically the team running the CI platform.

**What triggers this skill:**
- "create a cluster", "create a queue", "set up hosted agents", "configure agents"
- "instance shape", "right-size", "scale queue", "queue wait time"
- "cluster secrets", "add a secret to the cluster"
- "pipeline template", "standardize pipelines", "create template"
- "audit log", "compliance", "SOC2", "audit trail"
- "SSO", "SAML", "onboarding", "team access"
- "CI costs", "cost per build", "cost optimization"
- "how much are we spending on CI"
- Any mention of `buildkite-agent.cfg`, agent tags, agent tokens

**Content outline:**

| Area | Job | Framework evidence |
|------|-----|--------------------|
| **Infrastructure provisioning** | | |
| Clusters (create, configure) | J9 | The container for queues, secrets, and agent config. First thing a platform team creates. |
| Queues + hosted agent instance shapes | J9 | GraphQL `clusterQueueCreate` / `clusterQueueUpdate`. Sizing guide: 2CPU/4GB for basic apps, 4CPU/8GB for monorepos, 4CPU/16GB for heavy compilation. Specialized queues for workload isolation (test vs build vs deploy). |
| Cluster secrets | J9 | Encrypted, cluster-scoped. `secrets:` key in pipeline YAML. Gotcha: names can't start with `buildkite` or `bk`. Framework's terraform provisions these automatically. |
| Agent tokens + self-hosted agent config | J9 | `buildkite-agent.cfg`, tags, queue targeting. For teams that need self-hosted alongside hosted. |
| Agent lifecycle hooks (environment, pre-command) | J9 | Bootstrap scripts, secret injection at runtime, custom environment setup. |
| Queue monitoring + auto-scaling | J9 | Framework's monitor script: check p95 wait time, scale up if >2min. Right-size underutilized queues to save cost. |
| **Governance** | | |
| Pipeline templates (GraphQL `pipelineTemplateCreate`) | J8 | Enterprise-only. Templates use standard pipeline YAML. Assignment via UI or API. |
| Audit logging + SIEM integration | J8 | Fetch events, classify severity (HIGH: agent_token.created, member.invited), stream to SIEM. |
| SSO/SAML | J8 | "Skip creating accounts for everyone. Someone joins GitHub org → they access builds. Someone leaves → revoked." |
| Cost tracking + optimization | J8 | Queue utilization analysis, agent-minutes tracking, right-sizing. Framework's ROI dashboard. |
| Organization API (REST + GraphQL) | J8 | Team management, permissions, organization settings. |

---

### Cross-cutting 1: `buildkite-agent-runtime` — "The in-job toolkit"

**Jobs served:** All — used inside step scripts across every journey

**What this is:** The `buildkite-agent` binary exposes subcommands that run *inside* a job step. This is the runtime toolkit for interacting with Buildkite from within your build scripts — creating annotations, uploading artifacts, sharing state between jobs, generating dynamic pipelines, requesting OIDC tokens, acquiring distributed locks, and more.

**Why separate from pipelines:** The pipelines skill teaches *what to put in pipeline.yml* (declarative). This skill teaches *what commands to run inside your step scripts* (imperative). `artifact_paths: "dist/**"` is pipeline YAML (→ buildkite-pipelines). `buildkite-agent artifact upload "dist/**"` is a runtime command (→ buildkite-agent-runtime). Same outcome, different skill.

**Why separate from agent-infrastructure:** Platform-engineering is about *setting up* agents — clusters, queues, `buildkite-agent.cfg`, tokens. This skill is about *using* the agent binary from within a running job. Different persona, different moment.

**What triggers this skill:**
- "buildkite-agent annotate", "buildkite-agent artifact", "buildkite-agent meta-data"
- "upload pipeline dynamically", "pipeline upload"
- "share data between steps", "meta-data set/get"
- "request OIDC token", "buildkite-agent oidc"
- "distributed lock", "buildkite-agent lock"
- "get step attribute", "update step label"
- "redact secret from logs", "buildkite-agent secret get"
- Any `buildkite-agent <subcommand>` invocation inside a step

**Content outline:**

| Subcommand | What it does | Framework evidence |
|------------|-------------|-------------------|
| `annotate` | Create/update build annotations with styles (default, info, warning, error, success), context keys, markdown content | SURFACE phase — "show errors in the build page." The example pipeline uses annotate extensively for test summaries, triage checklists, and navigation. |
| `artifact upload/download/search/shasum` | Upload files as build artifacts, download from current or other builds, search by glob, verify checksums | Used across all phases. SHARPEN uses artifacts for Docker manifests + SLSA attestations. |
| `meta-data set/get/exists/keys` | Shared key-value store across all jobs in a build. Set in one job, read in another. | SKIP phase — dynamic pipeline generators read meta-data to pass state. Block step field values stored as meta-data. |
| `pipeline upload` | Upload YAML (from file or stdin) to dynamically add steps to the running build | SKIP phase — the core of dynamic pipeline generation. The Python generator pipes YAML to `pipeline upload`. |
| `oidc request-token` | Request a short-lived OIDC token for authentication to external services (package registries, cloud providers) | SHARPEN phase — `--audience URL --lifetime 300`, piped to `docker login --password-stdin`. |
| `step get/update/cancel` | Read or modify step attributes at runtime (label, state, metadata). Cancel a running step. | Useful for conditional logic within steps and build automation. |
| `lock acquire/release/get/do` | Distributed mutex locks across parallel jobs in the same build | SCALE phase — when parallel jobs need to coordinate (e.g., only one job runs a migration). |
| `env dump/get/set/unset` | Inspect and modify the job's environment. `dump` outputs JSON for debugging hook changes. | Debugging lifecycle hooks — see what environment changes hooks made. |
| `secret get` | Retrieve cluster secrets by name at runtime (alternative to `secrets:` YAML key) | Programmatic secret access within scripts when `secrets:` declarative approach isn't flexible enough. |
| `redactor add` | Add values to the log redactor so they're masked in build output | Security — redact dynamically-retrieved secrets that weren't declared in `secrets:`. |
| `tool sign/verify` | Sign or verify pipeline step definitions for integrity checking | SHARPEN phase — pipeline signing verification at the step level. |

---

### Cross-cutting 2: `buildkite-cli` — "Do things from my terminal"

**Jobs served:** All (operational layer)

**Why cross-cutting, not a journey:** The CLI isn't a journey — it's a tool people use throughout every journey. "Trigger a build" happens during pipeline development. "Download artifacts" happens during debugging. "Create a secret" happens during secure delivery setup. No single journey owns it.

**Relationship to MCP server:** Many CLI operations overlap with MCP server tools (`bk build view` ≈ `get_build`, `bk job log` ≈ `read_logs`). The skill teaches CLI syntax for when the agent executes via Bash. When the MCP server is available, the agent may use MCP tools directly instead — no CLI knowledge needed. The skill should note where MCP alternatives exist: "To view build details, run `bk build view <number>`. If the Buildkite MCP server is available, use the `get_build` tool instead."

**What triggers this skill:**
- Any mention of `bk` commands
- "trigger a build", "check build status", "download artifact"
- "from the command line", "from terminal"

**Content outline:**

| Area | Jobs served | MCP alternative |
|------|-------------|-----------------|
| `bk build create/view/list/cancel/retry` | J1, J2 | `create_build`, `get_build`, `list_builds` |
| `bk job log/retry/cancel` | J2 | `read_logs`, `tail_logs` |
| `bk pipeline list/create/update` | J8 | `list_pipelines`, `get_pipeline`, `create_pipeline` |
| `bk secret create/list/delete` | J6 | — (no MCP equivalent) |
| `bk artifact download/upload` | J2 | `list_artifacts_for_build`, `get_artifact` |
| `bk auth login` | All | `current_user`, `access_token` |

---

### Cross-cutting 3: `buildkite-api` — "Automate and integrate programmatically"

**Jobs served:** J8, J6, J7 (automation layer)

**Why separate from CLI:** The CLI is for humans in a terminal. The API is for scripts, webhooks, and integrations. Different user, different context:
- CLI user: "trigger a build while I wait"
- API user: "build a webhook handler that auto-retries failures" or "write a script that scales queues based on wait time"

**Relationship to MCP server:** The MCP server is the agent's **direct** API access — it handles auth, pagination, and response parsing. The `buildkite-api` skill is for when the agent needs to **write code** that calls the API (a webhook handler, a cron script, a custom integration). The skill teaches the endpoints and shapes so the generated code is correct. The MCP server is not a replacement for this skill — it serves a different purpose (agent tool vs user code).

**What triggers this skill:**
- "Buildkite API", "REST API", "GraphQL", "webhook"
- "automate", "integrate", "script that calls Buildkite"
- Any mention of `api.buildkite.com`, `graphql.buildkite.com`

**Content outline:**

| Area | Jobs served | MCP server overlap |
|------|-------------|--------------------|
| REST API (builds, pipelines, organizations, annotations) | All | MCP covers read operations; skill teaches full CRUD + auth for user code |
| GraphQL API (mutations: queue scaling, template creation, cluster management) | J4, J8 | No MCP equivalent for mutations — skill is the only source |
| Webhooks (build.failed, build.fixed, filtering, Slack integration) | J2 | No MCP equivalent — webhooks are receiver-side |
| Webhook handlers (automated remediation, failure routing) | J2, J8 | No MCP equivalent — user-written code |
| Authentication (API tokens, scopes, token management) | All | MCP handles its own auth; skill teaches auth for user code |

---

## v1 vs v2 comparison

| Dimension | v1 | v2 |
|-----------|----|----|
| **Organizing principle** | Product surface (YAML, binary, CLI, APIs) | User journey (what are they trying to accomplish) |
| **Number of skills** | 5 | 7 (4 journey + 3 cross-cutting) |
| **Biggest change** | Test Engine extracted from platform | Secure delivery + platform engineering split from catch-all "platform"; agent infra gets a real home |
| **`buildkite-platform` (v1)** | Catch-all: APIs, webhooks, OIDC, SSO, Test Engine, packages, audit, templates | Split into 3 focused skills: secure-delivery, agent-infrastructure, api |
| **`buildkite-agent` (v1)** | Standalone skill for agent binary | Clusters, queues, hosted agents, secrets, agent config → `buildkite-agent-infrastructure`. Signing → `buildkite-secure-delivery`. Queue routing in YAML → `buildkite-pipelines`. |
| **`buildkite-agent` (v1)** runtime cmds | Mixed into pipelines skill | **buildkite-agent-runtime**: dedicated skill for in-job subcommands (annotate, artifact, meta-data, pipeline upload, oidc, step, lock, env, secret, redactor) |
| **CLI + API** | Separate (CLI only) | Separated: CLI (human terminal) vs API (programmatic automation) |

### What happened to `buildkite-agent`?

v1 had a standalone agent skill scoped to the agent binary. v2 absorbs agent concerns into the journeys where they actually matter:

- **Creating clusters, queues, and configuring hosted agents** → `buildkite-agent-infrastructure` (the platform team provisions infrastructure)
- **`buildkite-agent.cfg`, agent tokens, self-hosted setup, lifecycle hooks** → `buildkite-agent-infrastructure` (same persona, same session)
- **Agent sizing advice** (which instance shape to pick) → `buildkite-agent-infrastructure` (queue creation) AND referenced from `buildkite-pipelines` (when builds are slow)
- **Pipeline signing (JWKS)** → `buildkite-secure-delivery` (part of the secure publish flow)
- **Queue routing from pipeline YAML** (`agents: queue: "linux-large"`) → `buildkite-pipelines` (it's pipeline YAML syntax)

The agent binary doesn't have its own user journey. The platform engineer creating queues and the developer referencing them in YAML are doing different jobs — and v2 puts the content where each person looks for it.

---

## Skill trigger matrix

How user queries route to skills, and which execution path the agent uses:

| User says | Skill | Agent executes via | MCP tools available |
|-----------|-------|--------------------|---------------------|
| "my build takes 20 minutes" | buildkite-pipelines | File edit (pipeline.yml) | `get_build`, `read_logs` to diagnose |
| "add caching to this pipeline" | buildkite-pipelines | File edit | — |
| "show test failures in the build page" | buildkite-pipelines + buildkite-agent-runtime | File edit (pipeline YAML + annotate command) | `list_annotations` to check existing |
| "only run tests when code changes" | buildkite-pipelines | File edit | — |
| "add an annotation to this step" | buildkite-agent-runtime | File edit (step script) | — |
| "share data between steps" | buildkite-agent-runtime | File edit (`meta-data set/get`) | — |
| "upload pipeline dynamically from a script" | buildkite-agent-runtime | File edit (`pipeline upload`) | — |
| "acquire a lock so parallel jobs don't collide" | buildkite-agent-runtime | File edit (`lock acquire/release`) | — |
| "redact this secret from the logs" | buildkite-agent-runtime | File edit (`redactor add`) | — |
| "get an OIDC token inside the step" | buildkite-agent-runtime | File edit (`oidc request-token`) | — |
| "why did this build fail" | buildkite-pipelines | — (read-only) | `get_build`, `read_logs`, `list_annotations` |
| "split my tests across 10 machines" | buildkite-test-engine | File edit + Bash (bktec) | `get_test_run`, `get_failed_executions` |
| "is this test flaky" | buildkite-test-engine | — (read-only) | `get_test`, `list_test_runs` |
| "set up OIDC for docker registry" | buildkite-secure-delivery | File edit (pipeline.yml) | — |
| "sign our pipelines" | buildkite-secure-delivery | File edit (agent config) | — |
| "create a cluster and queue" | buildkite-agent-infrastructure | Bash (GraphQL) or MCP | `list_clusters`, `get_cluster`, `list_cluster_queues` |
| "set up hosted agents" | buildkite-agent-infrastructure | Bash (GraphQL) or MCP | `get_cluster_queue` to verify |
| "add a secret to the cluster" | buildkite-agent-infrastructure | Bash (API call) | — |
| "configure self-hosted agents" | buildkite-agent-infrastructure | File edit (agent.cfg) | — |
| "queue wait time is too high" | buildkite-agent-infrastructure | — (diagnose) | `get_cluster_queue` for metrics |
| "create a pipeline template" | buildkite-agent-infrastructure | Bash (GraphQL) | `list_pipelines` to verify |
| "set up audit logging" | buildkite-agent-infrastructure | Bash (API) | — |
| "how much is CI costing us" | buildkite-agent-infrastructure | Bash (API) | `list_builds` for volume data |
| "trigger a build" | buildkite-cli | Bash (`bk build create`) | `create_build` (MCP alternative) |
| "check the latest build" | buildkite-cli or MCP | Bash (`bk build view`) | `get_build` (MCP alternative) |
| "show me the build logs" | buildkite-cli or MCP | Bash (`bk job log`) | `read_logs`, `tail_logs` (MCP alternative) |
| "write a script that auto-retries failures" | buildkite-api | Code generation | — (agent writes code that calls API) |
| "scale queue based on wait time" | buildkite-api | Code generation | — (agent writes code that calls API) |

---

## Impact map

| Framework outcome | Target | Primary skill | Supporting |
|-------------------|--------|---------------|------------|
| CI Feedback Time <10 min | START | buildkite-pipelines | buildkite-agent-infrastructure (sizing, queues) |
| Queue wait <2 min | START/SCALE | buildkite-agent-infrastructure | — |
| Time to Triage <10 min | SURFACE | buildkite-pipelines | buildkite-api (webhooks) |
| Build speed +10-30% | SKIP | buildkite-pipelines | — |
| Test suite -20-40% | SCALE | buildkite-test-engine | buildkite-pipelines (parallelism), buildkite-agent-infrastructure (queues) |
| Flaky rate <3% | SKIP/SCALE | buildkite-test-engine | — |
| Zero static credentials | SHARPEN | buildkite-secure-delivery | — |
| Signed + attested artifacts | SHARPEN | buildkite-secure-delivery | — |
| Cost per merge -20-30% | SHARPEN | buildkite-agent-infrastructure | buildkite-api (GraphQL) |

---

## What this still does NOT include

| Rejected idea | Why |
|---------------|-----|
| A "5S framework" skill | Journey doc for humans, not agent behavior |
| Phase-based skills (one per S) | Wrong axis — adoption timeline, not user intent |
| A standalone "buildkite-agent" skill | Agent config isn't a journey — it's split across agent-infrastructure (provisioning), secure-delivery (signing), and pipelines (queue routing in YAML) |
| A "migration" skill | Tempting (framework has a comparison table) but too narrow and too variable across source platforms |
| A "monorepo" skill | Framework flags it as an adjustment, not a separate journey. Monorepo patterns are dynamic pipelines (in pipelines skill) + governance concerns |
| A "troubleshooting" skill | Troubleshooting is contextual to each journey — "slow build" troubleshooting is in pipelines, "flaky test" troubleshooting is in test-engine |
