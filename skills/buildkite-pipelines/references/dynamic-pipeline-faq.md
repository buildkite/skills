# Dynamic Pipeline FAQ

Recurring customer questions about dynamic pipelines that aren't covered elsewhere in the skill. Most of these resolve to "Buildkite doesn't have that feature" — naming the gap saves repeat investigation.

## Contents

1. [Is there a pre-upload hook?](#is-there-a-pre-upload-hook)
2. [Can I lock a build to prevent further pipeline uploads?](#can-i-lock-a-build-to-prevent-further-pipeline-uploads)
3. [Should I use branch-derived `concurrency_group` keys in dynamic pipelines?](#should-i-use-branch-derived-concurrency_group-keys-in-dynamic-pipelines)
4. [What does `Gusto/buildkite-builder` do?](#what-does-gustobuildkite-builder-do)

## Is there a pre-upload hook?

No. The agent's job lifecycle hooks are: `pre-bootstrap` (self-hosted agents only), `environment`, `pre-checkout`, `checkout`, `post-checkout`, `pre-command`, `command`, `post-command`, `pre-artifact`, `post-artifact`, `pre-exit`. There is no `pre-upload` hook that fires before `buildkite-agent pipeline upload`.

To validate or transform YAML before it's uploaded, do it in the generator script that pipes into `pipeline upload`. `pipeline upload --dry-run` validates the YAML server-side without committing it to the build:

```bash
#!/bin/bash
set -euo pipefail

.buildkite/generate.sh > /tmp/pipeline.yml
buildkite-agent pipeline upload --dry-run < /tmp/pipeline.yml
buildkite-agent pipeline upload /tmp/pipeline.yml
```

For agent-wide gating before any job is permitted to run, use `pre-bootstrap` (self-hosted only). It runs once per job — not once per upload — and can reject the job entirely by exiting non-zero. See the **buildkite-agent-infrastructure** skill for `pre-bootstrap` setup, and the [agent hooks reference](https://buildkite.com/docs/agent/hooks) for the full hook list.

## Can I lock a build to prevent further pipeline uploads?

No. Once a build is created, any running job in it can call `buildkite-agent pipeline upload` and add steps. `pipeline upload` has no `--freeze` flag, no "lock the build" toggle, and no built-in way to require uploads to come from a specific step.

This matters for security: a low-privilege step (e.g. lint) can upload a new step that runs against the same build's agent pool, including on queues reserved for higher-trust workloads. Mitigation patterns, in order of robustness:

1. **Separate queues by trust level.** Run the upload step on a low-trust queue, and target privileged steps (deploys, signing, release) at a different queue served by agents with restricted token access. This is the most common production pattern and the cheapest to adopt incrementally. See the **buildkite-agent-infrastructure** skill for cluster and queue setup.
2. **Pipeline signing.** Cryptographically verify uploaded YAML matches what was signed at upload time. Gives upload provenance and prevents unsigned steps from running on configured agents. See the **buildkite-secure-delivery** skill.
3. **Image-level hardening.** Run privileged steps in containers with reduced capabilities, separate IAM roles, or read-only filesystems. Doesn't prevent upload, only constrains what an injected step can do at runtime — the right tool when you can't restructure the queue topology.
4. **Disable fork builds and gate untrusted PRs with `block` steps.** Already covered in `references/dynamic-pipeline-troubleshooting.md` under Security. The standard recommendation for public pipelines.

For pipelines where any of these matter, design the queue topology before writing the dynamic pipeline.

## Should I use branch-derived `concurrency_group` keys in dynamic pipelines?

Prefer stable keys. Every unique `concurrency_group` key creates a record that persists in the organisation. High-cardinality keys — `deploy/${BUILDKITE_BRANCH}`, `build/${BUILDKITE_PULL_REQUEST}`, anything ending in a generated identifier — accumulate over time. Under heavy upload load, lookups against a very large concurrency-group set get slower; the concurrency-group UI page also lists every distinct key.

For dynamic pipelines, prefer keys derived from **the resource being protected**, not from the build that's running:

```yaml
# Avoid — every branch creates a new concurrency-group record
concurrency_group: "deploy/${BUILDKITE_BRANCH}"

# Prefer — one record per real deploy target
concurrency_group: "deploy/production"
concurrency_group: "migrate/users-db"
```

If the intent is "only one build per branch", use the `cancel_intermediate_builds` pipeline setting in Buildkite rather than per-branch concurrency groups. If high-cardinality keys are genuinely needed (rare — usually a sign that something else should be modelled), scope them tightly and don't pair them with high `concurrency:` limits.

Concurrency groups are organisation-scoped, not pipeline-scoped — two pipelines using `"deploy/auth/production"` share the limit globally. See `references/dynamic-pipeline-troubleshooting.md` → "Concurrency in dynamically generated steps" for the interpolation gotcha.

## What does `Gusto/buildkite-builder` do?

[`Gusto/buildkite-builder`](https://github.com/Gusto/buildkite-builder) is a community Ruby DSL for generating Buildkite pipelines. It predates the official [Buildkite SDK](https://github.com/buildkite/buildkite-sdk)'s Ruby support and offers a more idiomatic Ruby API for Ruby-heavy teams. It is a community project, not maintained by Buildkite.

When picking a generator language for dynamic pipelines:

| Option | Reach for it when |
|--------|-------------------|
| Bash heredocs | Generator is short and produces a small number of steps; no shared logic across pipelines |
| Buildkite SDK (TypeScript/JavaScript, Python, Go, Ruby) | Type checking, IDE support, unit-testable generator, shared retry/timeout policies across many steps |
| `Gusto/buildkite-builder` (Ruby) | Ruby-heavy team that wants an idiomatic Ruby DSL and is comfortable depending on a community project |
| Other community DSLs | When an existing tool already encodes the patterns the team needs and is actively maintained |

Pick a community DSL when its ergonomics meaningfully beat the official SDK and the team will own the dependency. The official SDK is the safer default for teams without a strong language preference.

## Further Reading

- [Agent hooks reference](https://buildkite.com/docs/agent/hooks)
- [Pipeline upload CLI reference](https://buildkite.com/docs/agent/v3/cli-pipeline.md)
- [Controlling concurrency](https://buildkite.com/docs/pipelines/configure/workflows/controlling-concurrency.md)
- [Buildkite SDK](https://github.com/buildkite/buildkite-sdk)
