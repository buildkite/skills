# Buildkite Skills

Skills that teach AI coding agents how to use [Buildkite](https://buildkite.com).
Install them into your agent of choice so it can generate correct Buildkite
pipeline YAML, configure agents, use the `bk` CLI, and call the API.

## Installation

```bash
npx skills add buildkite/skills
```

See [skills.sh](https://skills.sh) for more info.

### Cursor

Search for "Buildkite Skills" in the Cursor Marketplace, or run `/add-plugin` and search for "Buildkite".

### Manual

Copy skill files directly into your agent's skills directory:

```bash
# Claude Code
mkdir -p .claude/skills
cp -r skills/buildkite-pipelines .claude/skills/
cp -r skills/buildkite-agent .claude/skills/
cp -r skills/buildkite-cli .claude/skills/
cp -r skills/buildkite-platform .claude/skills/

# Cursor
mkdir -p .cursor/skills
cp -r skills/buildkite-pipelines .cursor/skills/
cp -r skills/buildkite-agent .cursor/skills/
cp -r skills/buildkite-cli .cursor/skills/
cp -r skills/buildkite-platform .cursor/skills/
```

## Available Skills

| Skill | Directory | Description |
|-------|-----------|-------------|
| **Pipelines** | [skills/buildkite-pipelines/](skills/buildkite-pipelines/SKILL.md) | Pipeline YAML, step types, plugins, dynamic pipelines, artifacts, hooks, matrix builds |
| **Agent** | [skills/buildkite-agent/](skills/buildkite-agent/SKILL.md) | Agent installation, configuration, tags, queues, clusters, hosted agents |
| **CLI** | [skills/buildkite-cli/](skills/buildkite-cli/SKILL.md) | `bk` commands for builds, jobs, pipelines, secrets, and artifacts |
| **Platform** | [skills/buildkite-platform/](skills/buildkite-platform/SKILL.md) | REST API, GraphQL, webhooks, Test Engine, Packages, OIDC, SSO |

## Contributing — Hackathon Quick Start

### 1. Clone and branch

```bash
git clone git@github.com:buildkite/skills.git
cd skills
git checkout -b <firstname>
```

### 2. Read the conventions and reference

Before writing anything, read these two files completely:

- **[CONVENTIONS.md](CONVENTIONS.md)** — frontmatter format, section order, style rules, skill boundary table, quality checklist
- **[references/depot-ci-skill.md](references/depot-ci-skill.md)** — quality benchmark (14.5KB, dense, agent-friendly)

### 3. Scope assignments

| Person | Skill | Directory | Primary docs |
|--------|-------|-----------|-------------|
| Ozden + Daniel | buildkite-pipelines | `skills/buildkite-pipelines/` | [buildkite.com/docs/pipelines](https://buildkite.com/docs/pipelines) |
| Baz | buildkite-agent | `skills/buildkite-agent/` | [buildkite.com/docs/agent/v3](https://buildkite.com/docs/agent/v3) |
| Jams | buildkite-cli | `skills/buildkite-cli/` | [buildkite.com/docs/platform/cli](https://buildkite.com/docs/platform/cli) |
| Simone | buildkite-platform | `skills/buildkite-platform/` | [buildkite.com/docs/apis](https://buildkite.com/docs/apis) |
| Patrick | README + llms.txt | root | (synthesizes from all four skills) |
| Ken | Blog draft + publishing | external | (writes after skills done) |

Each person owns exactly one directory. No two people write to the same path.

### 4. Write your skill

Open `skills/<your-skill>/SKILL.md` — the frontmatter stub is already there. Write the full skill content following the section order in CONVENTIONS.md.

**Agent bootstrapping prompt** (adapt for your tool):

```
Before writing anything, read these two files completely:
1. CONVENTIONS.md
2. references/depot-ci-skill.md

Then confirm you've read them by stating:
- The frontmatter format you'll use
- Your assigned skill name
- 3 topics you will NOT cover (because they belong to other skills)
- Your target file size

Only after this confirmation, fetch the docs from buildkite.com/docs/[your-area]
and write skills/<your-skill>/SKILL.md.
```

### 5. Commit and push

```bash
git add skills/<your-skill>/SKILL.md
git commit -m "wip: <skill-name> - <what you added>"
git push origin <firstname>
```

### 6. Open a PR when done

```bash
gh pr create --title "Add buildkite-<skill> skill" --base main
```

### Quality bar

- **10-15KB** per skill (the Depot reference is 14.5KB)
- Every CLI command has a **flag table** (Flag | Short | Default | Description)
- At least **5 rows** in the Common Mistakes table
- At least **3 links** in Further Reading
- **No boundary violations** — check the boundary table in CONVENTIONS.md

## Documentation

Full Buildkite docs at [buildkite.com/docs](https://buildkite.com/docs).

## License

[MIT](LICENSE)
