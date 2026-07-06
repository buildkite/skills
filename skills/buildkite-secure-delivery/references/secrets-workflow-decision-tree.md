# Secrets workflow decision tree

Expanded form of the table in `SKILL.md`. Pick a row by answering the questions in order.

## Question 1: Buildkite-hosted agent, or self-hosted?

### Buildkite-hosted

Only one secret mechanism works: **Buildkite secrets** (cluster-scoped, encrypted at rest, auto-redacted). External secret-store plugins that require IAM credentials on the host are not viable, because the host is managed.

Workflow:

1. Create the secret on the cluster (Agents → cluster → Secrets → New Secret).
2. Reference it from the pipeline:

   ```yaml
   steps:
     - command: scripts/deploy.sh
       secrets:
         - DEPLOY_TOKEN
   ```

3. The value is injected as `$DEPLOY_TOKEN` only into the step that declares it.

OIDC is still preferred where the target supports it. For ECR, GCR, Azure Container Registry, or any cloud target with a federated identity option, request a token in the step and skip the stored secret entirely.

Minimum agent version for Buildkite secrets: **3.106.0**.

### Self-hosted

Go to Question 2.

## Question 2: Does the secret already live in an external secret store?

### Yes — AWS Secrets Manager or SSM Parameter Store

Use OIDC + the `aws-ssm` plugin (or `aws-secrets-manager` plugin). No copies of the secret outside source-of-truth, and CloudTrail records every fetch.

```yaml
steps:
  - label: "Deploy"
    plugins:
      - aws-assume-role-with-web-identity#v1.2.0:
          role-arn: arn:aws:iam::012345678910:role/deploy-role
          session-tags:
            - organization_slug
            - pipeline_slug
      - aws-ssm#v1.0.0:
          parameters:
            DEPLOY_KEY: /deploy/key
```

### Yes — HashiCorp Vault

Use OIDC-to-Vault via the `vault-secrets` plugin. Bind the Vault JWT auth role to the Buildkite issuer with `bound_subject` matching the org/pipeline.

### Yes — GCP Secret Manager

Use the `gcp-workload-identity-federation` plugin to mint a short-lived access token, then `gcloud secrets versions access` in the command.

### No — secret exists nowhere else yet

Go to Question 3.

## Question 3: Is the secret stable across pipelines, or computed inside a job?

### Stable

Create it as a **Buildkite secret on the cluster**, even on self-hosted. This is the recommended fallback when no external secret store is in play. Cluster-scoped, encrypted, auto-redacted.

If a Buildkite secret is not an option (older agent version, strict tenancy requirement), the documented fallback is an `environment` hook on the agent that exports the value with a pipeline-slug guard:

```bash
# /etc/buildkite-agent/hooks/environment
set -euo pipefail
case "$BUILDKITE_PIPELINE_SLUG" in
  deploy-prod) export DEPLOY_TOKEN="$(cat /etc/secrets/deploy-prod-token)" ;;
esac
```

This pattern requires the secret file to be readable only by the agent user and a pipeline-slug guard to prevent unrelated pipelines on the same agent from reading it.

### Computed inside a job

A secret derived at runtime (a temporary credential exchanged via OIDC, a one-time PAT minted from a GitHub App) bypasses the agent's auto-redaction list because the agent never saw the value at startup. Register it explicitly before any code path that might log it:

```bash
DEPLOY_TOKEN="$(./mint-token.sh)"
buildkite-agent redactor add --format=plain <<< "$DEPLOY_TOKEN"
```

After that call, the value is redacted from subsequent log output for the rest of the step.

## Leaked secret in a log

If a secret has already appeared in a build log:

1. **Rotate the secret immediately.** Log redaction does not retroactively scrub existing log content; the value must be assumed compromised.
2. **Add the new (or any related) value to `buildkite-agent redactor add` for the next run.**
3. For historical log scrubbing, contact `security@buildkite.com` — log mutation is not user-controllable.
4. **Audit downstream copies.** Logs are often shipped to log aggregators, S3, or alerting systems; the leak surface extends beyond Buildkite.

## Why per-step scoping matters

A pipeline-global `secrets:` block injects the value into every job's environment. A test job that imports a third-party library can exfiltrate any env var; if `PROD_DEPLOY_TOKEN` is in that env, the third-party library has it. Per-step scoping reduces the blast radius to the one step that legitimately needs the credential.
