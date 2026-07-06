# Failure-Attribution Decision Tree

Anthropic's PF-9400 ask is for a first-class `failure_reason` field on build metadata so an LLM evaluator can tell "the build failed because the model wrote bad code" apart from "the build failed because Kubernetes evicted the pod". Until the platform ships that field, this table is the decision tree an agent runs to compute the same classification.

Format: **signature → category → first signal to check → recommended downstream skill or reference**. Run top to bottom; the first matching row is the working hypothesis. Confirm in Phase 4 (Verify) before recording.

## Infra — memory, CPU, disk

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Exit code 137, `Killed` or `OOMKilled` in log tail | infra-oom | `bk job log` for `Killed` / `OOMKilled`; `kubectl get events` on agent-stack-k8s | **buildkite-agent-infrastructure** (resource class) |
| Exit code 139 (SIGSEGV) inside the test binary | test-segfault | Core dump or stack trace in the framework output | **buildkite-preflight** for local repro |
| Exit code 143 (SIGTERM) shortly after `agent_stopped_at` | infra-cancellation | Agent cancellation event; build was canceled or queue was drained | **buildkite-agent-infrastructure** |
| `no space left on device` or `ENOSPC` in log | infra-disk | Agent disk usage telemetry; cache size | **buildkite-agent-infrastructure** (disk sizing) |
| `context deadline exceeded` from agent (no exit code) | infra-timeout | Job `timeout_in_minutes` vs `started_at`/`finished_at` delta | **buildkite-pipelines** (timeout) or **buildkite-agent-infrastructure** (agent-side) |

## Infra — agent and network

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Exit code -1, "agent lost contact" in build view | infra-agent-disconnect | Agent connection events at `agent_stopped_at`; `agent_id` in `bk build view` | `agent-disconnect-diagnostics.md`, **buildkite-agent-infrastructure** |
| Stalled job, empty log, no exit code | infra-scheduler | Missing-K8s-events signature (A-1110); `kubectl get events --field-selector involvedObject.name=<pod>` | `agent-disconnect-diagnostics.md`, **buildkite-agent-infrastructure** |
| Agent emits 401 from agent API mid-job | infra-agent-token | Job UUID in token vs current job UUID (PS-300 FlyZipline pattern) | **buildkite-agent-infrastructure** |
| `connection refused` or `dial tcp ... i/o timeout` to internal service | network | Service mesh sidecar readiness; cluster network policy | **buildkite-agent-infrastructure** (network) |
| Repeated `Could not resolve host` | network-dns | Agent host's resolver and cluster DNS | **buildkite-agent-infrastructure** |

## Test — real failure

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Exit code 1, test framework output, assertion text | test-real | Test Engine summary or `--print-job-summary` | **buildkite-preflight** for local repro |
| Exit code 1, single test failing, other tests pass | test-real-single | Test name, frame in stack trace | **buildkite-preflight** |
| Exit code 1, intermittent across reruns | test-flaky-candidate | Failure rate across last 50 runs; Test Engine flaky-test analytics | future **buildkite-test-engine** |
| Exit code 1, order-dependent (passes in isolation) | test-order-dependent | Test runner config (parallelism, sharding, seed) | future **buildkite-test-engine** |

## Config — pipeline or step

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Pipeline upload step fails with YAML parse error | config-yaml | Upload step's log; `buildkite-agent pipeline upload --dry-run` locally | **buildkite-pipelines**, **buildkite-dynamic-pipelines** |
| `step does not exist` / `unknown plugin` | config-step | Pipeline YAML diff; plugin registry availability | **buildkite-pipelines** |
| `if_changed` matched nothing on a change that should match | config-filter | The `if_changed` glob and the actual diff | **buildkite-pipelines** |
| Step skipped silently with no error | config-skipped | Step `skip:` field, branch filter, concurrency group lock | **buildkite-pipelines** |

## Upstream — parent build or webhook

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Same job fails when triggered, passes on direct run | upstream-metadata | `build_meta_data` from triggering build vs current | **buildkite-pipelines** (trigger), **buildkite-agent-runtime** (meta-data) |
| Build state inconsistent with `build.finished` webhook | upstream-event-timing | Compare REST `get_build` vs webhook payload (PS-1300 pattern) | `webhook-state-traps.md`, **buildkite-api** |
| Ghost build running for hours with all jobs finished | upstream-stuck-state | `get_build` state vs job states; PS-505 Airtable pattern | `webhook-state-traps.md`, **buildkite-api** |

## Regression — agent or stack version

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| New failure across the fleet starting at a known time | regression-rollout | Agent version diff across the cohort; agent-stack-k8s controller version | **buildkite-agent-infrastructure** |
| Pre-command hooks suddenly stopped running | regression-hook-path | PS-1200 Mistral pattern — `localHookPath` regression in agent 3.106+ / controller v0.32+ | **buildkite-agent-infrastructure** |
| Pods rejected by k8s after stack upgrade, logs empty | regression-pod-spec | PS-1250 Doordash hugepages pattern; `kubectl get events` shows the spec rejection | **buildkite-agent-infrastructure** |

## Data — environment, secrets, external

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| Test fails only in CI, passes locally with same commit | data-env | Diff `BUILDKITE_*` and pipeline env vs local; missing secret or feature flag | **buildkite-preflight** |
| Failure correlates with external API rate limit | data-rate-limit | Upstream API's rate-limit response in the log | **buildkite-agent-runtime** (retry), **buildkite-pipelines** (retry) |

## Quota — Buildkite-side or cloud limits

| Signature | Category | First signal | Hand off to |
|---|---|---|---|
| `Matrix limit exceeded` (PS-656, PS-1350) | quota-matrix | Matrix size in pipeline YAML vs org limit | **buildkite-pipelines** |
| Cloud provider quota error in agent provisioning | quota-cloud | Agent autoscaler logs; cloud quota dashboard | **buildkite-agent-infrastructure** |

## Flake — only after Phase 4 verification

A failure earns the `flake` label only after Phase 4 produces statistical evidence (Test Engine flaky-test analytics, or ≥3 reruns showing intermittent failure with no code change). Until then, label the working hypothesis precisely — `test-flaky-candidate`, `infra-intermittent-candidate` — so the recorded annotation does not mislead the next investigator.

## Using this tree

1. Read the failing job's log tail (~200 lines) and exit code.
2. Walk the table top to bottom — the first matching row is the hypothesis.
3. Run the **first signal** column to confirm before moving on.
4. If two rows match (e.g. a 137 and a network error in the same log), the later signal usually wins; treat earlier matches as symptoms.
5. Record the category in build meta-data: `buildkite-agent meta-data set "failure-reason" "<category>"`.
