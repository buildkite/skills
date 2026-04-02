---
name: buildkite-preflight
description: >
  This skill should be used when the user asks to "run preflight",
  "validate changes before pushing", "check CI locally", "pre-commit validation",
  "test my changes against CI", or "run a preflight build".
  Also use when the user mentions bk preflight, preflight builds,
  pre-push validation, or asks about validating local changes against
  a Buildkite pipeline before committing.
---

# Buildkite Preflight

Preflight validates local changes against a Buildkite CI pipeline by pushing a temporary commit, waiting for the build, and reporting structured results — all without disrupting the working tree. It is a subcommand of the `bk` CLI gated behind the `preflight` experiment.

## Quick Start

```bash
# Enable the preflight experiment (one-time setup)
bk config set experiments preflight

# Run preflight against a pipeline and watch the build
bk preflight --pipeline my-org/my-pipeline --watch
```

## How It Works

Preflight executes a five-stage workflow:

1. **Snapshot** — Stashes uncommitted changes (staged, unstaged, untracked), creates a temporary commit, then restores the working tree.
2. **Push** — Pushes the commit to `refs/heads/bk/preflight/<id>` on origin. Buildkite picks it up via the normal webhook flow.
3. **Wait** — Polls the Buildkite API until a build appears for the preflight branch (when `--watch` is enabled).
4. **Monitor** — Polls the build until all jobs reach a terminal state.
5. **Report** — Outputs a summary of command job results. Wait, block, trigger, and other non-command jobs are excluded.

The working tree is never disrupted — continue editing while the build runs.

## Enabling the Experiment

The `preflight` subcommand requires the experiment flag. Set it once via config or per-invocation via environment variable:

```bash
# Persistent (recommended)
bk config set experiments preflight

# Per-invocation
BUILDKITE_EXPERIMENTS=preflight bk preflight --pipeline my-org/my-pipeline --watch
```

## Running a Preflight Build

### Basic usage

```bash
# Run preflight and watch until completion
bk preflight --pipeline my-org/my-pipeline --watch

# Run without watching (starts the build and exits)
bk preflight --pipeline my-org/my-pipeline

# Skip confirmation prompts (useful in scripts)
bk preflight --pipeline my-org/my-pipeline --watch --yes

# Increase polling interval to reduce API calls
bk preflight --pipeline my-org/my-pipeline --watch --interval 5

# Keep the remote preflight branch after the build finishes
bk preflight --pipeline my-org/my-pipeline --watch --no-cleanup
```

### Pipeline resolution

The `--pipeline` flag accepts either a pipeline slug or `{org slug}/{pipeline slug}`:

```bash
# With org prefix (explicit)
bk preflight --pipeline my-org/my-pipeline --watch

# Pipeline slug only (org resolved from bk config)
bk preflight --pipeline my-pipeline --watch
```

## Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--pipeline` | `-p` | — | Pipeline to build (`{slug}` or `{org}/{slug}`) (required) |
| `--[no-]watch` | | — | Watch the build until completion |
| `--interval` | | `2` | Polling interval in seconds when watching |
| `--no-cleanup` | | `false` | Skip deleting the remote preflight branch after the build finishes |
| `--yes` | `-y` | `false` | Skip all confirmation prompts |
| `--no-input` | | `false` | Disable all interactive prompts |
| `--quiet` | `-q` | `false` | Suppress progress output |
| `--no-pager` | | `false` | Disable pager for text output |
| `--debug` | | `false` | Enable debug output for REST API calls |

## Exit Codes

Check the exit code to determine the build result:

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| `0` | All command jobs passed | Proceed with commit/push |
| `1` | Generic error | Check error message for details |
| `9` | Build completed with failures | Examine failed jobs and fix |
| `10` | Build incomplete but failures observed | Build still running; failures already detected |
| `11` | Build incomplete (scheduled/running/blocked) | Build hasn't finished yet |
| `12` | Unknown build state | Investigate the build on Buildkite |
| `130` | User aborted (Ctrl+C) | Re-run when ready |

## Interpreting Results

Preflight only reports on **command jobs** (script/command steps). Other job types (wait, block, trigger) are excluded from the summary. When a build finishes:

- **Exit code 0** — All command jobs passed. Safe to commit and push.
- **Exit code 9** — One or more command jobs failed. Preflight logs all failures. Examine the output, fix issues, and re-run.
- **Exit code 10** — Build is still running but failures have already been detected. Decide whether to wait or start fixing.

## Typical Workflow

```bash
# 1. Make changes locally
vim src/app.go

# 2. Run preflight to validate against CI
bk preflight --pipeline my-org/my-pipeline --watch

# 3. If preflight passes (exit code 0), commit and push
git add -A && git commit -m "feat: add new endpoint"
git push origin HEAD
```

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Running `bk preflight` without enabling the experiment | Command not found or unrecognized subcommand | Run `bk config set experiments preflight` first |
| Omitting `--watch` and expecting results | Preflight starts the build and exits immediately without reporting results | Add `--watch` to wait for the build to complete |
| Running preflight without a clean git remote | Push to `refs/heads/bk/preflight/<id>` fails | Ensure the git remote `origin` is configured and accessible |
| Confusing preflight exit code 9 with a generic error | Exit code 9 specifically means the build completed with job failures | Check the logged failures rather than treating it as an infrastructure error |
| Running preflight without `bk configure` | Authentication fails on API calls | Run `bk configure` or `bk auth login` first — see the **buildkite-cli** skill |
| Expecting non-command jobs in the report | Wait, block, and trigger jobs are excluded | Preflight only reports on command (script) jobs |

## Further Reading

- [Buildkite CLI overview](https://buildkite.com/docs/platform/cli)
- [CLI command reference](https://buildkite.com/docs/platform/cli/reference)
- [CLI installation](https://buildkite.com/docs/platform/cli/installation)
