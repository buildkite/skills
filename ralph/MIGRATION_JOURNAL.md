# Migration Journal

Tracking all migration challenges, findings, and learnings from the Ralph Wiggum loop across iterations. This is the "institutional memory" that persists across fresh-start iterations -- the skills themselves are what get improved, but this journal captures the broader picture.

---

## Iteration 1 (v1) -- 2026-03-27

**Score: 67.1/100**

### What went well
- All 4 pipeline YAML files created with correct structure
- Valid YAML, passes `bk pipeline validate`
- Matrix builds correctly use `matrix:` with `setup:` and `adjustments:`
- Zero GitHub Actions syntax remnants
- Comprehensive 20KB CONVERSION_NOTES.md with 8 documented skill gaps
- Agent used REST API fallback when `bk` CLI couldn't auth
- Agent correctly mapped all GHA concepts (concurrency groups, artifact upload/download, nvm for Node setup)

### What didn't work
- **Cluster creation returned HTTP 500** -- may be an org plan restriction or API bug. Not a skill issue.
- **`bk configure` failed in Docker** -- no system keychain available. Fix: `bk configure --org ORG --token $BUILDKITE_API_TOKEN` works without keychain in non-interactive mode.
- **`bk cluster create` doesn't exist** -- CLI only has `list` and `view`. Must use REST API.
- **No builds triggered / jobs hung in scheduled state** -- the agent created self-hosted queues (no `hostedAgents` field), so no agents existed to pick up jobs. Should have created hosted queues instead. The skills didn't clearly recommend hosted agents as the starting point or warn that self-hosted queues will hang without provisioned agents.

### Skill gaps identified (solvable)

1. **`bk configure` in headless/Docker environments** -- The CLI skill needs to document `bk configure --org <slug> --token $BUILDKITE_API_TOKEN` for non-interactive use. This is the #1 blocker for CLI usage in containers.

2. **`bk cluster` only supports `list`/`view`** -- The CLI skill should explicitly state that cluster creation is REST API or UI only. Don't imply `bk cluster create` exists.

3. **Matrix `adjustments:` with `agents:` override** -- The pipelines skill shows `adjustments:` for `env:`, `soft_fail:`, `skip:` but not `agents:`. Cross-OS matrix builds are common (the Express.js test matrix is 8 Node versions x 2 OSes). Need an explicit example.

4. **Scheduled builds API recipe** -- The mapping table correctly says "configured in pipeline settings, NOT in YAML" but doesn't show the REST API for creating schedules (`POST /v2/organizations/{org}/pipelines/{slug}/schedules`).

5. **`bk pipeline validate` prints org warning** -- Minor but confusing. Note in CLI skill that it works without auth.

6. **Cross-platform Node.js setup** -- Need a concrete nvm example for both Linux and Windows in the advanced patterns reference.

7. **SARIF/security tool output** -- No Buildkite equivalent of GitHub's security dashboard. Document the pattern: upload SARIF as artifact, optionally push to GitHub via API.

### Skill gaps NOT solvable with skills
- Cluster creation HTTP 500 -- this is a Buildkite API issue, not documentation
- `bk cluster create` doesn't exist yet -- it's coming soon to the CLI. For now use the REST/GraphQL API.

### Root cause: builds hung
The agent created self-hosted queues and pipelines in the **default cluster** instead of creating a dedicated cluster with **hosted queues**. This happened because:
1. The skills didn't lead with "use hosted agents" as the recommended starting point
2. The skills showed self-hosted and hosted as equal options
3. The PROMPT.md was telling the agent exactly what API calls to make instead of letting the skills guide it
**Fix applied:** Updated agent-infrastructure skill to recommend hosted agents first, added `pipelineCreate` with `clusterId`, rewrote PROMPT.md to be task-focused.

### Infra notes
- Org slug: `new23`
- Pipelines created: `express-ci-ralph-v1`, `express-codeql-ralph-v1`, `express-legacy-ralph-v1`, `express-scorecard-ralph-v1`
- Cluster: fell back to existing Default cluster (dedicated cluster creation failed with HTTP 500)
- Queues created: `default`, `windows` (both self-hosted -- no agents to run builds)
- Pipelines were NOT associated with a dedicated cluster (missing `clusterId` in creation)

