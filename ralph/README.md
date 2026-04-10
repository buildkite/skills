# Ralph Wiggum Loop

An iterative self-improvement loop that tests and improves the Buildkite skills by repeatedly attempting to convert a real open-source project (Express.js) from GitHub Actions to Buildkite.

Named after the [Ralph Wiggum pattern](https://ghuntley.com/ralph/) -- each iteration starts completely fresh with no memory of previous attempts. The skills themselves are the only thing that improves between iterations.

> [!NOTE]
> This was an experiment. It actually works quite well at trying to automate the migration of a public repo GHA CI to Buildkite. But the skills were not well developed enough. And not enough of the setup could be done by agents. 

## How it works

```
     ┌──────────────────────────────────────────────┐
     │              orchestrate.sh                   │
     │              (outer loop)                     │
     └──────────────┬───────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
 Phase 1         Phase 2        Phase 3
 CONVERT         EVALUATE       IMPROVE
 (Docker)        (Python)       (worktree)
    │               │               │
    ▼               ▼               ▼
 .buildkite/     scores.json    skills/
 + BK cluster    + bar chart    + commit
```

### Phase 1: Conversion (Docker sandbox)

A fresh Claude Code agent runs inside a Docker container with:
- Express.js checkout mounted read-write at `/workspace`
- Skills repo mounted read-only at `/skills`
- Full bash access (the container IS the sandbox)
- Buildkite MCP tools for creating real infrastructure

The agent reads the GitHub Actions workflows, reads the Buildkite skills for guidance, then converts everything to Buildkite pipelines. It creates real clusters, queues, and pipelines via the Buildkite API.

### Phase 2: Evaluation (local Python)

The evaluator scores the conversion across 9 categories:

| Category | Weight | How it's checked |
|----------|--------|-----------------|
| File existence | 10% | Expected `.buildkite/*.yml` files exist |
| YAML validity | 10% | Valid YAML + `bk pipeline validate` |
| Workflow coverage | 15% | All GHA workflow features represented |
| Matrix builds | 10% | Uses Buildkite-native `matrix:` syntax |
| Buildkite idioms | 10% | Uses `depends_on`, `wait`, `agents:`, etc. |
| Infrastructure live | 15% | Cluster/queues/pipelines verified via `bk` CLI |
| Builds ran | 15% | Builds triggered, completed, and passed |
| Conversion notes | 5% | CONVERSION_NOTES.md exists with substance |
| No anti-patterns | 10% | Zero GitHub Actions syntax remnants |

### Phase 3: Improvement (restricted worktree)

A second Claude Code agent analyzes the eval results and conversion log, identifies the lowest-scoring categories, and patches the skill files to address the gaps. It runs in a git worktree with restricted tools (no general bash, only `python evals/*` for regression checks).

Then the loop resets Express.js to a clean branch and tries again.

## Security model

| Agent | Sandbox | Tools | Secrets |
|-------|---------|-------|---------|
| Conversion | Docker container | Full bash, MCP tools | Only `ANTHROPIC_API_KEY` + `BUILDKITE_API_TOKEN` |
| Improvement | Git worktree + restricted tools | Read, Edit, Glob, Grep, `python evals/*` | Only `ANTHROPIC_API_KEY` |

The conversion agent cannot access the host filesystem, SSH keys, or other credentials. The improvement agent cannot run arbitrary bash or access external services.

## Files

| File | Purpose |
|------|---------|
| `orchestrate.sh` | Main loop -- manages iterations, phases, termination |
| `Dockerfile` | Docker sandbox image (Node 20 + Claude CLI + bk agent/CLI) |
| `mcp-config.json` | Buildkite MCP server config (mounted into container) |
| `PROMPT.md` | System prompt for the conversion agent |
| `IMPROVE.md` | System prompt for the improvement agent |
| `evaluate.py` | Scores conversion output against the rubric |
| `rubric.yaml` | Evaluation rubric (categories, weights, checks) |
| `express-checkout/` | Cloned Express.js repo (the conversion target) |
| `state/` | Iteration history, logs, eval results |

## Usage

### Prerequisites

```bash
# Docker running (OrbStack, Docker Desktop, etc.)
# Required env vars:
export ANTHROPIC_API_KEY=sk-ant-...
export BUILDKITE_API_TOKEN=bkua_...

# Optional: customer research (Plain support threads, Avoma call recordings)
export PLAIN_API_KEY=...
export AVOMA_API_KEY=...
export CUSTOMER_RESEARCH_DIR=/path/to/buildkite-product-toolkit/skills/customer-research

# bk CLI installed and authenticated
bk configure
```

### Build the Docker image

```bash
docker build -t ralph-agent ralph/
```

### Run the loop

```bash
# Full loop (up to 20 iterations, stops at 90% score or plateau)
./ralph/orchestrate.sh

# Single iteration for testing
./ralph/orchestrate.sh --max-iterations 1

# Dry run (skip Docker/Claude, just test evaluator plumbing)
./ralph/orchestrate.sh --dry-run

# Skip Buildkite infrastructure creation (offline mode)
./ralph/orchestrate.sh --skip-infra

# Use a different model
./ralph/orchestrate.sh --model opus
```

### Check results

```bash
# View iteration history
cat ralph/state/iterations.json | python3 -m json.tool

# View latest eval
cat ralph/state/eval-v1.json | python3 -m json.tool

# Run evaluator manually
python3 ralph/evaluate.py \
  --express-dir ralph/express-checkout \
  --cluster-name ralph-express-v1 \
  --version 1 \
  --output ralph/state/eval-manual.json
```

## Termination conditions

The loop stops when:
1. **Score >= 90%** -- the skills reliably guide a conversion
2. **20 iterations reached** -- max budget protection
3. **3 iterations with no improvement** -- plateau detected

## What Express.js has

The target repo has 4 GitHub Actions workflows:

- **ci.yml** -- Lint + test matrix (8 Node versions x 2 OSes) + coverage
- **codeql.yml** -- CodeQL security scanning (weekly + on push)
- **legacy.yml** -- Legacy Node 16/17 testing
- **scorecard.yml** -- OpenSSF Scorecard (weekly)

This is a realistic migration target covering matrices, scheduled builds, cross-platform testing, security scanning, and coverage aggregation.
