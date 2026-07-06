# Orient Quick Queries

Phase 1 (Orient) is mechanical. The agent has a build URL or `<pipeline> <number>` and needs build state, exit codes, retry counts, annotations, meta-data, and the failure cohort — fast.

This reference is a recipe book for that data, across `bk`, MCP, and REST. Use it as a lookup, not a tutorial.

## Inputs the agent typically has

- A build URL: `https://buildkite.com/my-org/my-app/builds/42`
- Or a pair: pipeline slug (`my-org/my-app`) and build number (`42`)
- Or a job ID (UUID)

Parsing a build URL:

```bash
URL="https://buildkite.com/my-org/my-app/builds/42"
ORG=$(echo "$URL" | awk -F/ '{print $4}')
PIPE=$(echo "$URL" | awk -F/ '{print $5}')
NUM=$(echo "$URL" | awk -F/ '{print $7}')
```

## Recipe: one-shot bundle

The single most useful command. Returns everything Phase 1 needs in one Markdown block.

```bash
scripts/investigate-build.sh https://buildkite.com/my-org/my-app/builds/42
```

Use this first. Fall back to the individual queries below when the bundle is missing a specific datum.

## Recipe: build state, jobs, exit codes

| Need | `bk` command | MCP tool | REST endpoint |
|---|---|---|---|
| Build state and metadata | `bk build view 42 --pipeline my-org/my-app --output json` | `get_build` | `GET /organizations/:org/pipelines/:slug/builds/:n` |
| Job list with exit codes | `bk build view 42 ... --output json \| jq '.jobs[]'` | `get_build` (jobs included) | same |
| Just failed jobs | `bk build view 42 ... --output json \| jq '.jobs[] \| select(.state=="failed")'` | filter `get_build` result | same |

## Recipe: failure cohort

```bash
# Last 20 failed builds for the pipeline
bk build list --pipeline my-org/my-app --state failed --output json | jq '.[0:20]'

# How many of the last 20 builds failed?
bk build list --pipeline my-org/my-app --output json \
  | jq '[.[0:20] | .[] | select(.state=="failed")] | length'

# Are the failures clustered in time?
bk build list --pipeline my-org/my-app --state failed --output json \
  | jq '.[0:20] | .[] | {number, state, finished_at}'
```

MCP: `list_builds` with `state=failed` returns the same shape.

## Recipe: annotations and meta-data

```bash
# Annotations on the build
bk api /organizations/my-org/pipelines/my-app/builds/42/annotations \
  | jq '.[] | {context, style, body_html: .body_html[0:200]}'

# Meta-data
bk api /organizations/my-org/pipelines/my-app/builds/42/meta_data
```

MCP: `list_annotations` returns annotations. Meta-data is included in `get_build`.

## Recipe: job log tail

The full log is often too long to read. The tail and the summary are the right starting point.

```bash
# Tail
bk job log <job-id> --pipeline my-org/my-app --build 42 | tail -200

# Summary (Test Engine output, last N lines, exit code) without full log
bk job log <job-id> --pipeline my-org/my-app --build 42 --print-job-summary
```

MCP: `read_logs` returns the full log. `tail_logs` streams; for Phase 1, `read_logs` then a client-side `tail` is enough.

## Recipe: agent that ran the job

```bash
bk build view 42 --pipeline my-org/my-app --output json \
  | jq '.jobs[] | select(.id=="<job-id>") | {agent_id: .agent.id, agent_name: .agent.name, agent_meta: .agent.meta_data}'
```

Useful for Phase 3 correlation: did all failures land on the same agent or the same queue?

## Recipe: who triggered the build

```bash
bk build view 42 --pipeline my-org/my-app --output json \
  | jq '{creator: .creator.name, source: .source, branch, commit, message}'
```

`source` distinguishes webhook-triggered builds (push, PR) from API-triggered (manual, scheduled, triggered-from-parent).

## Recipe: trigger relationship (was this build triggered by another?)

```bash
bk build view 42 --pipeline my-org/my-app --output json \
  | jq '.triggered_from'
```

Non-null means the build was created by a parent pipeline's `trigger` step. The parent's meta-data is reachable via that build's API endpoint — useful when the same job fails when triggered but passes on direct run (PF-9500 Aiven priority cascade pattern).

## Recipe: the build's environment

```bash
# All BUILDKITE_* env vars the build sees (requires the build to expose them)
bk build view 42 --pipeline my-org/my-app --output json | jq '.env'
```

Critical for Phase 4 verification: reproducing locally requires matching the failing build's env, not the current shell's env.

## When to skip ahead to MCP

If the user has the Buildkite MCP server connected, prefer MCP over shell. `get_build`, `list_builds`, `list_annotations`, `read_logs`, `tail_logs`, and `get_failed_executions` cover Phase 1 entirely and avoid shell-quoting issues. Fall back to `bk` for operations MCP does not cover (rare in Phase 1).

## Cross-references

- For the command syntax and parameters of every `bk` and MCP call above, see the **buildkite-cli** skill.
- Once Phase 1 is complete, classify the signature using `failure-attribution-decision-tree.md`.
