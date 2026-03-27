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
**Fix applied:** Updated platform-engineering skill to recommend hosted agents first, added `pipelineCreate` with `clusterId`, rewrote PROMPT.md to be task-focused.

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
