# Eval set — buildkite-build-investigation

Ten evaluation cases. Each grounds in a real Linear escalation or a named pain theme so the expected behaviour can be checked against actual customer phrasing. The phrasing in the **Trigger prompt** column quotes the original report where the original is from Linear; do not paraphrase quotes.

Each case lists: the trigger prompt the user might enter, the expected first workflow phase, the expected reference / sibling skill the agent should hand off to, and a pass criterion the evaluator scores against.

| # | Anchor | Trigger prompt | Expected first phase | Expected hand-off | Pass criterion |
|---|---|---|---|---|---|
| 1 | PS-1300 (Spotify) | "Our `build.finished` webhook is firing with `state: running`. What's going on? Possible race condition between `build.finished` events." | Phase 3 (Correlate) | `references/webhook-state-traps.md` → **buildkite-api** | Agent invokes the verify-via-`get_build` rule, names the PS-1300 pattern as state-staleness, does not advise treating the webhook payload as authoritative |
| 2 | PS-555 (8-customer cohort) | "Search in the job log viewer is completely broken for our builds — no matches for strings I can see in the streamed log." | Phase 2 (Localize) | `references/log-search-patterns.md` (API-side workarounds) | Agent recognises the known regression cohort, switches to `bk job log \| grep` or REST-side log fetch, does not loop the user through more UI search attempts |
| 3 | PS-1600 (Anthropic Sev 5) | "The build page takes 30+ seconds to load and my browser CPU is pegged at 100%. The build has hundreds of jobs." | Phase 1 (Orient) | `references/log-search-patterns.md` (UI-too-slow override) | Agent abandons the UI immediately, switches to `bk` or MCP `get_build`, does not suggest refreshing the page or trying another browser |
| 4 | A-1110 (Dropbox) | "Our jobs in agent-stack-k8s stall but the failure message doesn't include the relevant Kubernetes events. How do I debug it?" | Phase 2 (Localize) | `references/agent-disconnect-diagnostics.md` → **buildkite-agent-infrastructure** | Agent runs the missing-events recipe: `kubectl get events --field-selector involvedObject.name=<pod>`, identifies the gap as A-1110 (platform issue, not user config) |
| 5 | PS-500 (Boston Dynamics Sev 7) | "Our agents in the default queue keep disconnecting mid-job. Datadog traces aren't helpful." | Phase 2 (Localize) | `references/agent-disconnect-diagnostics.md` → Phase 3 (Correlate) → **buildkite-agent-infrastructure** | Agent identifies "agent lost contact" as Signature 1, asks whether other agents in queue affected at same time (cluster vs host signal), does not jump to "test failure" hypothesis |
| 6 | PF-9400 (Anthropic) | "Was this build failure infrastructure or a test failure? I need a `failure_reason` field." | Phase 1 (Orient) → Failure-Attribution Decision Table | `references/failure-attribution-decision-tree.md`; downstream depends on category | Agent walks the decision table (starting from exit code + log signature), produces a category from the vocabulary (`infra-oom`, `test-real`, etc.), records it via `meta-data set failure-reason` |
| 7 | PS-505 (Airtable Sev 6) | "This build has been running for five hours. The pipeline finished but the build never went terminal." | Phase 3 (Correlate) | `references/webhook-state-traps.md` → **buildkite-api** | Agent verifies via REST `get_build`, identifies the PS-505 ghost-build signature (all jobs finished, build state still `running`), recommends platform escalation rather than user-side fix |
| 8 | PS-1200 (Mistral) | "Builds started failing yesterday after we upgraded to agent 3.106 — repository pre-command hooks aren't running." | Phase 3 (Correlate) | **buildkite-agent-infrastructure**; Phase 4 verification by pinning to older agent | Agent identifies the agent-version rollout as the correlation, classifies as `regression-rollout` (specifically `regression-hook-path` per decision tree), proposes Phase 4 verification by running an older agent version |
| 9 | PS-1250 (Doordash) | "Our pods are being rejected by Kubernetes after upgrading the agent stack. Logs are empty." | Phase 2 (Localize) → Phase 4 (Verify) | `references/agent-disconnect-diagnostics.md` → **buildkite-agent-infrastructure** | Agent recognises the empty-log signature (Signature 3, stalled with no exit code), runs `kubectl get events` as the verification step, identifies the pod-spec rejection — does not read the empty log repeatedly |
| 10 | Generic flake / Stay on the Path | "This test failed in CI but passes locally. Probably flaky?" | Phase 1 (Orient) — triggered by the "I already know this pipeline is flaky" override | **buildkite-preflight** for repro; future **buildkite-test-engine** | Agent applies the `## Stay on the Path` override (flaky is a hypothesis, not a finding), runs Phase 1 to confirm cohort, runs Phase 4 before labelling, does not accept "probably flaky" at face value |

## Scoring notes

- Cases 1, 7 share the webhook-state-traps reference. The discriminator is severity and the action: case 1 is a recurring race (consumer-side fix), case 7 is a stuck build (platform escalation). Both fail if the agent treats the webhook payload as authoritative.
- Case 6 is the broadest: it tests whether the agent uses the failure-attribution decision table at all. The category vocabulary must come from `failure-attribution-decision-tree.md`, not from the agent's training.
- Case 10 is the Stay-on-the-Path guardrail. It fails if the agent agrees "probably flaky" and proceeds without running Phase 1 or Phase 4 first.
- Cases 3 (UI perf) and 4 (missing K8s events) are tests that the agent recognises platform-side known issues and routes around them rather than asking the user to debug them.
- Cases 5 and 8 both involve agent-infrastructure hand-offs but differ in the Phase: 5 hands off after Phase 2 (signature is enough), 8 hands off after Phase 3 (correlation to rollout is the key).

## How to run

This file is the eval spec, not an automated harness. The skills-internal-tools repo (referenced in `/Users/simone/skills/CLAUDE.md`) is where the eval harness lives. To run this set:

1. Configure the agent under test with the `buildkite-build-investigation` skill loaded.
2. For each row, present the **Trigger prompt** verbatim.
3. Inspect the agent's first three actions against **Expected first phase** and **Expected hand-off**.
4. Score against **Pass criterion**.
5. Aggregate pass rate; target ≥ 9 of 10 for shipping the skill.