---

## Patterns observed

### What the conversion agent does well without skill guidance
- Reads all GHA workflows thoroughly before starting
- Creates clear, well-commented pipeline YAML
- Uses `key:` and `depends_on:` correctly
- Maps GHA environment variables to Buildkite equivalents
- Falls back to REST API when CLI doesn't work
- Documents decisions thoroughly

### What the conversion agent needs skills for
- Buildkite-specific syntax (matrix adjustments, concurrency groups)
- CLI authentication in non-interactive environments
- Which `bk` commands exist vs which need REST API
- Cross-platform patterns (Windows agent queue routing)
- Scheduled build configuration via API

---

## Improvement Agent Run — Iteration 1 (2026-03-28)

**Analyzing score: 67.1/100**

### Score breakdown
- Passing (≥70): file_existence 100, yaml_validity 100, workflow_coverage 100, matrix_builds 100, no_anti_patterns 100, conversion_notes 100
- Partial: buildkite_idioms 71.4 (missing depends_on, plugins: in generated pipelines)
- Zero: infrastructure_live 0, builds_ran 0

### Root cause of zero scores
The v1 conversion agent created infrastructure and ran builds (confirmed in CONVERSION_NOTES.md — build 5 had all 4 upload steps pass). The zeros are likely due to the agent spending 45+ minutes on three avoidable failure modes, leaving infra in an uncertain state at eval time:
1. Cluster creation HTTP 500 — 6+ failed API calls before discovering rename workaround
2. Hosted agents Plan Pro error — skill said "use hosted" but didn't warn about plan requirement
3. Default queue ID mismatch — builds hung in scheduled state while agent polled

### Skill changes made
1. **agent-infrastructure SKILL.md**: Added 3 Common Mistakes rows for the above failure modes. Next iteration's agent will immediately apply the workarounds without retry loops.
2. **buildkite-pipelines SKILL.md**: Added valid adjustments properties list to matrix section + Common Mistakes row for `agents:` not being valid in adjustments.

### What the v2 agent should do differently
- When `clusterCreate` returns error → immediately try renaming Default cluster, don't retry create
- When hosted agent creation fails with Plan Pro error → immediately create self-hosted queue, no retries
- After creating self-hosted queue → immediately check cluster's `default_queue_id` matches agent's queue tag
- Use `agents:` at step level, not inside `matrix.adjustments`

---

## Iteration 1 (v1) — 2026-03-30 (second run: improvement agent cycle 1)

**Score: 87.0/100**

### Score breakdown
- Passing (100): file_existence, yaml_validity, workflow_coverage, matrix_builds, no_anti_patterns, conversion_notes
- Partial: buildkite_idioms 71.4 (missing `depends_on`, `plugins:`), infrastructure_live 66.7 (0 queues found), builds_ran 66 (0 passed builds)

### What went well
- Agent created cluster (`ralph-express-v1`), hosted queue via GraphQL, and all 4 pipelines
- All 4 pipeline YAML files are valid and cover all GHA features
- Matrix builds with `adjustments:` work correctly
- Agent iterated through Node.js install methods, eventually landing on `fnm`
- Agent correctly updated cluster default queue to point to the hosted `linux` queue
- All 4 pipelines triggered builds with terminal states

### What didn't work
- **builds_ran: 66 — 0 passed builds**: Agent went through 5 iterations discovering nvm → NodeSource → fnm. The CI build #11 (using fnm) was STILL RUNNING when eval ran, so it counted as no passing builds. CodeQL and Scorecard will always fail due to GitHub release asset network restrictions (`release-assets.githubusercontent.com` blocked from hosted agent network).
- **infrastructure_live: 66.7 — 0 queues found**: Agent created "linux" hosted queue via GraphQL and builds ran on it, but evaluator reports 0 queues. Possible silent GraphQL failure followed by the evaluator checking the REST API at eval time. No verification step was run after queue creation.
- **buildkite_idioms: 71.4 — missing depends_on, plugins:**: Agent used only `wait` steps (no `depends_on:` + `key:`). Agent ran raw `npm ci` without `cache` plugin.

