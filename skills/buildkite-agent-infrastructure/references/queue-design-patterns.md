# Queue design patterns

Worked examples for sizing, splitting, and operating queues at scale. Pair with the Phase 2 decision rules in SKILL.md.

## Little's Law applied to queue sizing

For a steady-state queue:

```
L = λ × W
```

Where:

- `L` — average number of jobs in the system (queued + running)
- `λ` — job arrival rate (jobs per unit time)
- `W` — average job dwell time (wait time + execution time)

To size for a target P95 wait time, the simpler practical form is:

```
required_concurrent_agents ≈ (peak_arrival_rate × median_job_duration) / target_utilisation
```

Target utilisation should be 0.6–0.7 in steady state to absorb arrival-rate variance. Anything above 0.85 produces a long tail of wait times even when average utilisation looks fine.

### Worked example — 1,000 builds/day

Assume:

- 1,000 builds/day, each with 10 jobs on average → 10,000 jobs/day
- Even distribution → ~7 jobs/minute average; peak ~21 jobs/minute (3× burst)
- Median job duration: 4 minutes
- Target utilisation: 0.65

```
required_agents ≈ (21 × 4) / 0.65 ≈ 130
```

In practice, 1,000 builds/day rarely needs 130 agents because the arrival pattern is not perfectly bursty. Start with 50 concurrent agents and tune from observed P95 wait time. Single queue is fine at this scale.

### Worked example — 10,000 builds/day

- 10,000 builds × 15 jobs/build → 150,000 jobs/day
- ~100 jobs/minute average; ~300 jobs/minute peak
- Median job duration: 5 minutes (longer pipelines at scale)
- Target utilisation: 0.65

```
required_agents ≈ (300 × 5) / 0.65 ≈ 2,300
```

At this scale, single-queue is unsafe — a long-running job class can starve the queue. Split by workload:

| Queue | Share of jobs | Concurrent agents |
|---|---|---|
| `linux-amd64-small` (lint, format) | 40% | 800 |
| `linux-amd64-medium` (unit tests) | 35% | 700 |
| `linux-amd64-large` (integration, build) | 20% | 600 |
| `macos-arm64-medium` (iOS) | 5% | 100 |

Per-workload queues also unlock per-queue scaler tuning (different idle timeouts, different spot-vs-on-demand mixes).

### Worked example — 100,000 builds/day

- 100,000 builds × 20 jobs/build → 2,000,000 jobs/day
- ~1,400 jobs/minute average; ~4,200 jobs/minute peak
- Per-queue agent count crosses the limit at which a single Buildkite cluster's scheduling latency begins to dominate

At this scale:

- Split into multiple Buildkite clusters by geography or regulatory boundary (e.g., US, EU, gov-cloud).
- Per-cluster, retain per-workload queues. Total of 10–20 queues across the org.
- Run two or more Agent Stack for Kubernetes controllers per cluster with leader election.
- Use a separate observability stack scoped to the agent layer (Prometheus + Grafana fed by the controller's `/metrics` endpoint plus Buildkite Insights queue metrics).

## Per-team vs per-workload queues

| Axis | Per-workload | Per-team |
|---|---|---|
| Routing primitive matches | The job's compute requirements | The job's owning team |
| Scaling target | One per OS/size combination | One per team — typically 10–50 queues |
| Cost attribution | Indirect — requires job-to-team mapping outside Buildkite | Direct — queue maps 1:1 to team |
| Operational cost | Lower — fewer queues to scale | Higher — every team needs scaling tuning |
| Risk profile | A long-running job class can starve a queue | A team's runaway job count cannot affect other teams |

Default to per-workload. Add per-team only when cost attribution is a board-level requirement or when one team's misbehaviour is repeatedly affecting another team's builds.

## Multi-cluster patterns

Reach for multiple Buildkite clusters when:

- **Geographic isolation** — EU data residency, US gov-cloud, AP regional egress costs
- **Regulatory boundary** — PCI scope, HIPAA scope, SOC 2 scope kept separate from general engineering
- **Blast radius** — separating a noisy or experimental workload from the production cluster

Multi-cluster trade-offs:

- Cluster tokens, queue keys, and observability stacks duplicate per cluster
- Cross-cluster pipeline triggers add latency
- Internal tooling (e.g., a custom build-status dashboard) must aggregate across clusters

If the goal is only cost attribution, use per-team queues within one cluster. Multi-cluster is a heavier hammer.

## Queue depth and wait-time alerting

Minimum alert set:

| Alert | Threshold | Action |
|---|---|---|
| `P95(wait_time_per_queue)` exceeds SLA | Per-queue SLA (e.g., 60s for `linux-amd64-small`, 300s for `linux-amd64-large`) | Page on-call; investigate scaler health |
| `queue_depth_per_queue` exceeds 10× concurrent agents | Static threshold | Investigate stuck dispatch or a runaway pipeline |
| `controller_pod_restart_count` | >0 in a 5-minute window | Page on-call; controller pod is unstable |
| `agent_disconnect_rate_per_queue` | Above baseline + 3σ | Page on-call; correlate with VPC flow logs |

The Buildkite Cluster Queue Job Explorer surfaces real-time queue depth in the UI; programmatic monitoring requires the REST API or Buildkite Insights queue metrics export.

## Hosted-vs-self-hosted audit checklist

Before adopting hosted agents for a workload, confirm:

- [ ] **Egress** — does the workload require allowlisting Buildkite hosted IP ranges in third-party services?
- [ ] **VPC-only** — does the workload need to reach VPC-private resources (private RDS, internal services)? Hosted agents cannot.
- [ ] **Regulated data** — does the workload process data subject to data-residency or regulatory boundary constraints?
- [ ] **Custom system packages** — does the workload need OS packages outside the hosted image catalogue?
- [ ] **Boot-time setup** — does the workload need to bootstrap with credentials injected from a specific cloud provider?
- [ ] **Concurrency cap** — does the workload's peak concurrency exceed the hosted-queue cap?
- [ ] **Cost** — does the per-minute hosted cost beat self-hosted at this workload's utilisation profile?

If three or more of these are deal-breakers, stay self-hosted. If all pass, hosted agents are the lower-operational-cost choice.

## Anti-patterns

- **Queue per pipeline.** Routing explosion; agents cannot share idle capacity; scaling per pipeline is intractable.
- **One queue for everything.** A long-running job class starves short jobs. Split at the first workload-class divergence.
- **Queue keys with semantic meaning that changes.** A queue key is part of the routing contract — changing it requires every pipeline using it to update.
- **Disabling queue depth alerts during incidents.** The alerts are the early-warning signal; disabling them masks the next incident.
