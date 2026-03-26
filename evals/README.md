# Buildkite Skills Evals Dataset

Evals dataset for testing Buildkite AI skill routing and answer quality. Built from real customer support questions (Plain threads, Sep 2025 - Mar 2026).

## Purpose

1. **Discover skill boundaries** — clusters in the dataset reveal natural topic groupings from real questions
2. **Test routing** — does the right skill get selected for each question?
3. **Test answer quality** — does the skill produce answers containing the right concepts?

## Dataset Format

Each eval in `dataset.yaml`:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (cluster-NNN format) |
| `question` | Standalone customer question (PII-free) |
| `source` | Origin: `plain`, `pf-ticket`, or `synthetic` |
| `source_ref` | Plain thread ID or PF ticket number |
| `difficulty` | `getting-started` \| `configuration` \| `troubleshooting` \| `advanced` |
| `cluster` | Natural topic cluster (emergent from support data) |
| `primary_skill` | Which skill should primarily handle this |
| `secondary_skills` | Additional skills involved (cross-skill questions) |
| `expected_contains` | Terms/concepts the answer MUST include |
| `expected_not_contains` | Terms that indicate wrong skill or hallucination |
| `tags` | Filterable labels |

## Cluster Distribution

| Cluster | Count | Key patterns |
|---------|-------|-------------|
| pipeline-config | 8 | YAML syntax, dynamic pipelines, uploads, validation |
| triggers | 3 | Branch filters, skip ci, if_changed |
| environment-vars | 3 | Cross-step data, meta-data, env hooks |
| retry-timeout | 4 | Automatic retry config, timeout behavior |
| artifacts | 2 | Cross-pipeline download, timing issues |
| agent-setup | 4 | Tokens, queues vs tags, disconnect settings |
| hosted-agents | 4 | Hosted vs self-hosted, networking, isolation |
| kubernetes | 2 | agent-stack-k8s hooks, env vars |
| api-graphql | 2 | Complexity limits, query construction |
| api-rest | 1 | Rate limits |
| webhooks | 4 | Setup, secrets, troubleshooting, GitHub vs BK |
| test-engine | 3 | Upload, splitting, bktec troubleshooting |
| oidc | 3 | AWS setup, token lifetime, vs API tokens |
| hooks-plugins | 1 | Pre-command hooks with Docker plugin |
| migration | 3 | Getting started, UI-to-YAML, planning |
| secrets | 2 | Cross-step secrets, token scoping |
| build-debugging | 2 | False failures, upload errors |
| docker | 1 | Artifacts in Docker builds |

## Insights for Skill Boundary Decisions

The support data suggests the current 4-skill split (pipelines, agent, CLI, platform) may not match real question patterns:

- **Webhooks** (50+ real threads) could be its own skill
- **Test Engine** (26+ threads) is distinct enough for its own skill
- **OIDC** (17+ threads) is a focused topic area
- **Hosted agents** (17+ threads) are distinct from self-hosted agent questions
- **Kubernetes/agent-stack-k8s** (12+ threads) has unique concerns
- **CLI** had very low support volume — may not need a dedicated skill

## Running Evals

### Setup

```bash
pip install -r evals/requirements.txt
```

Set `ANTHROPIC_API_KEY` in a `.env` file at the repo root (loaded automatically via python-dotenv):

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Quality Eval Runner

`run_quality.py` tests whether a skill's content produces answers containing the right concepts. For each eval it sends the question to the Anthropic API with the skill's `SKILL.md` as a system prompt, then grades the response against `expected_contains` and `expected_not_contains` terms.

```bash
# Run all evals for a skill
python evals/run_quality.py --skill buildkite-pipelines

# Focus on a specific cluster
python evals/run_quality.py --skill buildkite-pipelines --cluster pipeline-config

# Run specific evals by ID
python evals/run_quality.py --skill buildkite-pipelines --id pipeline-001,pipeline-006

# Filter by difficulty or tag
python evals/run_quality.py --skill buildkite-pipelines --difficulty getting-started
python evals/run_quality.py --skill buildkite-pipelines --tag dynamic-pipelines

# Speed up with parallel API calls
python evals/run_quality.py --skill buildkite-pipelines --parallel 5

# Use a different model
python evals/run_quality.py --skill buildkite-pipelines --model claude-opus-4-20250514

# Print full model responses in terminal
python evals/run_quality.py --skill buildkite-pipelines --show-responses

# Skip saving results JSON
python evals/run_quality.py --skill buildkite-pipelines --no-save
```

### Results

Each run saves a JSON file to `evals/results/` (gitignored) containing:
- Pass/fail status and matched/missed terms for each eval
- The full model response for each eval
- The original question for easy reading
- Aggregate stats (pass rate, coverage)

### Comparing Runs

Track progress between skill iterations using `--compare`:

```bash
# Edit SKILL.md to fix gaps, then re-run and compare
python evals/run_quality.py --skill buildkite-pipelines \
  --compare evals/results/quality-buildkite-pipelines-20260326-005304.json
```

This shows which evals flipped (FIXED/REGRESSED) and the pass rate delta.

### Iteration Workflow

1. Run evals: `python evals/run_quality.py --skill buildkite-pipelines`
2. Review failures — check which `expected_contains` terms are missing
3. Read the full responses in the results JSON to understand why
4. Improve `SKILL.md` to cover the gaps
5. Re-run with `--compare` to verify fixes and catch regressions
6. Repeat until pass rate is satisfactory

### Scoring

- **Pass/fail**: An eval passes when all `expected_contains` terms appear and no `expected_not_contains` terms appear (case-insensitive substring match)
- **Contains coverage**: Average fraction of expected terms matched across all evals
- **Boundary violations**: Count of `expected_not_contains` terms found (indicates hallucination or wrong-skill content)

The script exits with code 1 if any eval fails, making it usable in CI.

## Adding Evals

1. Use the next available ID in the relevant cluster (e.g., `pipeline-009`)
2. Prefer real questions from Plain/Avoma over synthetic ones
3. Distill questions to be standalone — no company names, no thread context
4. Include at least one `expected_contains` term
5. Tag cross-skill questions with `secondary_skills` and the `cross-skill` tag
