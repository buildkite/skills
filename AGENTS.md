# Buildkite Skills — Agent Context

A collection of AI agent skills that teach coding agents how to use Buildkite CI/CD.
Installed via `npx skills add buildkite/skills` or manually copied into agent skill directories.

## Repository Structure

```
skills/                              # All skills live here
  buildkite-pipelines/               # Journey — pipeline YAML, step types, caching, parallelism
  buildkite-migration/               # Journey — CI migration, bk pipeline convert, converting from GitHub Actions, Jenkins, CircleCI, Bitbucket, GitLab CI
  buildkite-preflight/               # Cross-cutting — bk preflight against local uncommitted changes
  buildkite-agent-runtime/           # Cross-cutting — buildkite-agent subcommands in job steps
  buildkite-cli/                     # Cross-cutting — bk CLI commands
  buildkite-api/                     # Cross-cutting — REST API, GraphQL, webhooks
```

## Skill Architecture

Each skill directory contains:

- `SKILL.md` (required) — core skill content, 10-18KB typical
- `references/` (optional) — detailed content loaded on demand
- `examples/` (optional) — complete runnable examples
- `agents/openai.yaml` (required) — multi-agent platform metadata
- `assets/` (required) — icon and brand assets for agent marketplaces

Skills use progressive disclosure:
1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — loaded when skill triggers (~1,500-2,500 words)
3. **Bundled resources** — loaded as needed by the agent (unlimited)

## Skills vs. Documentation

Skills are not documentation rewrites. They encode *expertise* — the judgment calls,
defaults, and pitfalls that experienced Buildkite users know — rather than cataloguing
features. Buildkite docs explain what's possible; skills teach agents how to do it correctly.

Assume the agent is already smart. Only include context it cannot infer on its own.
Link to Buildkite docs for canonical reference; do not reproduce them.

## Key Conventions

- Read `CONVENTIONS.md` before writing or modifying any skill
- Each skill owns specific topics exclusively — see the boundary table in CONVENTIONS.md
- Cross-references use: `> For [topic], see the **buildkite-[skill]** skill.`
- Style: imperative voice, no second person, no marketing language
- All code blocks must be syntactically correct and copy-paste ready
- SKILL.md body target: 10-18KB; total with references: 15-45KB

## Working on Skills

1. Read `CONVENTIONS.md` completely
2. Review an existing complete skill as a quality benchmark
3. Check the boundary table — never duplicate content owned by another skill
4. Follow the section order: frontmatter, title, overview, quick start, feature sections, common mistakes, additional resources, further reading
