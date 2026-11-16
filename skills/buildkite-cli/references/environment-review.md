# Review a Buildkite Environment

Use settings and build history to recommend changes to Buildkite workflows, not compute sizing or compute costs. Keep observations separate from interpretations and proposed changes.

## Contents

- Establish scope and access
- Collect a bounded sample
- Check four areas
- Inspect configuration for a specific question
- Report findings and coverage

## Establish Scope and Access

Resolve the explicitly requested pipeline, otherwise use the checkout's pipeline only when unambiguous. Ask for the target if unresolved. Review multiple pipelines or the organization only when requested.

Default to the latest 50 builds per pipeline created within the preceding seven days. Freeze and report the UTC bounds, pipelines, actual build counts, and whether the cap truncated the window. This is a sample, not all builds in the period. Allow a user-requested window or limit instead.

Check the installed CLI and existing authentication without updating the CLI, logging in, switching organizations, or changing configuration. A review authorizes reads only: do not cancel/retry jobs, change settings, edit pipeline files, create schedules, run builds or generators, commit, or push. Use GET for REST and query operations for GraphQL. Do not print credentials or environment values returned by reads.

```bash
bk --version
bk api --help
bk build list --help
bk job list --help
bk auth status -o json | jq '{organization_slug, scopes: .token.scopes}'
```

Use authorized MCP read tools when available, as described in the main skill. Use structured CLI output or `bk api` when the tools omit required fields. Missing access makes a check incomplete; do not acquire broader access silently. Core REST reads require `read_pipelines` and `read_builds`, subject to pipeline visibility. GraphQL also requires its API-access permission.

> For API authentication, endpoint contracts, and pagination, see the **buildkite-api** skill.

## Collect a Bounded Sample

Read current pipeline settings, schedules, and lightweight build metadata first. Fetch complete job inventories only where needed for the checks. Current settings do not establish historical settings at build time. Retain source, PR context, and rebuild ancestry when comparing builds.

The examples below use Bash, Python 3, and jq. Replace the example pipeline/build with the resolved target. `bk api` prefixes REST paths with `/v2/organizations/{configured-org}`. Confirm that organization matches the target; do not pass full API URLs or an organization prefix as its endpoint.

```bash
set -euo pipefail
pipeline=my-app

# Project settings without printing configuration or environment values.
bk api "/pipelines/$pipeline" | jq '{
  slug, web_url, default_branch, branch_configuration,
  skip_queued_branch_builds, skip_queued_branch_builds_filter,
  cancel_running_branch_builds, cancel_running_branch_builds_filter
}'

# Freeze the seven-day creation window. Fetch one extra build to detect truncation.
read -r since until < <(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
end = datetime.now(timezone.utc).replace(microsecond=0)
print((end - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ'),
      end.strftime('%Y-%m-%dT%H:%M:%SZ'))
PY
)
builds=$(bk api "/pipelines/$pipeline/builds?created_from=$since&created_to=$until&per_page=51&exclude_jobs=true&exclude_pipeline=true")
printf '%s\n' "$builds" | jq --arg since "$since" --arg until "$until" '{
  window: {created_from: $since, created_to: $until},
  truncated: (length > 50),
  sample_count: (.[:50] | length),
  builds: [.[:50][] | {
    number, web_url, branch, commit, source, pull_request, rebuilt_from,
    state, created_at, scheduled_at, started_at, finished_at
  }]
}'
```

For a different window or cap, adjust the request and projection together. For samples beyond one page, use a client that exposes REST `Link` headers. `bk api` prints the body only and does not paginate. `bk build list --pipeline my-app --summary --since 168h --limit 51 -o json` is an alternative for a relative window; record its actual bounds and trim to 50. Do not infer completeness from a full page.

For a selected build, fetch jobs with `include_retried_jobs=true`, without state filters that would hide other attempts:

```bash
build=429
bk api "/pipelines/$pipeline/builds/$build/jobs?include_retried_jobs=true&per_page=100" |
  jq '{items: [.items[] | {
    id, web_url, type, state, step_key, matrix,
    parallel_group_index, parallel_group_total,
    retry_source, retry_type, retried_in_job_id, soft_failed,
    created_at, scheduled_at, started_at, finished_at, concurrency_wait_time_ms
  }], links}'
```

This reads one page, not a complete inventory. Follow `.links.next` until null and combine `.items`. Before passing a next URL to `bk api`, verify its origin and organization match the target, then remove only that API organization's prefix. Preserve the remaining path and query, including cursor and filters. Use the API skill's authenticated client approach when response headers are needed. For GraphQL, follow connection cursors and check operation errors as well as HTTP errors.

Mark unavailable fields, denied requests, and incomplete inventories explicitly. Missing data is not zero or proof of no problem. Use executable calculations for durations, overlaps, and rates; retain numerators, denominators, and exclusion reasons rather than estimating from JSON or logs.

## Check Four Areas

### 1. Obsolete Branch Builds

Compare the skip/cancel settings and their filters with overlapping lifetimes of different-commit builds on the same branch. Measure older-job execution after a newer build's creation only where timestamps support it. Separate completed durations from still-running observations; exclude missing timestamps rather than inventing them.

Suggest reviewing branch-scoped skip/cancel behavior only when observed overlap makes it relevant. A disabled setting alone is not a finding. Branch names and timestamps do not prove commit ancestry or that work is redundant. Confirm build purpose, PR context, rebuild ancestry, and whether every commit must run, especially for deployment/release pipelines. Label overlap as a candidate, not execution known to be unnecessary.

