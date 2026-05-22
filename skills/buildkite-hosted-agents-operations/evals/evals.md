# `buildkite-hosted-agents-operations` evals

Pass criterion for every case: the `buildkite-hosted-agents-operations` skill loads, the correct section is invoked, and the response names the specific gotcha or rule cited in the expected behaviour. Prompts mirror real Linear escalation and Plain-thread phrasing.

## Positive cases

| # | User prompt | Expected skill behaviour | Pass signal |
|---|---|---|---|
| 1 | "We're trying to update our hosted agent image — Groq is being asked to copy-paste a Dockerfile into the UI to update auth bootstrap. There has to be a better way." | Skill loads. Routes to the Image Lifecycle section mode 3 (internal container registry + Image URL). Cites the A-500 pattern. Surfaces `scripts/hosted-image-build-and-push.sh`. | Response names `BUILDKITE_HOSTED_REGISTRY_URL` and the queue's **Image URL** setting. Flags `agentImageRef` as private preview and internal container registry as Enterprise-only. |
| 2 | "We're seeing a spike in errors from Namespace on our 11x.ai cluster — builds failing, no useful error in the pipeline log." | Skill loads. Routes to the Namespace Integration section namespace.so escalation playbook. Instructs the user to gather the timestamp window and escalate to `support@buildkite.com`. Does not invent a fix. | Response identifies that namespace.so errors surface only in the operational/admin UI; recommends support escalation; flags the limitation honestly. |
| 3 | "Our iOS team just upgraded to Xcode 26 — fastlane build broke with `bundler: failed to load command: fastlane`, missing mutex_m." | Skill loads. Routes to the macOS Hosted Agents section fastlane Ruby gem dependency error. Recommends adding `gem 'mutex_m'`, `gem 'ostruct'`, `gem 'abbrev'` to the `Gemfile`. | Response names the three gems; explains Ruby 3.4+ default-gem removal; routes to `references/macos-build-gotchas.md`. |
| 4 | "Code signing failing on macOS hosted — exit 65, fastlane reports CodeSign error. We're hand-rolling certs." | Skill loads. Routes to the macOS Hosted Agents section code-signing decision table. Recommends switching to `fastlane match`. Suggests `security find-identity -v -p codesigning` via terminal access. | Response names `fastlane match` and the diagnostic command. |
| 5 | "Should we enable container cache volumes for our Node monorepo, or push to the internal container registry?" | Skill loads. Routes to the Cache Volumes section and `references/cache-volume-sizing.md`. Cache volumes for `node_modules`; registry only for OCI images needed deterministically. | Response names the deterministic-vs-non-deterministic distinction; cites 14-day retention. |
| 6 | "What IPs do our hosted agents come from? Our security team wants an allowlist." | Skill loads. Routes to the Network Security section. IP ranges visible per queue under **Networking → Network Ranges**; flags the non-static caveat; recommends OIDC where possible. | Response names the **Networking** page; states ranges may shift; recommends OIDC. |
| 7 | "Our hosted Linux build succeeds locally but fails to start on hosted — agent never connects." | Skill loads. Routes to the Image Lifecycle section and the "Issues with starting a job" decoder. First check is `ca-certificates` in the custom image. | Response names `ca-certificates`; also lists `git` and `bash` as required tools. |
| 8 | "How do I open a terminal on a hosted agent to debug?" | Skill loads. Routes to the Terminal Access section. Explains permission requirements (build perms / cluster maintainer / org admin). Recommends `sleep 600` to extend the session. Flags org-admin disable toggle. | Response names the **Open Terminal** button and the `sleep` extension pattern. |
| 9 | "Our concurrency on hosted Linux feels wrong — we have 48 vCPU on our plan but only get 6 agents at once." | Skill loads. Routes to the Namespace Integration section concurrency arithmetic. Identifies the queue is on Large (`LINUX_AMD64_8X32`, 8 vCPU), so 48 / 8 = 6 is correct. Suggests smaller shape if more concurrency is wanted. | Response computes the arithmetic and identifies instance shape as the lever. |
| 10 | "Mounting a cache volume at `/tmp` on macOS hosted isn't working." | Skill loads. Routes to the macOS Hosted Agents section reserved-path trap. Recommends mounting `/tmp/volume` instead. | Response names `/tmp` and `/private` as reserved; recommends sub-path mount. |
| 11 | "We need to migrate this self-hosted pipeline to hosted agents — what changes in the repo settings?" | Skill loads. Routes to the Network Security section code-access sub-paragraph and the `pipeline_migration.md` cite. Flags HTTPS-checkout requirement. For non-GitHub providers, names the `git-ssh-checkout` plugin plus a cluster secret. | Response names the HTTPS-checkout switch in pipeline settings; for non-GitHub, names `git-ssh-checkout` plugin. |
| 12 | "Are remote Docker builders making our build slower for tiny images?" | Skill loads. Routes to the Cost, Billing, and Plan Gating section and Common Mistakes. Explains Enterprise default and disable pattern (`DOCKER_BUILDKIT=0` or `docker buildx use default`). Recommends measuring before disabling. | Response names `DOCKER_BUILDKIT=0` or `docker buildx use default`. |

## Negative cases (should NOT trigger this skill)

| Prompt | Correct skill |
|---|---|
| "Choose between Elastic CI Stack and agent-stack-k8s for our new cluster" | `buildkite-agent-infrastructure` |
| "Write a pipeline.yml that targets a hosted Linux queue with caching" | `buildkite-pipelines` (YAML authoring) |
| "Add an annotation from inside my hosted Mac test step" | `buildkite-agent-runtime` |
| "Set up OIDC federation to AWS from hosted agents" | `buildkite-secure-delivery` (planned) — this skill only points at OIDC; depth is owned elsewhere |
