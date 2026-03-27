# CONVENTIONS.md — Read This Before Writing Anything

You are writing an Agent Skill for Buildkite's CI/CD platform.
Your output will be installed by AI coding agents (Claude Code, Cursor, Codex,
Copilot, Windsurf, Gemini CLI) via `npx skills add buildkite/skills`.

**Read this entire file before writing a single line of your skill.**
**Then review an existing complete skill (e.g. `skills/buildkite-pipelines/SKILL.md`) as your quality benchmark.**

---

## Required: Confirm Your Understanding First

Before writing, state aloud (in your response or thinking):
1. The frontmatter you will use (copy the template below)
2. Your assigned skill name
3. Three topics you will NOT cover (per the boundary table below)
4. Your SKILL.md size target (6-8KB body, with overflow in `references/`)

---

## Skill Directory Structure

Each skill lives in its own directory with this structure:

```
skills/<skill-name>/
├── SKILL.md              (required — core skill, 6-8KB target)
├── references/           (optional — detailed content loaded on demand)
│   ├── flag-reference.md
│   └── advanced-examples.md
├── examples/             (optional — complete, runnable example files)
└── scripts/              (optional — utility scripts for validation, etc.)
```

### Progressive Disclosure

Skills use a three-tier loading system to manage context efficiently:

1. **Metadata (name + description)** — always in context (~100 words)
2. **SKILL.md body** — loaded when skill triggers (~1,500-2,500 words)
3. **Bundled resources** — loaded as needed by the agent (unlimited)

This means SKILL.md should contain the **essential** knowledge an agent needs for
common tasks. Move exhaustive flag tables, advanced examples, edge cases, and deep
reference material into `references/` files. The agent will read them when needed.

### What goes where

| Content type | Location | Why |
|-------------|----------|-----|
| Core concepts, quick start, common patterns | `SKILL.md` | Always needed |
| Exhaustive flag tables, advanced YAML examples | `references/` | Loaded on demand |
| Complete runnable pipeline examples | `examples/` | Copy-paste ready |
| Validation or helper scripts | `scripts/` | Executed without reading |

Do not modify other skills. Create only the directories you actually need.

---

## Frontmatter Template

Copy this exactly. Fill in `<skill-name>` and `<description>`:

```yaml
---
name: <skill-name>
description: >
  This skill should be used when the user asks to [primary task verb phrases].
  Also use when the user mentions [specific terms, directories, commands, or concepts].
---
```

**Good description example:**
```yaml
description: >
  This skill should be used when the user asks to "configure pipelines",
  "write pipeline steps", "set up dynamic pipelines", "troubleshoot pipeline syntax",
  or "work with artifacts in pipeline YAML".
  Also use when the user mentions .buildkite/ directory, buildkite-agent pipeline
  upload, pipeline.yml, or asks about Buildkite CI configuration.
```

**Why the description matters:** Agents load skills based on description matching.
A weak description means the skill never gets loaded. Include specific quoted phrases
that match real user queries. Use third person ("This skill should be used when...")
so the system can evaluate the description in context.

---

## Section Order (mandatory)

Every SKILL.md must follow this structure:

1. **YAML frontmatter** (name + description)
2. **H1 title** — `# Buildkite <Area>`
3. **2-sentence overview** — what this covers and why agents care
4. **## Quick Start** — minimum viable example, copy-paste ready, <20 lines
5. **## [Feature sections]** — one H2 per major feature area
   - Include CLI examples in fenced code blocks
   - Include flag tables for the most common commands
   - Include YAML examples where relevant
6. **## Common Mistakes** — table format (see below)
7. **## Additional Resources** — pointers to `references/` and `examples/` files
8. **## Further Reading** — 3-5 links to buildkite.com/docs

---

## Style Rules

**Voice — imperative/infinitive form:**
- Write for agents, not humans. Agents need exact commands and structured data.
- Use imperative form: "Run `bk build create`" not "You should run `bk build create`"
- No second person. Write "Specify the branch with `--branch`" not "You can specify..."
- No marketing language. No "powerful", "seamless", "robust", "best-in-class".
- No hedging. "Use `--branch` to specify the branch" not "You might want to consider using `--branch`..."

**Code blocks:**
- Every code block must be syntactically correct and copy-paste ready
- Use `bash` for shell commands, `yaml` for YAML, `json` for JSON
- Include the full command, not just fragments
- Show realistic example values, not `<your-value-here>` placeholders where avoidable

**Flag tables:**
Use this format for CLI commands. Include the most essential commands inline in
SKILL.md; move exhaustive tables to `references/`.

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

