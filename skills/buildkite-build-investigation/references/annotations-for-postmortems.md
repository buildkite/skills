# Annotations for Postmortems

Phase 5 (Record) leaves an investigation visible to the next person who lands on the build. The recommended carrier is a build annotation with a stable context, plus structured meta-data that downstream automation can read without parsing prose.

This reference covers the annotation contexts, styles, and meta-data keys to use, and a worked example for the three most common patterns.

## Why annotate

Three audiences read the annotation:

1. **The next human investigator** who clicks the build URL ten minutes later.
2. **A reviewing agent** doing batch triage across the cohort.
3. **Downstream automation** (deploy gates, notifications, audit logs) that reads `failure-reason` meta-data.

A good annotation serves all three: a one-line headline, a short paragraph of context, optional links, and a meta-data field encoding the category.

## Conventions

### Contexts

A **context** is a stable identifier for the annotation; reusing it replaces rather than duplicates. The investigation skill writes to one of these:

| Context | Purpose | When written |
|---|---|---|
| `root-cause` | The investigation conclusion | Phase 5 (Record) |
| `next-steps` | What the next investigator should do | When the investigation is incomplete |
| `escalation` | Pointer to a support ticket or SRE incident | When platform escalation is needed |
| `cohort` | Pointer to related failures in the cohort | When the failure is one of N |

Use `--context` (not `--id`) so the value is human-readable in the API.

### Styles

| Style | Use for |
|---|---|
| `error` | Investigation found a real failure (test or infra) |
| `warning` | Failure with workaround applied; future work needed |
| `info` | Informational record (no action needed) |
| `success` | Investigation resolved with verified fix |

### Meta-data keys

The failure-attribution category goes here so downstream automation can branch on it:

| Key | Value | Source |
|---|---|---|
| `failure-reason` | One of: `test-real`, `infra-oom`, `infra-agent-disconnect`, `infra-scheduler`, `infra-agent-token`, `network`, `config-yaml`, `upstream-metadata`, `upstream-event-timing`, `regression-rollout`, `data-env`, `quota-matrix`, `test-flaky-candidate` | Phase 5, after Phase 4 verification |
| `failure-component` | Pipeline step / module / service name | Phase 2 (Localize) result |
| `failure-first-seen` | ISO8601 timestamp of first failure in cohort | Phase 1 (Orient) result |
| `investigation-link` | URL to incident, ticket, or runbook | Phase 5 |

PF-9400 — Anthropic's request for a first-class `failure_reason` field on build metadata — is addressed in the meantime by writing the same value as build meta-data with this key.

## Worked example: OOM root cause

```bash
buildkite-agent annotate --style "error" --context "root-cause" <<'EOF'
**Root cause: OOMKilled in step `build-image`**

Agent `i-0abc1234` in queue `docker-large` was killed by the kernel OOM
at 2026-05-19T14:02:13Z. Memory headroom on the host was 2.1 GB at start;
the docker build consumed 6.8 GB at peak.

- Failure category: `infra-oom`
- First seen: 2026-05-19T13:48:00Z (3 builds back)
- Cohort: 5 of the last 10 builds on this pipeline failed the same way
- Datadog: <https://app.datadoghq.com/dashboard/abc-xyz?from_ts=...>
- Suggested fix: bump `docker-large` agent memory request, or split the
  build into smaller layers. Hand off to the platform team.
EOF

buildkite-agent meta-data set "failure-reason" "infra-oom"
buildkite-agent meta-data set "failure-component" "build-image"
buildkite-agent meta-data set "failure-first-seen" "2026-05-19T13:48:00Z"
```

## Worked example: webhook state trap recorded

```bash
buildkite-agent annotate --style "warning" --context "root-cause" <<'EOF'
**Root cause: webhook payload state stale (PS-1300 pattern)**

`build.finished` webhook arrived at 14:02Z with `state: running`. REST
`GET /organizations/.../builds/47` returns `state: passed`. Downstream
consumer should fetch canonical state via API, not rely on payload state.

- Failure category: `upstream-event-timing`
- Reference: `references/webhook-state-traps.md`
- Consumer-side fix tracked in: <ticket-url>
EOF

buildkite-agent meta-data set "failure-reason" "upstream-event-timing"
```

## Worked example: incomplete investigation handed over

```bash
buildkite-agent annotate --style "warning" --context "next-steps" <<'EOF'
**Investigation incomplete — handing off**

Reached Phase 3 (Correlate). Hypothesis: agent-version regression after
the 06:00Z deploy of agent 3.106.0. Need to verify by rerunning the same
job on the previous agent version.

- Failure category (provisional): `regression-rollout`
- Next step: run `bk build retry 42 --pipeline my-app` with agent pinned
  to 3.105.x on the `docker-large` queue. If green, this is PS-1200.
- Cohort: 8 of last 12 builds failed identically; all started after 06:00Z.
EOF
```

## Anti-patterns

- **Annotating "build failed" with no detail.** Adds noise, no signal. The next investigator still has to redo Phases 1–4.
- **Annotating without a stable context.** Re-runs create duplicate annotations; the build page fills with copies.
- **Reusing `root-cause` for a guess.** `root-cause` means Phase 4 verified the cause. Use `next-steps` or `cohort` for hypotheses.
- **Putting secrets, tokens, or customer data in the annotation body.** Annotations are visible to anyone with build read access.
- **Annotating only in the success path.** Phase 5 runs on failure investigations; do not skip it because the build did not pass.

## Cross-references

- For the `buildkite-agent annotate` and `buildkite-agent meta-data set` command syntax, flags, and patterns, see the **buildkite-agent-runtime** skill.
- For the failure-category vocabulary, see `failure-attribution-decision-tree.md`.
- For where in the investigation loop this fits, see SKILL.md Phase 5 (Record).
