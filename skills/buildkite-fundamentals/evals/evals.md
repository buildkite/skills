# buildkite-fundamentals evaluation set

Twelve cases. Nine should activate this skill; two should explicitly *not* activate (over-trigger guards routed to deeper skills); one activates briefly then hands off. Activation rate target: 9 of 12 (75%).

| Case ID | Trigger prompt | Expected activation | Expected behavior | Source |
|---|---|---|---|---|
| F-01 | "What's the difference between a build and a job in Buildkite?" | activates | Returns the build hierarchy: pipeline -> build -> step -> job, with the one-step-many-jobs note. References `build-hierarchy.md`. | structural (foundational) |
| F-02 | "We're seeing webhook build.finished arrive while jobs still say running. What's going on?" | activates, then hands off | Explains webhooks are eventually consistent; the API is the source of truth. Points at **buildkite-api** for payload details. | 01-linear.md theme #4 (Spotify) |
| F-03 | "Should I use the MCP server or the REST API to read build state from my agent?" | activates, then hands off | Returns the surface map decision rule: AI agents prefer MCP. Points at **buildkite-api**. References `surface-map.md`. | 01-linear.md theme #2 (Airtable / Wayfair MCP) |
| F-04 | "How do I write a pipeline that runs tests only for changed services?" | does NOT activate; routes to **buildkite-pipelines** | n/a — operational depth (`if_changed`, dynamic generation) is owned by **buildkite-pipelines**. | structural (over-trigger guard) |
| F-05 | "What is an OIDC subject in Buildkite?" | activates | Returns the canonical subject string format and points at `oidc-subject-format.md` and **buildkite-secure-delivery**. | structural (foundational) |
| F-06 | "Is a queue the same as a cluster?" | activates | Explains containment: organization contains clusters; cluster contains queues; queue contains agents. Points at **buildkite-agent-infrastructure**. | 01-linear.md theme #3 (Hosted Agents namespace) |
| F-07 | "We need a failure_reason field — is that infra or test failure?" | activates briefly, then hands off | Explains build state vs job state vs outcome and the infra-versus-test distinction. Points at **buildkite-build-investigation**. | 01-linear.md theme #9 (Anthropic PF-9400) |
| F-08 | "buildkite-agent annotate isn't found — what's wrong?" | activates, then hands off | Explains `buildkite-agent` only runs inside a job (needs `BUILDKITE_AGENT_ACCESS_TOKEN`). Points at **buildkite-agent-runtime** for the in-job API and **buildkite-cli** for the laptop equivalent. | structural (surface-map over-trigger guard) |
| F-09 | "What's a hook in Buildkite, exactly?" | activates | Names the hook concept and the lifecycle positions (`environment`, `pre-checkout`, `checkout`, `post-checkout`, `pre-command`, `command`, `post-command`, `pre-exit`). References `hooks-lifecycle.md`. | 01-linear.md theme #1 (k8s hook resolution, Mistral.ai PS-1200) |
| F-10 | "Should we go with Buildkite hosted agents or self-host?" | activates | Returns the hosted-vs-self-hosted decision table; notes the hybrid control-plane architecture. Points at **buildkite-agent-infrastructure**. | 01-linear.md theme #3 |
| F-11 | "Can I trigger a build with bk or do I need to call the API?" | activates, then hands off | Surface map: `bk` is the developer-laptop surface, REST is the resource API. Points at **buildkite-cli** and **buildkite-api**. | structural (surface-map foundational) |
| F-12 | "We're hitting matrix limit issues — what's the cap and why?" | does NOT activate; routes to **buildkite-pipelines** | n/a — matrix limits and adjustments are pipeline-authoring depth, owned by **buildkite-pipelines**. | 01-linear.md theme #8 (Iress, NIB) — over-trigger guard |

## Over-trigger guards

F-04 and F-12 are the explicit "do not activate" cases. They look superficially like Buildkite orientation questions, but each asks for operational depth owned by a sibling skill. If fundamentals activates on either, the skill is over-triggering and the trigger phrases in the description need narrowing toward "what is X" rather than "how do I do X".

## Activation rate

- Activate: F-01, F-02, F-03, F-05, F-06, F-07, F-08, F-09, F-10, F-11 = 10 of 12
- Do not activate: F-04, F-12 = 2 of 12

Note: F-07 activates briefly then hands off — counted as activation for this rate calculation. The spec's 9-of-12 figure treats F-07 as borderline; either reading is acceptable.
