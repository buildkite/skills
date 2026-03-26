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

No eval runner exists yet. The dataset is designed for a future script that:

1. Passes `question` to the skill routing system
2. Checks if `primary_skill` was selected (routing accuracy)
3. Passes question + SKILL.md content to an LLM
4. Checks `expected_contains` terms appear in the response
5. Checks `expected_not_contains` terms do NOT appear
6. Scores: routing accuracy %, content coverage %, boundary violation rate

## Adding Evals

1. Use the next available ID in the relevant cluster (e.g., `pipeline-009`)
2. Prefer real questions from Plain/Avoma over synthetic ones
3. Distill questions to be standalone — no company names, no thread context
4. Include at least one `expected_contains` term
5. Tag cross-skill questions with `secondary_skills` and the `cross-skill` tag
