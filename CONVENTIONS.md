# CONVENTIONS.md — Read This Before Writing Anything

You are writing an Agent Skill for Buildkite's CI/CD platform.
Your output will be installed by AI coding agents (Claude Code, Cursor, Codex,
Copilot, Windsurf, Gemini CLI) via `npx skills add buildkite/skills`.

**Read this entire file before writing a single line of your skill.**
**Then read `references/depot-ci-skill.md` as your quality benchmark.**

---

## Required: Confirm Your Understanding First

Before writing, state aloud (in your response or thinking):
1. The frontmatter you will use (copy the template below)
2. Your assigned skill name
3. Three topics you will NOT cover (per the boundary table below)
4. Your target size (10-15KB)

---

## File Location

Your skill lives at exactly this path:

```
skills/<skill-name>/SKILL.md
```

Do not create other files unless explicitly asked. Do not modify other skills.

---

## Frontmatter Template

Copy this exactly. Fill in `<skill-name>` and `<description>`:

```yaml
---
name: <skill-name>
description: >
  [2-3 sentences. First sentence: what this skill covers.
  Second sentence: trigger scenarios — start with "Use when...".
  Third sentence: additional triggers — start with "Also use when..."]
---
```

**Good description example:**
```yaml
description: >
  Configure and manage Buildkite CI/CD pipelines using pipeline.yml.
  Use when writing pipeline steps, configuring plugins, setting up dynamic
  pipelines, working with artifacts, or troubleshooting pipeline syntax.
  Also use when the user mentions .buildkite/ directory, buildkite-agent
  pipeline upload, or asks about Buildkite CI configuration.
```

**Why the description matters:** Agents load skills based on description matching.
A weak description means the skill never gets loaded. Write it to match real queries.

---

## Section Order (mandatory)

Every skill must follow this structure:

1. **YAML frontmatter** (name + description)
2. **H1 title** — `# Buildkite <Area>`
3. **2-sentence overview** — what this covers and why agents care
4. **## Quick Start** — minimum viable example, copy-paste ready, <20 lines
5. **## [Feature sections]** — one H2 per major feature area
   - Include CLI examples in fenced code blocks
   - Include flag tables for every command
   - Include YAML examples where relevant
6. **## Common Mistakes** — table format (see below)
7. **## Further Reading** — 3-5 links to buildkite.com/docs

---

## Style Rules

**Voice:**
- Write for agents, not humans. Agents need exact commands and structured data.
- Active voice: "Run `bk build create`" not "A build can be created by running..."
- No marketing language. No "powerful", "seamless", "robust", "best-in-class".
- No hedging. "Use `--branch` to specify the branch" not "You might want to consider using `--branch`..."

**Code blocks:**
- Every code block must be syntactically correct and copy-paste ready
- Use `bash` for shell commands, `yaml` for YAML, `json` for JSON
- Include the full command, not just fragments
- Show realistic example values, not `<your-value-here>` placeholders where avoidable

**Flag tables:**
Use this format for every CLI command:

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--branch` | `-b` | current branch | Git branch to build |
| `--commit` | `-c` | HEAD | Git commit SHA |

Always include the Default column. Agents use defaults to fill in omitted arguments.

**YAML examples:**
- Show complete, runnable examples (not snippets missing required fields)
- Add comments explaining non-obvious fields
- Show both minimal and full examples where helpful

**Cross-references:**
When your topic touches another skill's territory, use exactly this pattern:
> For [topic], see the **buildkite-[skill]** skill.

Never duplicate content owned by another skill. One sentence + pointer.

**Size target:** 10-15KB. The Depot reference is 14.5KB — match that density.
If your first draft is under 8KB, it's incomplete. Expand flag tables, add more
examples, deepen the common mistakes section.

---

## Skill Boundary Table

Each skill owns specific topics exclusively. Do not cover topics outside your boundary.

| Topic | Owner | Others do this |
|-------|-------|---------------|
| `pipeline.yml` syntax | **buildkite-pipelines** | Reference only |
| Step types (command, wait, block, trigger, group) | **buildkite-pipelines** | Reference only |
| Plugins — how to use them | **buildkite-pipelines** | Reference only |
| Dynamic pipelines (`buildkite-agent pipeline upload`) | **buildkite-pipelines** | Reference only |
| Hooks (environment, pre-command, post-command, etc.) | **buildkite-pipelines** | Reference only |
| Artifacts — YAML syntax for upload/download | **buildkite-pipelines** | Reference only |
| Retry, concurrency, priority rules | **buildkite-pipelines** | Reference only |
| Matrix builds | **buildkite-pipelines** | Reference only |
| `buildkite-agent` binary installation | **buildkite-agent** | Reference only |
| `buildkite-agent.cfg` configuration | **buildkite-agent** | Reference only |
| Tags and queue routing | **buildkite-agent** | Reference only |
| Clusters | **buildkite-agent** | Reference only |
| Agent tokens | **buildkite-agent** | Reference only |
| Hosted agents (sizes, labels) | **buildkite-agent** | Reference only |
| SSH keys, git mirrors | **buildkite-agent** | Reference only |
| Agent lifecycle hooks | **buildkite-agent** | Reference only |
| Agent diagnostics and debugging | **buildkite-agent** | Reference only |
| `bk build create/watch/view/list` | **buildkite-cli** | Reference only |
| `bk job log/retry/cancel` | **buildkite-cli** | Reference only |
| `bk pipeline` commands | **buildkite-cli** | Reference only |
| `bk secret` management | **buildkite-cli** | Reference only |
| `bk artifact` commands | **buildkite-cli** | Reference only |
| `bk auth login` | **buildkite-cli** | Reference only |
| REST API | **buildkite-platform** | Reference only |
| GraphQL API | **buildkite-platform** | Reference only |
| Webhooks | **buildkite-platform** | Reference only |
| Test Engine (splitting, analytics) | **buildkite-platform** | Reference only |
| Packages registry | **buildkite-platform** | Reference only |
| OIDC token management | **buildkite-platform** | Reference only |
| SSO/SAML | **buildkite-platform** | Reference only |
| Notification services | **buildkite-platform** | Reference only |

**Artifact ambiguity:** The pipeline YAML for artifact upload/download belongs to
**buildkite-pipelines**. The `bk artifact` CLI commands belong to **buildkite-cli**.
Each skill covers its half and cross-references the other.

---

## Common Mistakes Table Format

Use this exact format:

```markdown
## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| ... | ... | ... |
```

Aim for 5-8 rows. These are high-value for agents — they learn what NOT to do, which
is often more useful than what to do.

---

## Quality Checklist

Before you consider your skill done, verify:

- [ ] Frontmatter has both `name` and `description` fields
- [ ] Description contains trigger phrases ("Use when...", "Also use when...")
- [ ] Follows section order exactly (Quick Start before feature sections, Common Mistakes near end)
- [ ] File is 10-15KB
- [ ] Every CLI command has a flag table
- [ ] Flag tables include Default column
- [ ] All code blocks are syntactically correct
- [ ] No topics that belong to other skills (check boundary table)
- [ ] Minimum 5 rows in Common Mistakes table
- [ ] At least 3 Further Reading links to buildkite.com/docs
- [ ] Cross-references use "see the **buildkite-[skill]** skill" pattern

---

## Reference

Read `references/depot-ci-skill.md` to see what good looks like.
Note: that's a Depot file, not Buildkite. Do not copy content — use it as a
model for density, structure, and agent-friendliness only.
