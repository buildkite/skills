# Log Search Patterns at Scale

In 2025, the in-UI log search regression cohort known internally as **PS-555** surfaced eight separate customer reports of the same problem: Materialize, Faire, Airbnb, Klaviyo, Samsara, Aurora, Block, and FlyZipline all reported that search in the job log viewer was effectively broken — either returning no matches for strings clearly present in the log, or matching the wrong line range, or hanging the page.

At the same scale, **PS-1600 (Anthropic, Sev 5)** documented `ProgressiveBuildShow` rendering pegging browser CPU at 100% on builds with many jobs, and **PS-700 (Affirm)** documented the same canvas-rendering pain on many-step builds.

The combined consequence: on a sufficiently large build, neither the log search nor the build page itself is a reliable investigation surface. This reference covers the workarounds.

## Decision: when to abandon the UI

Switch to `bk` or MCP / REST when any of the following hold:

- The build page takes more than five seconds to first paint.
- The job log viewer's search box returns no matches for a string the user can see in the streamed log.
- Browser CPU pegs while scrolling the log.
- The build has more than a few dozen jobs.
- The user is on a constrained network and the WebSocket reconnect loop is visible.

The cost of the switch is one command. The cost of staying in a slow UI compounds for the rest of the investigation.

## Pattern 1: grep over the raw log

The agent's job log is available via REST and via `bk`. Fetch once, grep many times.

```bash
# Full log via bk
bk job log <job-id> --pipeline my-org/my-app --build 42 > /tmp/job.log
grep -nE 'OOMKilled|Killed|exit code|panic|FATAL' /tmp/job.log

# Or the REST endpoint directly
bk api /organizations/my-org/pipelines/my-app/builds/42/jobs/<job-id>/log > /tmp/job.log
```

Tail-only when the failure is at the end:

```bash
bk job log <job-id> --pipeline my-org/my-app --build 42 | tail -500 | grep -nE 'error|fail'
```

## Pattern 2: job summary first, then full log

`--print-job-summary` returns the structured summary (Test Engine output, last-N-lines, exit code) without the full log body. Use this first to decide whether the full log is worth pulling.

```bash
bk job log <job-id> --pipeline my-org/my-app --build 42 --print-job-summary
```

## Pattern 3: structured log alternatives

Annotations and meta-data are structured by design and unaffected by log-search regressions. When the pipeline owner emits the failure signal as an annotation, search becomes a one-call API operation:

```bash
bk api /organizations/my-org/pipelines/my-app/builds/42/annotations | jq '.[] | select(.style=="error")'
```

For pipelines under your control, encode the failure category at write time:

```bash
buildkite-agent meta-data set "failure-reason" "infra-oom"
buildkite-agent annotate --style "error" --context "root-cause" "Step build-image OOMKilled at 14:02Z"
```

A downstream agent reading these via `list_annotations` / `get_build` never touches the log search box.

## Pattern 4: cohort search across builds

The in-UI search is per-job. To search across the cohort:

```bash
# List recent failed builds, then grep each one's logs for the signature
bk build list --pipeline my-org/my-app --state failed --output json \
  | jq -r '.[].number' \
  | while read n; do
      echo "--- build $n ---"
      bk build view "$n" --pipeline my-org/my-app --output json \
        | jq -r '.jobs[] | select(.state=="failed") | .id' \
        | while read job; do
            bk job log "$job" --pipeline my-org/my-app --build "$n" 2>/dev/null \
              | grep -H "OOMKilled" /dev/stdin && echo "  found in $n/$job"
          done
    done
```

The MCP equivalents (`list_builds`, `get_build`, `read_logs`) follow the same shape and avoid the shell-quoting pain.

## Pattern 5: when the build page itself is unusable

The PS-1600 pattern: opening the build URL pegs browser CPU, the page never finishes rendering, and the investigation cannot proceed in a browser.

Sequence:

1. Get the build number and pipeline slug from the URL — no need to load the page.
2. `bk build view <n> --pipeline <slug> --output json` returns the same data the page renders, in a fraction of the time.
3. Filter to failed jobs with `jq '.jobs[] | select(.state=="failed")'`.
4. Pull each failed job's summary and log via `bk job log`.

The `scripts/investigate-build.sh` helper packages this into one command for the common case.

## What is *not* a workaround

- Refreshing the page. The regression is deterministic on the build size, not the load.
- Trying a different browser. The CPU peg is in the rendering code, not the browser.
- Asking the user to wait. The UI does not get faster on its own.

## Related

- `failure-attribution-decision-tree.md` — once a log signature is found, classify it here.
- `annotations-for-postmortems.md` — leave the next investigator a structured signal that does not depend on log search.
