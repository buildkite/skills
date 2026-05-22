# Hosted agent namespace integration and concurrency

Anchor: Linear PS-400 (11x.ai) — *"Builds are failing, Seeing a Spike in Errors in Namespace — namespace.so errors visible only via separate admin UI."* This reference covers concurrency arithmetic, the wait-time alerting runbook, and the (limited) namespace.so escalation playbook.

## Concurrency arithmetic

Hosted Linux concurrency = `plan's max combined vCPU / instance-shape vCPU`.
Hosted macOS concurrency = `plan's Mac M4 max combined vCPU / instance-shape vCPU`.

### Worked example — Linux

Plan: 48 max combined vCPU. Queue: `LINUX_AMD64_4X16` (Medium, 4 vCPU).

```
48 / 4 = 12 concurrent agents
```

If the same plan provisions a Large queue instead (`LINUX_AMD64_8X32`, 8 vCPU):

```
48 / 8 = 6 concurrent agents
```

Same plan, half the concurrency. Anti-pattern: budgeting concurrent agents from the plan page without dividing by the largest instance shape in use.

### Worked example — macOS

Plan: 24 max combined Mac M4 vCPU. Queue: `MACOS_ARM64_M4_6X28` (Medium, 6 vCPU).

```
24 / 6 = 4 concurrent agents
```

### Mixed-shape clusters

Concurrency is divided by *each queue's* instance shape independently. A cluster with one Medium Linux queue (4 vCPU) and one Large Linux queue (8 vCPU), against a 48 vCPU plan, can run 12 Medium agents *or* 6 Large agents — but those agents share the same 48 vCPU budget across queues. Two Large agents reduce the Medium queue's effective ceiling.

### Plan-tier reference points

The exact "max combined vCPU" depends on the plan and any custom additions; the public pricing page is the source of truth. Reasonable rough orders of magnitude:

| Plan tier | Linux max combined vCPU (order of magnitude) | Mac M4 max combined vCPU (order of magnitude) |
|---|---|---|
| Personal | Small only | Not available |
| Pro | Tens | Tens |
| Enterprise | Hundreds | Tens-to-hundreds, with extras on request |

Always confirm exact values against the customer's billing page before quoting capacity.

## Wait-time alerting runbook

Hosted does not surface concurrency exhaustion as an error in pipeline logs. Jobs queue silently and start when capacity frees. The observable signal is **wait time** (the gap between job-scheduled and job-started timestamps).

Recommended alert: **P95 hosted-queue wait time > 60s sustained for 5+ minutes**.

Sources for wait time:
- Buildkite REST API: `GET /v2/organizations/{org}/pipelines/{pipeline}/builds` → per-job `started_at` minus `scheduled_at`.
- GraphQL: `Job.startedAt` minus `Job.scheduledAt`.
- Buildkite Insights / cluster operational view (UI): per-queue wait-time distribution.

> For the API call mechanics — pagination, rate limits, authentication — see the **buildkite-api** skill.

### Reading the operational view

The cluster operational view (Agents → cluster → operational view) is the canonical surface for hosted-agent health. Look for:

- Per-queue **wait time** distribution. Spike correlates with concurrency exhaustion.
- Per-queue **running agents** count. Plateau at the concurrency cap confirms exhaustion.
- **Failed builds** by reason. A sudden jump in unattributable infra failures is the PS-400 signal — see next section.

## namespace.so error escalation playbook

**namespace.so is the underlying compute provider for Buildkite hosted agents.** When namespace.so has an incident, hosted agents see infra errors that surface in a separate admin/operational UI — not on the customer's build page.

PS-400 (11x.ai) escalated exactly this case: builds were failing with no useful pipeline-side error, but Buildkite's operational view showed a namespace.so spike.

### Response playbook

When a customer reports "spike in errors in namespace" or unattributable build failures with no pipeline-side error:

1. **Gather the timestamp window.** First failure, last failure, current state. UTC.
2. **Pull the cluster operational view** for the same window. Note any infra-side error indicator.
3. **Confirm the customer's pipeline.yml has not changed.** Eliminate the pipeline-side hypothesis.
4. **Escalate to `support@buildkite.com`** with the timestamp window, cluster name, queue name, and a representative build URL. Support has visibility into the namespace.so operational UI that customers do not.
5. **Do not invent a fix.** namespace.so internals are not customer-self-serviceable. Suggesting retry/restart/cache-clear when the failure is upstream wastes the customer's time and damages credibility.

### What customers can self-serve

Limited surface. If the operational view shows the queue is healthy and the pipeline is at fault:

- Confirm wait time is not the actual problem (see previous section).
- Confirm the image is reachable and `ca-certificates` is present (see `references/image-lifecycle-patterns.md`).
- Check terminal access for OS-level errors during a running job (`dmesg`, `journalctl -xe`).

If the operational view shows infra-side errors, escalate. Full stop.

## Requesting capacity changes

Three classes of capacity request, all via `support@buildkite.com`:

| Request | Triggered by |
|---|---|
| Extra-large Linux instance shapes | Workloads that legitimately need 16+ vCPU per agent — large native builds, GPU-adjacent workloads |
| Linux jobs > 8 hours | Long-running integration tests, large data processing |
| macOS jobs > 4 hours | Large iOS apps with deep test matrices |

Provide: plan tier, cluster name, queue name, expected concurrency, expected job duration. Support cannot grant these from a Plain thread alone without that context.

## Cross-references

- Image-side reasons jobs may not start: `references/image-lifecycle-patterns.md` "Issues with starting a job" decoder.
- Cache-volume sizing in concurrency-heavy workloads: `references/cache-volume-sizing.md`.
- For pipeline-level concurrency keys (`concurrency:`, `concurrency_group:`) and YAML routing semantics, see the **buildkite-pipelines** skill — those are pipeline-side, not queue-side.
