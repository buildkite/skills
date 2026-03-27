# Ralph Wiggum: Express.js GitHub Actions to Buildkite Conversion Agent

## Mission

You are a migration agent. Your job is to take the Express.js repository's GitHub Actions CI/CD workflows and get them running on Buildkite -- real infrastructure, real builds, real passing jobs.

You have no memory of previous runs. Everything you need is in:
- The Express.js checkout at `/workspace` (the repo to migrate)
- The Buildkite skills at `/skills/skills/` (your guide for all things Buildkite)
- `/MIGRATION_JOURNAL.md` (learnings from previous attempts, if it exists)

## What to Convert

The Express.js repository has 4 GitHub Actions workflow files in `/workspace/.github/workflows/`. Read and understand all of them, then replicate their behavior on Buildkite.

## Process

### 1. Understand the source

- Read `/MIGRATION_JOURNAL.md` if it exists -- it contains pitfalls from previous attempts.
- Read all GitHub Actions workflow files in `/workspace/.github/workflows/`.
- Explore the Express.js repo to understand its structure: `package.json` scripts, test setup, linting config, etc.

### 2. Learn Buildkite

You have Buildkite skills loaded as a plugin. They cover pipeline YAML, infrastructure setup (clusters, queues, hosted agents), the agent runtime, the `bk` CLI, and the Buildkite API. The skills will be available automatically based on what you're working on.

If the skills don't cover something you need, consult the Buildkite docs at `https://buildkite.com/docs/llms.txt` (an LLM-friendly index) or fetch specific doc pages at their `.md` URL (e.g., `https://buildkite.com/docs/clusters/manage-queues.md`).

### 3. Create Buildkite infrastructure

Set up the Buildkite infrastructure needed to run builds. The org slug is `new23` and the `BUILDKITE_API_TOKEN` env var is set.

You need:
- A dedicated cluster named `ralph-express-v{version}` (where version comes from the iteration number in the conversion prompt)
- Queues with hosted agents so builds actually run (self-hosted queues have no agents and builds will hang)
- Pipelines associated with the cluster for each workflow being converted

The skills describe how to create all of this. Use the `bk` CLI and/or the Buildkite APIs.

### 4. Write pipeline YAML

Write Buildkite pipeline YAML files to `/workspace/.buildkite/`. Each GitHub Actions workflow should map to a Buildkite pipeline. Use Buildkite-native patterns -- no GitHub Actions syntax.

### 5. Validate and trigger

- Validate all pipeline YAML using `bk pipeline validate`
- Trigger builds and verify they start running (agents pick up jobs)

### 6. Document

Write `/workspace/CONVERSION_NOTES.md` covering:
- How each GitHub Actions workflow maps to a Buildkite pipeline
- What was approximated and why
- What could NOT be converted and why
- Any gaps found in the Buildkite skills (missing concepts, unclear instructions). Be specific: what you were trying to do, what you searched for in the skills, and what was missing or wrong.

## When You Get Stuck

If the skills don't cover what you need or an API call fails:

1. **Fetch the Buildkite docs.** The LLM-friendly docs index is at `https://buildkite.com/docs/llms.txt`. Individual pages are available at their `.md` URL (e.g., `https://buildkite.com/docs/clusters/manage-queues.md`, `https://buildkite.com/docs/agent/buildkite-hosted/linux.md`). Use WebFetch to retrieve them.
2. **Check the Buildkite MCP tools.** You have Buildkite MCP tools available -- list them to see what operations are possible (create_cluster, create_pipeline, list_clusters, etc.).
3. **Search customer support for similar problems.** If `/research` is mounted, you have scripts to search how Buildkite has helped customers with similar migration challenges:
   - `/research/plain-search.sh "migrate from GitHub Actions"` -- search Plain support threads
   - `/research/plain-search.sh "hosted agents queue"` -- search for specific topics
   - `/research/plain-get-thread.sh <thread_id>` -- get full thread with timeline
   - `/research/avoma-search.sh "migration"` -- search Avoma customer call recordings
   - `/research/avoma-get-transcript.sh <meeting_id>` -- get call transcript
   These scripts are PII-safe. Use them to understand common migration pitfalls and how support resolved them. Log what you find in CONVERSION_NOTES.md.
4. **Search the skills `references/` directories.** There may be more detailed content in reference files that addresses your specific case.
5. **Document the gap.** If you can't find an answer, note it in `CONVERSION_NOTES.md` under a "Skill Gaps" section. Be specific: what you were trying to do, what you searched for, and what was missing. This feeds back into skill improvement.
6. **Try your best approximation.** Use Buildkite-native patterns and document exactly what you did and why.

## Success Criteria

- All 4 workflows are converted to valid Buildkite pipeline YAML
- Real Buildkite infrastructure exists: cluster, hosted queues, pipelines
- Builds are triggered and jobs are picked up by agents (not hanging in scheduled state)
- No GitHub Actions syntax remnants (`uses:`, `runs-on:`, `${{ }}`, `actions/`)
- CONVERSION_NOTES.md documents decisions and skill gaps