**Size targets:**
- SKILL.md body: **6-8KB** (~1,500-2,500 words). Contains core knowledge for common tasks.
- References: **unlimited**. Move detailed flag tables, advanced examples, and edge cases here.
- Total skill content (SKILL.md + references): **10-15KB** typical.

If your SKILL.md first draft exceeds 8KB, identify sections to extract into `references/`.
If it's under 4KB, it's too thin — expand quick start, add more inline examples, deepen
common mistakes.

---

## Referencing Bundled Resources

When your skill includes `references/`, `examples/`, or `scripts/`, add an
**Additional Resources** section near the end of SKILL.md:

```markdown
## Additional Resources

### Reference Files
- **`references/flag-reference.md`** — Complete flag tables for all commands
- **`references/advanced-examples.md`** — Complex pipeline patterns and edge cases

### Examples
- **`examples/basic-pipeline.yml`** — Minimal working pipeline
- **`examples/matrix-build.yml`** — Matrix build with multiple languages
```

This ensures the agent knows these resources exist and can load them when needed.

---

## Skill Boundary Table

Each skill owns specific topics exclusively. Do not cover topics outside your boundary.

| Topic | Owner | Others do this |
|-------|-------|---------------|
| `pipeline.yml` syntax, step types, plugins, caching, parallelism, retry, `if_changed`, dynamic pipelines, matrix, `notify:`, `artifact_paths:`, concurrency, `agents:` routing, `secrets:` | **buildkite-pipelines** | Reference only |
| Test Engine suites, `bktec` CLI, test splitting, flaky detection, quarantine, test collectors, `BUILDKITE_TEST_ENGINE_*` env vars | **buildkite-test-engine** | Reference only |
| OIDC auth flows, Package Registry setup, SLSA provenance, pipeline signing (JWKS), verification rollout | **buildkite-secure-delivery** | Reference only |
| Clusters, queues, hosted agent instance shapes, cluster secrets, `buildkite-agent.cfg`, agent tokens, lifecycle hooks, pipeline templates, audit logging, SSO/SAML, cost optimization | **buildkite-platform-engineering** | Reference only |
| `buildkite-agent` subcommands inside job steps: annotate, artifact, meta-data, pipeline upload, oidc, step, lock, env, secret, redactor, tool sign/verify | **buildkite-agent-runtime** | Reference only |
| `bk build`, `bk job`, `bk pipeline`, `bk secret`, `bk artifact`, `bk auth`, `bk cluster`, `bk package` commands | **buildkite-cli** | Reference only |
| REST API endpoints, GraphQL schema/mutations, webhook setup, API authentication, pagination | **buildkite-api** | Reference only |
| CI migration planning, provider-specific conversion rules (GitHub Actions, Jenkins, CircleCI, Bitbucket), pipeline best practices for converted pipelines | **buildkite-migration** | Reference only |

**Artifact ambiguity:** The pipeline YAML for artifact upload/download belongs to
**buildkite-pipelines**. The `buildkite-agent artifact` subcommands belong to
**buildkite-agent-runtime**. The `bk artifact` CLI commands belong to **buildkite-cli**.
Each skill covers its scope and cross-references the others.

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

**Structure:**
- [ ] Frontmatter has both `name` and `description` fields
- [ ] Description uses third person ("This skill should be used when...")
- [ ] Description contains specific quoted trigger phrases
- [ ] Follows section order exactly (Quick Start before feature sections, Common Mistakes near end)
- [ ] SKILL.md body is 6-8KB; detailed content moved to `references/`
- [ ] All referenced `references/` and `examples/` files exist

**Content:**
- [ ] Written in imperative/infinitive form — no second person ("you")
- [ ] Every inline CLI command has a flag table
- [ ] Flag tables include Default column
- [ ] All code blocks are syntactically correct and copy-paste ready
- [ ] No topics that belong to other skills (check boundary table)
- [ ] Minimum 5 rows in Common Mistakes table
- [ ] At least 3 Further Reading links to buildkite.com/docs
- [ ] Cross-references use "see the **buildkite-[skill]** skill" pattern

**Progressive Disclosure:**
- [ ] Core concepts and common patterns in SKILL.md
- [ ] Exhaustive flag tables, advanced examples in `references/`
- [ ] Additional Resources section points to bundled files
- [ ] Total skill content (SKILL.md + references) is 10-15KB

---

## Reference

Review existing complete skills to see what good looks like:

- **`skills/buildkite-pipelines/SKILL.md`** — journey skill with progressive disclosure (SKILL.md + references/ + examples/)
- **`skills/buildkite-api/SKILL.md`** — cross-cutting skill, single-file format
- **`skills/buildkite-agent-runtime/SKILL.md`** — cross-cutting skill with reference files

Use these as models for density, structure, and agent-friendliness.
