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

# Run without skill content (baseline — measures what Claude knows without the skill)
python evals/run_quality.py --skill buildkite-pipelines --baseline

# Run both with-skill and baseline, then print side-by-side comparison
python evals/run_quality.py --skill buildkite-pipelines --ablation --parallel 5
```

### Results

Each run saves a JSON file to `evals/results/` (gitignored) containing:
- Pass/fail status and matched/missed terms for each eval
- The full model response for each eval
- The original question for easy reading
- Aggregate stats (pass rate, coverage)

### Browsing Results (Web UI)

For easier browsing of full responses and side-by-side diffs between runs:

```bash
python evals/server.py
```

Opens a browser at `http://127.0.0.1:8089` with:
- Two dropdowns to pick result files A and B (auto-selects the two most recent quality runs)
- Summary bar with pass rates and delta
- Filter tabs: All / Fixed / Regressed / Both Fail / Both Pass
- Click any row to expand full responses side-by-side with markdown rendering

Pass `--port 9000` to change the port. No dependencies beyond Python stdlib.

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

### Ablation Testing (Skill vs No-Skill)

The `--ablation` flag runs every eval twice — once with the skill content and once without — then compares results to measure whether the skill actually improves answer quality.

```bash
python evals/run_quality.py --skill buildkite-pipelines --ablation --parallel 5
```

The comparison categorizes each eval as:

- **Skill-essential** — baseline fails, skill passes. These justify the skill's existence.
- **Skill-neutral** — both pass or both fail. The skill doesn't affect these questions.
- **Skill-harmful** — baseline passes, skill fails. The skill content may be misleading for these questions — investigate.

The baseline uses a fully generic system prompt (`You are a helpful AI assistant.`) with no Buildkite-specific priming, testing the skill's value against Claude's unprimed training knowledge.

You can also run just the baseline independently with `--baseline`, which is useful for comparing against previous runs using `--compare`.

### Trigger Precision Eval Runner

`run_trigger.py` tests whether Claude selects the correct skill based on description alone. It presents all skill descriptions in a system prompt, sends a query, and checks whether the model picks the right skill. This tests **routing accuracy** — complementary to the quality runner which tests **answer correctness**.

Uses a separate dataset (`trigger_dataset.yaml`) with should-trigger and near-miss entries per skill.

```bash
# Run all trigger evals
python evals/run_trigger.py

# Filter to evals targeting a specific skill
python evals/run_trigger.py --skill buildkite-pipelines

# Only run near-miss entries
python evals/run_trigger.py --tag near-miss

# Multi-run for trigger rate reliability (3 runs per query)
python evals/run_trigger.py --runs 3

# Only holdout split (40%) for validation after description tuning
python evals/run_trigger.py --holdout

# Parallel execution (default: 5 concurrent)
python evals/run_trigger.py --parallel 10

# Compare against previous run
python evals/run_trigger.py --compare evals/results/trigger-20260326-120000.json
```

#### Trigger Dataset Format

Each eval in `trigger_dataset.yaml`:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (`t-{skill}-NNN` or `t-{skill}-nNN` for near-misses) |
| `query` | User question to route |
| `expected_skill` | Which skill should be selected |
| `expected_not_skills` | Skills that must NOT be selected (for near-miss testing) |
| `tags` | `should-trigger`, `near-miss`, boundary labels like `pipelines-vs-runtime` |

#### Trigger Metrics

- **Accuracy**: overall correct routing rate
- **Per-skill precision**: of queries where skill X was selected, what fraction should have been?
- **Per-skill recall**: of queries where skill X should have been selected, what fraction was?
- **F1**: harmonic mean of precision and recall
- **Confusion matrix**: expected (rows) vs selected (columns) — reveals systematic misrouting

#### Quality vs Trigger: When to Use Which

| | Quality (`run_quality.py`) | Trigger (`run_trigger.py`) |
|---|---|---|
| **Tests** | Does the skill content produce correct answers? | Does Claude pick the right skill? |
| **When to run** | After editing SKILL.md content | After editing skill description (frontmatter) |
| **Fix loop** | Improve skill body content | Improve description trigger phrases |

#### Adding Trigger Evals

1. Use `t-{skill}-NNN` for should-trigger, `t-{skill}-nNN` for near-misses
2. Near-misses are the most valuable — use shared keywords but different intent
3. Focus on known boundary overlaps (e.g., `pipelines` vs `agent-runtime` for artifacts)
4. Include `expected_not_skills` for near-miss entries
5. Tag with the boundary being tested (e.g., `pipelines-vs-runtime`)

## Adding Quality Evals

1. Use the next available ID in the relevant cluster (e.g., `pipeline-009`)
2. Prefer real questions from Plain/Avoma over synthetic ones
3. Distill questions to be standalone — no company names, no thread context
4. Include at least one `expected_contains` term
5. Tag cross-skill questions with `secondary_skills` and the `cross-skill` tag
