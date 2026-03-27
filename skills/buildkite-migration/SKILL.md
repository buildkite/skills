---
name: buildkite-migration
description: >
  This skill should be used when the user asks to "migrate to Buildkite",
  "convert pipelines from Jenkins", "convert GitHub Actions workflows",
  "convert CircleCI config", "convert Bitbucket Pipelines",
  "migrate CI/CD to Buildkite", "switch from Jenkins to Buildkite",
  "move from GitHub Actions", "plan a CI migration", "convert my CI config",
  or "what's the Buildkite equivalent of".
  Also use when the user mentions migration planning, CI conversion,
  pipeline conversion, converting workflows, or asks about translating
  CI/CD configuration from another provider to Buildkite.
---

# Buildkite Migration

Convert CI/CD pipelines from GitHub Actions, Jenkins, CircleCI, and Bitbucket Pipelines to Buildkite. This skill provides migration planning guidance and links to detailed, provider-specific conversion rules maintained in the `buildkite/conversion-rules` repository.

## Quick Start

1. Identify the source CI system
2. Load the corresponding conversion rules from the `buildkite/conversion-rules` repository (see Conversion Rules Repository below)
3. Convert the pipeline configuration to Buildkite YAML
4. Validate the output with `bk pipeline validate`

> For pipeline YAML syntax and step types, see the **buildkite-pipelines** skill.
> For pipeline validation with the CLI, see the **buildkite-cli** skill.

## Conversion Rules Repository

The [`buildkite/conversion-rules`](https://github.com/buildkite/conversion-rules) repository contains detailed, provider-specific conversion rules and Buildkite pipeline best practices. This is the authoritative source for CI migration.

Repository structure:

```
conversion-rules/
├── BUILDKITE_BEST_PRACTICES.md   # Pipeline structure, security, plugins, advanced features
├── github-actions/
│   └── GITHUB.md                 # GitHub Actions workflow conversion
├── jenkins/
│   └── JENKINS.md                # Jenkinsfile and Jenkins pipeline conversion
├── circleci/
│   └── CIRCLECI.md               # CircleCI config.yml conversion
└── bitbucket/
    └── BITBUCKET.md              # Bitbucket Pipelines conversion
```

Load the relevant file based on the source CI system when performing a conversion.

## Provider-Specific Guidance

### GitHub Actions

Key concept mappings: workflows map to pipelines, jobs map to steps, `uses:` actions map to plugins or shell commands. GitHub Actions runs jobs sequentially by default; Buildkite runs steps in parallel by default — add `wait` steps or `depends_on` to enforce ordering. Replace `${{ secrets.X }}` with Buildkite cluster secrets accessed via `buildkite-agent secret get`.

### Jenkins

Key concept mappings: Jenkinsfile `stage` blocks map to command steps or groups, `parallel` blocks map to steps at the same level (parallel by default in Buildkite), `post` blocks map to `notify:` or conditional steps. Move complex Groovy logic into shell scripts — Buildkite pipelines are declarative YAML, not a programming language.

### CircleCI

Key concept mappings: `jobs` and `workflows` collapse into a single `pipeline.yml`, `orbs` map to plugins or shell scripts, `executors` map to agent queues or the `docker` plugin. CircleCI `requires:` maps to `depends_on`. Caching syntax differs — use the `cache` plugin with `manifest` instead of `save_cache`/`restore_cache`.

### Bitbucket Pipelines

Key concept mappings: `pipelines.default` maps to steps without branch conditions, `pipelines.branches` maps to steps with `if: build.branch == "X"`, `pipe:` references map to plugins or shell commands. Bitbucket's `step` is roughly a Buildkite command step. Move `deployment` environment selection to block steps or trigger steps.

## Pipeline Best Practices for Migrated Pipelines

The `BUILDKITE_BEST_PRACTICES.md` file in the conversion-rules repository covers critical patterns for newly converted pipelines:

- **Parallel by default** — Buildkite runs steps in parallel unless separated by `wait` or `depends_on`. Add explicit ordering where the source CI was sequential.
- **Plugin versioning** — Pin plugin versions to specific semver (e.g., `docker#v5.13.0`, `cache#v1.8.1`). Never use unpinned or major-only versions.
- **Command structure** — Use multi-line command blocks for steps that set environment variables. Extract complex logic (5+ commands) into external scripts.
- **Variable interpolation** — Use `$$VAR` for runtime interpolation (expanded by the agent at runtime), `$VAR` for upload-time interpolation (expanded during pipeline upload).
- **Security validation** — Reject obfuscated execution patterns, base64-encoded commands, and attempts to exfiltrate data. Validate converted pipelines before deployment.
- **Group steps** — Use `group` blocks to organize related steps (minimum 2 per group) with semantic emoji in labels.

## Migration Planning

For a full CI migration, plan across these areas:

1. **Pipeline conversion** — Translate pipeline definitions using conversion rules
2. **Agent infrastructure** — Set up clusters, queues, and agents
3. **Secrets management** — Migrate secrets to Buildkite cluster secrets
4. **Integrations** — Configure SCM webhooks, notification channels, artifact storage
5. **Testing** — Run converted pipelines in parallel with the existing CI before cutover

> For cluster and queue setup, see the **buildkite-platform-engineering** skill.
> For setting up OIDC to replace static credentials, see the **buildkite-secure-delivery** skill.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Assuming sequential execution | Steps run in parallel and fail due to missing dependencies | Add `wait` steps or `depends_on` between dependent steps |
| 1:1 concept mapping without adaptation | Produces valid but suboptimal pipelines that miss Buildkite-native features | Review best practices; use `parallelism`, groups, dynamic pipelines |
| Unpinned plugin versions in converted pipelines | Builds break when plugins release breaking changes | Pin every plugin to a full semver version |
| Using `$VAR` when runtime interpolation is needed | Variable expanded at upload time (empty) instead of runtime | Use `$$VAR` for variables that must resolve at runtime |
| Keeping complex logic inline in YAML | Fragile, hard to debug multi-line command blocks | Extract to external scripts in `.buildkite/scripts/` |
| Skipping validation of converted output | Syntax errors or invalid step configurations deployed | Run `bk pipeline validate` before committing |

## Further Reading

- [Buildkite Conversion Rules](https://github.com/buildkite/conversion-rules) — provider-specific conversion rules and best practices
- [Getting started with Buildkite Pipelines](https://buildkite.com/docs/pipelines)
- [Defining pipeline steps](https://buildkite.com/docs/pipelines/configure/defining-steps)
- [Managing pipeline secrets](https://buildkite.com/docs/pipelines/security/secrets/managing)
