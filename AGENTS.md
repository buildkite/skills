# Buildkite Skills — Agent Context

A collection of AI agent skills that teach coding agents how to use Buildkite CI/CD.
Installed via `npx skills add buildkite/skills` or manually copied into agent skill directories.

## Repository Structure

```
skills/                              # All skills live here
  buildkite-pipelines/               # Journey — pipeline YAML, step types, caching, parallelism
  buildkite-test-engine/             # Journey — test splitting, flaky detection, bktec CLI
  buildkite-secure-delivery/         # Journey — OIDC, Package Registry, SLSA provenance
  buildkite-agent-infrastructure/    # Journey — clusters, queues, hosted agents, SSO, audit
  buildkite-agent-runtime/           # Cross-cutting — buildkite-agent subcommands in job steps
  buildkite-cli/                     # Cross-cutting — bk CLI commands
  buildkite-api/                     # Cross-cutting — REST API, GraphQL, webhooks
evals/                               # Quality eval dataset and runner
references/                          # Shared reference materials
```

## Skill Architecture

Each skill directory contains:

- `SKILL.md` (required) — core skill content, 6-8KB target
- `references/` (optional) — detailed content loaded on demand
- `examples/` (optional) — complete runnable examples

Skills use progressive disclosure:
1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — loaded when skill triggers (~1,500-2,500 words)
3. **Bundled resources** — loaded as needed by the agent (unlimited)

## Key Conventions

- Read `CONVENTIONS.md` before writing or modifying any skill
- Each skill owns specific topics exclusively — see the boundary table in CONVENTIONS.md
- Cross-references use: `> For [topic], see the **buildkite-[skill]** skill.`
- Style: imperative voice, no second person, no marketing language
- All code blocks must be syntactically correct and copy-paste ready
- SKILL.md body target: 6-8KB; total with references: 10-15KB

## Quality Evaluation

The `evals/` directory contains a dataset of real customer questions and a runner
that tests skill routing and answer quality. See `evals/README.md` for usage.

## Working on Skills

1. Read `CONVENTIONS.md` completely
2. Review an existing complete skill as a quality benchmark
3. Check the boundary table — never duplicate content owned by another skill
4. Follow the section order: frontmatter, title, overview, quick start, feature sections, common mistakes, additional resources, further reading
5. Run evals to verify quality
