# Buildkite Skills

Skills that teach AI coding agents how to use [Buildkite](https://buildkite.com).
Install them into your agent of choice so it can generate correct pipeline YAML,
run CLI commands, call the API, configure agents, split tests, and ship securely.

## Installation

```bash
npx skills add buildkite/skills
```

See [skills.sh](https://skills.sh) for supported agents and options.

### Cursor

Search for **Buildkite Skills** in the Cursor Marketplace, or run `/add-plugin` and search for "Buildkite".

### Manual

Copy skill directories into your agent's skills folder:

```bash
# Claude Code
mkdir -p .claude/skills
cp -r skills/buildkite-pipelines .claude/skills/
cp -r skills/buildkite-preflight .claude/skills/
cp -r skills/buildkite-agent-runtime .claude/skills/
cp -r skills/buildkite-cli .claude/skills/
cp -r skills/buildkite-api .claude/skills/
cp -r skills/buildkite-migration .claude/skills/
cp -r skills/buildkite-agent-infrastructure .claude/skills/
cp -r skills/buildkite-secure-delivery .claude/skills/
cp -r skills/buildkite-test-engine .claude/skills/

# Cursor
mkdir -p .cursor/skills
cp -r skills/buildkite-pipelines .cursor/skills/
cp -r skills/buildkite-preflight .cursor/skills/
cp -r skills/buildkite-agent-runtime .cursor/skills/
cp -r skills/buildkite-cli .cursor/skills/
cp -r skills/buildkite-api .cursor/skills/
cp -r skills/buildkite-migration .cursor/skills/
cp -r skills/buildkite-agent-infrastructure .cursor/skills/
cp -r skills/buildkite-secure-delivery .cursor/skills/
cp -r skills/buildkite-test-engine .cursor/skills/
```

## Skills

### Journey Skills

Skills organized by what you are trying to accomplish.

| Skill | Directory | Description |
|-------|-----------|-------------|
| **Pipelines** | [skills/buildkite-pipelines/](skills/buildkite-pipelines/SKILL.md) | Pipeline YAML, step types, plugins, caching, parallelism, dynamic pipelines, matrix builds, artifacts, hooks |
| **Test Engine** | [skills/buildkite-test-engine/](skills/buildkite-test-engine/SKILL.md) | Test splitting, flaky detection, quarantine, bktec CLI, test collectors |
| **Secure Delivery** | [skills/buildkite-secure-delivery/](skills/buildkite-secure-delivery/SKILL.md) | OIDC authentication, Package Registry, SLSA provenance, pipeline signing |
| **Migration** | [skills/buildkite-migration/](skills/buildkite-migration/SKILL.md) | CI migration planning, converting from GitHub Actions, Jenkins, CircleCI, Bitbucket Pipelines, GitLab CI using `bk pipeline convert` |
| **Platform Engineering** | [skills/buildkite-agent-infrastructure/](skills/buildkite-agent-infrastructure/SKILL.md) | Clusters, queues, hosted agents, agent config, pipeline templates, SSO, audit logging |

### Cross-Cutting Skills

Skills needed across all journeys.

| Skill | Directory | Description |
|-------|-----------|-------------|
| **Preflight** | [skills/buildkite-preflight/](skills/buildkite-preflight/SKILL.md) | `bk preflight` runs local uncommited changes against CI |
| **Agent Runtime** | [skills/buildkite-agent-runtime/](skills/buildkite-agent-runtime/SKILL.md) | `buildkite-agent` subcommands inside running job steps — annotate, artifact, meta-data, pipeline upload, OIDC, locks |
| **CLI** | [skills/buildkite-cli/](skills/buildkite-cli/SKILL.md) | `bk` commands for builds, jobs, pipelines, secrets, artifacts, and auth |
| **API** | [skills/buildkite-api/](skills/buildkite-api/SKILL.md) | REST API, GraphQL API, webhooks, authentication, pagination |

## How Skills Differ from Docs

Buildkite docs at [buildkite.com/docs](https://buildkite.com/docs) are the canonical
reference for what Buildkite features exist and how they work.

Skills serve a different purpose: they encode **expertise**. Where docs explain every
option, skills teach agents the right defaults, common patterns, and mistakes to avoid.
A skill captures the judgment an experienced Buildkite user applies — which step type to
reach for, how to structure a dynamic pipeline, when to use OIDC instead of static tokens.

In practice this means:
- Skills assume the agent already understands YAML, CI/CD concepts, and general programming
- SKILL.md files focus on quick starts, recommended patterns, and pitfall tables — not exhaustive option lists
- Detailed reference material lives in `references/` subdirectories, loaded only when needed
- Skills link to Buildkite docs rather than reproducing them

For more on content strategy, see [CONVENTIONS.md](CONVENTIONS.md).

## Contributing

1. Read [CONVENTIONS.md](CONVENTIONS.md) — frontmatter format, section order, style rules, skill boundaries, quality checklist
2. Review an existing complete skill as a quality benchmark (e.g. `skills/buildkite-pipelines/SKILL.md`)
3. Check the boundary table in CONVENTIONS.md — each topic is owned by exactly one skill
4. Write your skill following the section order and style rules
5. Run evals to verify quality (internal — see [buildkite/skills-internal-tools](https://github.com/buildkite/skills-internal-tools))

## Documentation

Full Buildkite docs at [buildkite.com/docs](https://buildkite.com/docs).

## License

[MIT](LICENSE)