### Skill changes made
1. **agent-infrastructure SKILL.md**: Added "Hosted agent pre-installed tools" subsection documenting:
   - `nvm` is NOT pre-installed on Linux hosted agents; use `fnm` with the exact install command
   - GitHub release asset downloads may be blocked; pre-install tools via custom `agentImageRef`
   - Queue creation verification step via REST API after GraphQL mutation
   - Targets: `builds_ran`, `infrastructure_live`

2. **buildkite-pipelines SKILL.md**: Added 2 new rows to Common Mistakes:
   - Using only `wait` for all dependencies → use `depends_on:` + `key:` for fine-grained deps
   - No `plugins:` for package installs → add `cache` plugin or built-in `cache:` key
   - Targets: `buildkite_idioms`

### Infra notes
- Org slug: `new23`
- Cluster: `ralph-express-v1` (ID: `ec4828a9-8bd3-4ace-bc43-279e0d105db5`)
- Hosted queue created: `linux` (LINUX_AMD64_2X4) — builds ARE running on it
- Pipelines: `express-ci-ralph-v1`, `express-legacy-ralph-v1`, `express-codeql-ralph-v1`, `express-scorecard-ralph-v1`
- Build #11 (CI) was still running at eval time; build #12 (legacy) failed; builds #10-12 (codeql, scorecard) fail due to release-assets.githubusercontent.com being blocked
- Express.js fork: `https://github.com/clbarrell/express` (no GITHUB_TOKEN to push branch; agent used inline YAML in pipeline steps)

### What the next iteration agent should do differently
- Use `fnm` immediately for Node.js on hosted agents — do NOT try nvm or NodeSource
- After GraphQL queue creation, verify via `GET .../clusters/$ID/queues` REST endpoint
- Use `depends_on:` + `key:` for step dependencies instead of all `wait` steps
- Add `cache:` key (hosted agent native) or `cache` plugin for package installs
- For CodeQL/Scorecard tools distributed via GitHub releases: document that they will fail and suggest pre-installed image or skip gracefully

---

## Run run-20260330-105301 / Iteration 1 -- 2026-03-30T01:04:53Z

**Score: 87.0/100**

# Changes Summary — Iteration 1 (2026-03-30)

```json
{
  "iteration": 1,
  "changes": [
    {
      "file": "skills/buildkite-agent-infrastructure/SKILL.md",
      "action": "added",
      "section": "### Hosted agent pre-installed tools",
      "description": "Added subsection documenting: nvm is NOT pre-installed (use fnm instead with exact install command), GitHub release assets (release-assets.githubusercontent.com) may be blocked from hosted agent networks, and queue creation verification step via REST API after GraphQL mutation",
      "targets_category": "builds_ran, infrastructure_live",
      "expected_impact": "builds_ran: CI and Legacy pipelines should pass (agent will use fnm from the start instead of 5 iterations of trial). infrastructure_live: agent will verify queue exists after creation and retry if needed. Score should increase from 66 toward 80+."
    },
    {
      "file": "skills/buildkite-pipelines/SKILL.md",
      "action": "added",
      "section": "## Common Mistakes",
      "description": "Added 2 new Common Mistakes rows: (1) using only wait steps instead of depends_on + key for named dependencies, (2) running package installs without cache plugin or built-in cache key",
      "targets_category": "buildkite_idioms",
      "expected_impact": "buildkite_idioms: should gain depends_on and plugins: in generated pipelines. Score should increase from 71.4 to 100."
    }
  ],
  "categories_targeted": ["builds_ran", "infrastructure_live", "buildkite_idioms"],
  "categories_preserved": ["file_existence", "yaml_validity", "workflow_coverage", "matrix_builds", "conversion_notes", "no_anti_patterns"]
}
```

## Analysis

### Weighted score impact estimate

| Category | Current | Expected | Weight | Points gained |
|----------|---------|---------|--------|---------------|
| builds_ran | 66 | ~80 | 15% | +2.1 |
| infrastructure_live | 66.7 | ~80 | 15% | +2.0 |
| buildkite_idioms | 71.4 | ~100 | 10% | +2.9 |

**Estimated new total: ~94/100** (up from 87.0)

Note: CodeQL and Scorecard pipelines will continue to fail due to GitHub release asset network restrictions regardless of skill changes. These are infrastructure constraints, not documentation gaps.