### 2. Retry Effectiveness

Reconstruct complete attempt chains from job IDs and retry links, including original attempts. Preserve step keys, matrix values, and parallel coordinates when grouping across builds; leave ambiguous identities unmatched. Separate automatic and manual retries, including mixed chains. Exclude canceled, missing-attempt, and unfinished chains from completed recovery rates, and report those exclusions.

Report recovered versus completed eligible chains and the summed execution duration of retry attempts with both timestamps. Keep soft failures distinct from passing outcomes. Do not count each attempt as an independent original failure or include the original attempt in retry execution totals.

If the rule matters to a recommendation, read `JobTypeCommand.retryRules.automatic` through a named GraphQL query with `bk api --file query.graphql`. Its exit-status/signal matching and limit describe which failures retry. Suggest reviewing automatic rules with repeatedly unsuccessful completed chains; a passing retry does not establish test flakiness, and repeated failure does not establish a common cause. Do not recommend retrying side-effecting work without confirming safety.

### 3. Schedule Health and Overlap

Read schedules and inspect enabled state, cron, next-build time, and recorded scheduling failures:

```bash
bk api "/pipelines/$pipeline/schedules" | jq '[.[] | {
  id, label, enabled, cronline, branch, commit, next_build_at,
  failed_at, failed_message
}]'
```

Follow list pagination before claiming all schedules were checked. A recorded scheduling failure means an attempt to create a build failed, not that a created build's jobs failed. Report its timestamp; do not assume an old failure is still active.

Compare effective branch/commit defaults and environments as well as cron expressions, including cron timezones. Compare environment values privately without displaying them; if unavailable, do not claim schedules are equivalent. Similar cron or repeated commits alone are not findings: schedules can intentionally recheck external systems or dependencies.

Attribute sampled builds using GraphQL `BuildSourceSchedule.pipelineSchedule`, or `PipelineSchedule.builds` with pagination and the same sample bounds. A deleted schedule can yield null attribution. Without attribution, label overlap as a configuration candidate rather than measured duplicate execution.

### 4. Measured Concurrency Contention

Use raw Jobs API `concurrency_wait_time_ms` where returned. Some CLI/SDK job models omit it; use `bk api` rather than interpreting omission as zero. Rank measured waits with counts of measured and unavailable durations. Zero means no wait. Null can mean no group, unfinished waiting, or wait inseparable from a platform-limit wait.

For a relevant job, retrieve current group identity, its configured limit, and bounded current contention context:

```bash
job=0190046e-e199-453b-a302-a21a4d649d31
bk api "/pipelines/$pipeline/builds/$build/jobs/$job/concurrency"
```

The jobs-ahead list applies when the job is limited, is visibility-filtered and capped, and is not a complete causal blocker inventory. An empty list does not prove no blockers. Current context does not explain historical waits by itself. Do not substitute `started_at - scheduled_at` for concurrency or agent-queue time; uploaded jobs can inherit older scheduled timestamps.

Suggest checking whether a group serializes unrelated work. Confirm the protected resource and ordering requirements before recommending any limit increase. Summed job wait is not elapsed build time saved.

## Inspect Configuration for a Specific Question

Follow up a concrete dependency/configuration question with stored pipeline YAML, available checkout files, or recent step-upload definitions. Do not turn every review into a repository-wide audit.

> For pipeline syntax, dependencies, retry configuration, caching, and concurrency configuration, see the **buildkite-pipelines** skill.

A pipeline's REST `configuration` can be only a bootstrap upload command. Step-upload list responses omit definitions; read an individual `/pipelines/{pipeline}/builds/{number}/step-uploads/{uuid}` with `bk api` for `definition_yaml`. Definitions expire with the build's maximum lifetime (up to 30 days; older requests return 410); oversized definitions can be omitted. Returned YAML is re-rendered, loses comments/anchors/formatting, and does not identify generator source. Do not execute generators or write uploaded definitions back as source files.

For a broad wait barrier, identify observed steps held back and inspect runtime dependencies where available (`JobTypeCommand.step.dependencies` and the wait-step equivalent in GraphQL). Account for explicit dependencies bypassing implicit wait/block barriers, dependencies on uploaded steps, approvals, artifacts, and concurrency ordering. Names such as “Lint” and “Test” do not prove independence. Recommend a focused dependency review when intent is unknown, not removing the barrier as a guaranteed speedup.

## Report Findings and Coverage

Lead with the few findings with the strongest evidence and clearest action. Rank measured observations before speculative configuration suggestions; do not fill a quota. Use these fields for each finding:

- **Observation:** what was found, including counts and denominators where relevant.
- **Evidence:** build/job links, relevant settings, and measured durations.
- **Suggested action:** the specific change to consider, or the next investigation when the correct change is unknown.
- **Before changing it:** intent/dependencies to confirm and evidence still missing.

Finish with the UTC sample bounds, pipeline/build counts, truncation, and checks that could not run. Say “No actionable findings in the sampled builds” only when supported, and qualify it with incomplete checks. Report execution and delay as measured, not guaranteed wall-clock or monetary savings. Keep credentials and environment values out of findings and evidence excerpts.

## Further Reading

- [Jobs and concurrency API](https://buildkite.com/docs/apis/rest-api/jobs)
- [Builds API](https://buildkite.com/docs/apis/rest-api/builds)
- [Pipeline schedules API](https://buildkite.com/docs/apis/rest-api/pipeline-schedules)
- [Step uploads API](https://buildkite.com/docs/apis/rest-api/step-uploads)
