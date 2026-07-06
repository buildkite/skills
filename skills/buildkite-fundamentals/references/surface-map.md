# Surface Map

Buildkite exposes five surfaces. Each has a different auth model, a different rate-limit pool, and a different intended caller. This reference maps intent to surface for AI agents and human operators alike.

## The five surfaces

| Surface | Endpoint | Auth | Caller | Rate-limit pool |
|---|---|---|---|---|
| MCP server | `mcp.buildkite.com` | OAuth (per-user, no static token) | AI agents driving CI from outside | Separate quota, per user |
| REST API | `api.buildkite.com` | Bearer API token | Resource CRUD from any external system | Org-shared, by token |
| GraphQL API | `graphql.buildkite.com` | Bearer API token | Complex queries, joins, server-side filtering | Org-shared, by token |
| `bk` CLI | local binary | `bk auth login` (OAuth-backed local token) | Developers from a laptop or terminal | Inherits REST quota |
| `buildkite-agent` | binary on agent host | `BUILDKITE_AGENT_ACCESS_TOKEN` in job env | Code running inside a running job | Distinct per-agent channel |

## Pick a surface by intent

| Intent | Use | Why |
|---|---|---|
| Read a build's state, jobs, annotations, or logs from an AI assistant | MCP | OAuth, tool schemas self-document, separate rate quota |
| Post an annotation from outside a running build | MCP | Tools exist for this; avoids token management |
| List or filter pipelines with conditions across multiple fields | GraphQL | Single round-trip, server-side filtering |
| Count builds, sum durations, fetch aggregate metrics | GraphQL | Connection types enable counts without paging the full list |
| Create a pipeline, build, schedule, or update provider settings | REST | Mutation surface for resource lifecycle |
| Re-run, cancel, or rebuild a build | REST | Idempotent mutation endpoints |
| Trigger a build from a developer laptop | `bk` CLI (`bk build create`) | OAuth-backed local auth, no API token to manage |
| Watch a running build from a terminal | `bk` CLI (`bk build watch`) | Streams from the API with sensible defaults |
| Annotate, upload artifacts, set or get meta-data inside a job | `buildkite-agent` | Only surface with access to in-job context (`BUILDKITE_AGENT_ACCESS_TOKEN`) |
| Request an OIDC token inside a job for cloud auth | `buildkite-agent oidc request-token` | Audience and claim mapping configured per-step |
| Upload dynamically generated pipeline steps from inside a build | `buildkite-agent pipeline upload` | Stream stdin or a file into the running build |

## Decision rules

1. **From an AI agent, default to MCP.** Reach for REST or GraphQL only when MCP does not expose the operation.
2. **From inside a job, use `buildkite-agent`.** Calling REST from within a job works but loses the auto-redaction, audit trail, and ergonomic flags that the in-job binary provides.
3. **From outside a job, never use `buildkite-agent`.** Its subcommands need `BUILDKITE_AGENT_ACCESS_TOKEN`, which only exists in a job environment. From a laptop, use `bk`. From a server-side script, use REST, GraphQL, or MCP.
4. **REST for resources, GraphQL for queries.** Mutating an unfamiliar resource via GraphQL costs more in trial-and-error than reading the REST endpoint reference.
5. **Pick one auth strategy per integration.** Mixing API tokens and OAuth in the same automation is a maintenance trap.

## Owning skills

| Surface | Owning skill |
|---|---|
| MCP server, REST, GraphQL, webhooks | **buildkite-api** |
| `bk` CLI | **buildkite-cli** |
| `buildkite-agent` in-job subcommands | **buildkite-agent-runtime** |

This reference does not duplicate parameter schemas, endpoint references, or webhook payload shapes — those live in the owning skills.
