# `buildkite-agent-infrastructure` evals

Pass criterion for every case: the `buildkite-agent-infrastructure` skill loads, the correct phase is invoked, and the response names the specific gotcha or rule cited in the expected behaviour. Prompts mirror real Linear escalation / Plain-thread phrasing.

## Positive cases

| # | User prompt | Expected skill behaviour | Pass signal |
|---|---|---|---|
| 1 | "Our pre-command hooks stopped running after we upgraded `buildkite-agent` to 3.106.0 inside agent-stack-k8s command containers." | Skill loads. Identifies the `localHookPath` regression. Recommends pinning agent ≤3.105.x OR upgrading the controller to the fixed version. Points at the Phase 3 gotcha table. | Response names `localHookPath` and recommends a version pin. |
| 2 | "The stack rejects our pod spec because `hugepages-2mi` isn't a recognized resource." | Skill loads. Explains the viper-lowercasing bug. Recommends setting hugepage resources via the `kubernetes` plugin's `podSpecPatch`, which bypasses the viper key transform. | Response names viper or "key transform"; includes a `podSpecPatch` YAML example with `hugepages-2Mi` correctly cased. |
| 3 | "Stalled jobs in our k8s queue show no useful failure message — how do we figure out why?" | Skill loads. Routes to Phase 6 observability plus Phase 3 row on missing K8s events. Recommends cross-referencing `kubectl get events --sort-by='.lastTimestamp'` against the Buildkite job ID. Points at `scripts/agent-stack-k8s-diagnose.sh`. | Response suggests correlating K8s events with the build/job ID. |
| 4 | "We keep falling back from agent-stack-k8s to EC2. What's the migration path?" | Skill loads. Routes to Phase 7. Recommends parallel-run + per-queue cutover. Flags hook parity as ~25% of effort and the most common stall point. | Response names Phase 7.3 (hook parity); recommends queue-by-queue cutover. |
| 5 | "We're at ~10,000 builds/day. How should we size our queues?" | Skill loads. Routes to Phase 2 sizing table. Recommends per-workload queues. Points at `references/queue-design-patterns.md` for Little's-Law-based sizing. | Response cites the 10k row of the sizing table and the per-workload split. |
| 6 | "Our agents keep disconnecting from the default-queue, no clear error in logs." | Skill loads. Runs the Phase 5 disconnect triage table. First checks MTU / NAT keepalive; second checks Datadog `agent.heartbeat` correlated with VPC flow logs by agent ID. | Response names MTU / NAT keepalive first; mentions correlating heartbeat against VPC flow logs. |
| 7 | "We're seeing `401 invalid job uuid in job token` errors mid-build." | Skill loads. Phase 5 triage. First check: agent host clock skew. Second check: server-side token rotation event during the job. | Response names clock skew. |
| 8 | "Our build-dir suddenly changed after we upgraded the agent-stack-k8s chart from 0.29 to 0.30.1." | Skill loads. Phase 3 row for chart workspace-volume layout change. Recommends pinning the chart and setting `workspaceVolume` explicitly. | Response names `workspaceVolume` or "chart pin" / pinned chart version. |
| 9 | "How do we apply `image-pull-policy: Always` to all containers in agent-stack-k8s, not just command?" | Skill loads. Phase 3 row. Explains that controller-level config covers only command containers. Provides a `podSpecPatch` example covering `agent`, `checkout`, and `imagecheck-*` containers. | Response identifies the default-only-command behaviour and gives a per-container `podSpecPatch`. |
| 10 | "Should we use Elastic CI Stack or agent-stack-k8s for our new cluster?" | Skill loads. Quick Start decision tree + Phase 1 trade-off table. Gates `agent-stack-k8s` recommendation on the presence of K8s operators on call. | Response asks about (or surfaces) K8s operator presence before recommending the stack. |
| 11 | "We want to rotate our agent tokens. What's the safe pattern?" | Skill loads. Phase 5 token rotation rules. Recommends cluster tokens (not unclustered), 90-day rotation cadence, never embedding in AMIs/images, injecting from secret store. | Response names cluster tokens, the 90-day cadence, and external secret injection. |
| 12 | "Pre-command hooks work in our EC2 fleet but not in our agent-stack-k8s queue. Why?" | Skill loads. Phase 4 hook execution differences. Explains separate-container execution: env vars from checkout do not flow into command containers; the `environment` hook runs once per container. Points at `references/ec2-to-k8s-migration.md`. | Response explains checkout vs command run in separate containers; recommends pipeline-level `env:` or workspace files for cross-phase values. |

## Negative cases (should NOT trigger this skill)

| Prompt | Correct skill |
|---|---|
| "Add an annotation from inside my test step" | `buildkite-agent-runtime` |
| "Write a pipeline.yml that splits tests across 4 agents" | `buildkite-pipelines` |
| "Convert this Jenkinsfile to a Buildkite pipeline" | `buildkite-migration` |
| "Page me when a build fails" | `buildkite-api` (webhook setup) |
| "Run `bk build create --branch main`" | `buildkite-cli` |
| "Set up pipeline signing with OIDC" | `buildkite-secure-delivery` (planned) |

## Notes on real-world phrasing

Cases 1, 2, 3, 8, 9 use the exact issue-title phrasing observed in Linear escalations from Mistral.ai, Doordash, Dropbox, Equilibrium Energy, and Meta respectively. Cases 6 and 7 reflect Boston Dynamics (Sev 7) and FlyZipline (Sev 3) escalations. Case 4 reflects the recurring "we keep falling back" framing observed in Plain support threads.

When updating these evals, retain the verbatim escalation phrasing — agents are likely to encounter the same shorthand from operators reporting similar issues.
