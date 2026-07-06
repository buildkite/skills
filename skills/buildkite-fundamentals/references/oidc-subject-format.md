# OIDC Subject Format

Buildkite issues OpenID Connect tokens to running jobs via `buildkite-agent oidc request-token`. External verifiers (AWS IAM, GCP Workload Identity Federation, Azure federated credentials, HashiCorp Vault, Buildkite Packages) match against the token's `sub` claim and a set of standard custom claims. This reference is the canonical source for the subject format and the claim list — quote it directly when writing trust policies.

## Canonical subject string

```
organization:<org-slug>:pipeline:<pipeline-slug>:ref:<git-ref>:commit:<sha>:step:<step-key>
```

Example for a tag build:

```
organization:my-org:pipeline:my-app:ref:refs/tags/v1.4.2:commit:9e2c1ab4...:step:deploy-prod
```

Example for a branch build with no step key set:

```
organization:my-org:pipeline:my-app:ref:refs/heads/main:commit:9e2c1ab4...:step:
```

The trailing `step:` segment is present even when empty, because the format is positional. Trust policies that match on subject prefix should account for this.

## Custom claims

The OIDC token carries the following claims in addition to the standard OIDC set. Trust policies should match on these directly rather than parsing the `sub` string.

| Claim | Example | Notes |
|---|---|---|
| `organization_slug` | `my-org` | Stable across renames only via slug; matches `<org-slug>` in `sub` |
| `organization_id` | `019b0b68-1b42-...` | UUID, stable across renames |
| `pipeline_slug` | `my-app` | Per-organization |
| `pipeline_id` | UUID | Stable across renames |
| `build_number` | `4231` | Per-pipeline integer |
| `build_branch` | `main` | Refs without the `refs/heads/` prefix |
| `build_tag` | `v1.4.2` | Set only on tag builds |
| `build_commit` | `9e2c1ab4...` | Full SHA |
| `build_source` | `webhook` / `api` / `schedule` / `ui` | How the build was triggered |
| `step_key` | `deploy-prod` | Empty string when not set |
| `job_id` | UUID | One per job (not per step) |
| `agent_id` | UUID | The agent that ran the job |
| `runner_environment` | `buildkite-hosted` / `self-hosted` | Useful for tightening trust to hosted runners only |

## Audience

The `aud` claim is set by the `--audience` flag passed to `buildkite-agent oidc request-token`. It must exactly match the audience configured on the verifying side (e.g. an AWS IAM identity provider, a GCP workload identity pool provider, or a Buildkite Packages registry URL). Mismatches reject the token before any claim matching happens.

Conventional audience values:

| Verifier | Audience |
|---|---|
| AWS STS | `sts.amazonaws.com` |
| GCP WIF | `https://iam.googleapis.com/projects/<num>/locations/global/workloadIdentityPools/<pool>/providers/<provider>` |
| HashiCorp Vault | The Vault JWT auth role's `bound_audiences` value |
| Buildkite Packages | The registry URL, e.g. `https://packages.buildkite.com/my-org/my-registry` |

## Lifetime

The default token lifetime is 600 seconds. Override with `--lifetime` up to a per-organization maximum.

## What this reference does not cover

- Setting up the verifier (IAM provider, GCP pool, Vault role) — owned by the **buildkite-secure-delivery** skill.
- The CLI flag surface of `buildkite-agent oidc request-token` — see **buildkite-agent-runtime**.
- Token signing keys, rotation, or key discovery URLs — owned by **buildkite-secure-delivery**.

This file exists so that an agent writing a trust policy can quote the subject and claim shape correctly without inventing fields from training data.
