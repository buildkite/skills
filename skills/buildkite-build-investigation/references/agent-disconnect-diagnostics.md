# Agent Disconnect Diagnostics

Three escalations anchor this reference:

- **PS-300 (FlyZipline, Sev 3)** — Agents intermittently receiving 401s from the agent API mid-job, due to invalid job UUID in the job token. Token invalidation cascades into the agent losing contact and the job being marked failed with exit code -1.
- **PS-500 (Boston Dynamics, Sev 7)** — Agents in `default-queue` in the default cluster disconnecting suddenly mid-job. The user reported that Datadog traces were not helpful (no spans near the disconnect timestamp). Sev 7 is the highest severity used in the Pipelines support workflow.
- **A-1110 (Dropbox)** — On agent-stack-k8s, jobs stall but the failure message displayed to the user does not include the relevant Kubernetes events. The diagnostic surface the agent needs (the k8s event that explains why the pod stalled) is not surfaced into the Buildkite UI; the user has to know to run `kubectl get events` separately.

Together these describe three distinct signatures of "agent disconnect mid-job" with three different diagnostic paths.

## Signature 1: Exit code -1, "agent lost contact"

The classic agent disconnect. The job's exit code is `-1` (the agent never reported a real exit), and `bk build view` shows an `agent_stopped_at` timestamp earlier than the job's `finished_at`.

**Agent-side signal.** The agent process's log around `agent_stopped_at`. Look for:

- `lost connection to buildkite-agent-api` followed by a TCP / TLS error
- `signal: killed` or `signal: terminated` (the agent was killed by the host)
- `context deadline exceeded` on the heartbeat (network partition)

**Queue / cluster-side signal.**

- Other agents in the same queue at the same time: did the whole queue lose contact (cluster-wide network event), or just this one agent (host-specific)?
- Agent autoscaler logs: was the host scaled down while the job was running?

**Hand off to.** **buildkite-agent-infrastructure** — the fix lives in the agent's environment, not the build.

## Signature 2: 401 from agent API mid-job

The PS-300 FlyZipline pattern. The agent process is alive and connected; mid-job, it starts receiving 401s on its API calls back to Buildkite, even though the token was valid moments ago.

**Agent-side signal.** Agent log shows `401 Unauthorized` on calls to `agent.buildkite.com`. The agent typically logs the job UUID it is using; check whether that UUID matches the current `BUILDKITE_JOB_ID`.

**Buildkite-side signal.** The job is canceled or retried under the hood — the original `job_id` may have been invalidated by a state transition the agent has not yet observed.

**Hand off to.** **buildkite-agent-infrastructure** for the agent-side fix; in the meantime, configure the pipeline's retry policy to handle the cancel-and-retry race.

## Signature 3: Stalled job, empty log, no exit code

The A-1110 Dropbox pattern on agent-stack-k8s. The job appears to start but never produces meaningful log output and never finishes. Exit code is empty; `agent_stopped_at` is empty; the build view says the job is `running` but no progress is being made.

**Agent-side signal.** On agent-stack-k8s, the agent never started the job — the pod did not reach Ready, or the pod was rejected by the scheduler. The Buildkite UI does not currently surface the underlying Kubernetes event (A-1110 is the request to fix this).

**Verification command.** Get the pod name from the job, then read k8s events:

```bash
# Find the pod for the job
kubectl get pods -l buildkite.com/job-id=<job-id>

# Or for the build
kubectl get pods -l buildkite.com/build-id=<build-id>

# Read events filtered to that pod
kubectl get events --field-selector involvedObject.name=<pod-name>

# Or, broader, the namespace
kubectl get events --sort-by=.lastTimestamp -n buildkite
```

Common findings:

- `FailedScheduling` with insufficient memory / CPU on the cluster
- `ImagePullBackOff` on the agent or step container
- Pod-spec validation failure (PS-1250 Doordash hugepages pattern — viper lowercased a config key, k8s rejected the spec, agent-stack-k8s did not surface the rejection)
- OOMKilled before the agent could report — the pod is gone and the only record is the k8s event

**Hand off to.** **buildkite-agent-infrastructure** for the agent-stack-k8s configuration; A-1110 tracks the platform fix to surface these events in the UI.

## Diagnostic flow

```
Job failed without exit code or with -1
│
├── Has `agent_lost_at` / `agent_stopped_at` timestamp?
│   ├── Yes → Signature 1 (lost contact)
│   │         → Agent log around timestamp
│   │         → Other agents in queue affected? Yes = cluster event; No = host event
│   │
│   └── No  → Signature 3 (stalled with no events)
│             → kubectl get events --field-selector involvedObject.name=<pod>
│             → Look for FailedScheduling, ImagePullBackOff, OOMKilled
│
└── Agent log shows mid-job 401? → Signature 2 (token invalidation)
                                   → Compare job UUID in token vs BUILDKITE_JOB_ID
```

## What to record in Phase 5

Use the failure category from `failure-attribution-decision-tree.md`:

```bash
# Signature 1
buildkite-agent meta-data set "failure-reason" "infra-agent-disconnect"
buildkite-agent annotate --style "error" --context "root-cause" \
  "Agent \`i-0abc\` lost contact at 14:02Z mid-job. Other agents in queue \`docker-large\` unaffected — likely host-specific. Datadog: <link>."

# Signature 2
buildkite-agent meta-data set "failure-reason" "infra-agent-token"

# Signature 3
buildkite-agent meta-data set "failure-reason" "infra-scheduler"
buildkite-agent annotate --style "error" --context "root-cause" \
  "Pod \`agent-xyz\` rejected by scheduler: insufficient memory. \`kubectl get events\` output attached."
```

## Cross-references

- For agent installation, configuration, and queue sizing, see the **buildkite-agent-infrastructure** skill.
- For the in-job `buildkite-agent` commands used by Phase 5 (Record), see the **buildkite-agent-runtime** skill.
- For the broader failure-attribution table this reference feeds into, see `failure-attribution-decision-tree.md`.
