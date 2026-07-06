# OIDC subject claim patterns

Per-provider cookbook for `agent.buildkite.com` OIDC. Snippets are taken from the official Buildkite docs cited in each section. Use these as starting points; verify against the current docs before applying.

## AWS

Provider URL `https://agent.buildkite.com`, audience `sts.amazonaws.com`. Custom trust policy (verbatim from `pipelines/security/oidc/aws.md`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/agent.buildkite.com"
            },
            "Action": [
                "sts:TagSession",
                "sts:AssumeRoleWithWebIdentity"
            ],
            "Condition": {
                "StringLike": {
                    "agent.buildkite.com:sub": "organization:ORGANIZATION_SLUG:pipeline:PIPELINE_SLUG:ref:REF:commit:BUILD_COMMIT:step:STEP_KEY"
                },
                "StringEquals": {
                    "agent.buildkite.com:aud": "sts.amazonaws.com",
                    "aws:RequestTag/organization_slug": "ORGANIZATION_SLUG",
                    "aws:RequestTag/organization_id": "ORGANIZATION_ID",
                    "aws:RequestTag/pipeline_slug": "PIPELINE_SLUG"
                },
                "IpAddress": {
                    "aws:SourceIp": [
                        "AGENT_PUBLIC_IP_ONE",
                        "AGENT_PUBLIC_IP_TWO"
                    ]
                }
            }
        }
    ]
}
```

Pipeline plugin block (verbatim from the same doc):

```yaml
steps:
  - label: ":aws: Deploy to Production"
    key: deploy-to-production
    command: echo "Example Deploy Key equals \$EXAMPLE_DEPLOY_KEY"
    env:
      AWS_DEFAULT_REGION: us-east-1
      AWS_REGION: us-east-1
    plugins:
      - aws-assume-role-with-web-identity#v1.2.0:
          role-arn: arn:aws:iam::012345678910:role/example-pipeline-oidc-for-ssm
          session-tags:
            - organization_slug
            - organization_id
            - pipeline_slug
      - aws-ssm#v1.0.0:
          parameters:
            EXAMPLE_DEPLOY_KEY: /pipelines/example-pipeline/oidc-for-ssm/example-deploy-key
```

Notes from the AWS doc:

- The `sub` claim is required by AWS in every trust policy that federates against a Buildkite OIDC provider. Use it to scope to the Buildkite organization (`organization:acme-inc:*`), then narrow further with `aws:RequestTag` conditions on immutable UUIDs.
- The `IpAddress` condition is defense-in-depth against a stolen OIDC token being exchanged from outside the agent fleet's known egress IPs.
- Including `build_branch` is supported but spoofable mid-build — a later step can check out another branch.

## Azure

Issuer `https://agent.buildkite.com`, audience `api://AzureADTokenExchange` (or `api://AzureADTokenExchangeUSGov` / `api://AzureADTokenExchangeChina`). Federated Identity Credential fields (from `pipelines/security/oidc/azure.md`):

| Field | Value |
|---|---|
| Issuer | `https://agent.buildkite.com` |
| Subject identifier | Pipeline UUID (default), or the UUID matching `--subject-claim` if overridden |
| Audience | `api://AzureADTokenExchange` |

Request a token in the step:

```bash
BUILDKITE_OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "api://AzureADTokenExchange")
```

Authenticate with the Azure CLI:

```bash
az login --service-principal \
  --username "$ARM_CLIENT_ID" \
  --tenant "$ARM_TENANT_ID" \
  --federated-token "$BUILDKITE_OIDC_TOKEN"
```

Allowed subject-claim values (from the Azure doc):

| Claim | Description | Scope |
|---|---|---|
| `pipeline_id` | Pipeline UUID (default) | A single pipeline |
| `cluster_id` | Cluster UUID | All pipelines in a cluster |
| `queue_id` | Queue UUID | All pipelines targeting a queue |
| `organization_id` | Organization UUID | All pipelines in the org |
| `build_id` | Build UUID | A single build (one-time use) |
| `job_id` | Job UUID | A single job (one-time use) |
| `agent_id` | Agent UUID | A single agent |

Azure matches on the `sub` claim only — it cannot restrict by branch or build source. Mitigate by splitting CI and CD pipelines and scoping RBAC tightly.

## GCP

Plugin: [`gcp-workload-identity-federation`](https://github.com/buildkite-plugins/gcp-workload-identity-federation-buildkite-plugin).

Workload Identity Pool provider configuration uses `https://agent.buildkite.com` as the issuer. Map the OIDC subject claim to a Google service account principal via an attribute mapping (`google.subject = assertion.sub`).

Request and use the token:

```yaml
steps:
  - label: ":gcloud: Deploy"
    plugins:
      - gcp-workload-identity-federation#v1.0.0:
          audience: //iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
          service-account: deploy@PROJECT_ID.iam.gserviceaccount.com
```

Verify the plugin version and parameter names against the plugin README before use.

## HashiCorp Vault

Plugin: [`vault-secrets`](https://buildkite.com/resources/plugins/buildkite-plugins/vault-secrets-buildkite-plugin/).

Configure a Vault JWT auth role bound to the `agent.buildkite.com` issuer. The role's `bound_subject` matches the `sub` claim — usually `organization:ORG_SLUG:pipeline:PIPELINE_SLUG:*`, narrowed via `bound_claims` on `organization_id` / `pipeline_id` UUIDs.

```yaml
steps:
  - label: ":vault: Fetch deploy creds"
    plugins:
      - vault-secrets#v2.0.0:
          server: https://vault.example.com
          path: secret/data/deploy
          auth: jwt
          role: buildkite-deploy
```

## Generic OIDC

Any RFC-compliant consumer can verify Buildkite-issued tokens. Discovery endpoint: `https://agent.buildkite.com/.well-known/openid-configuration`.

Request a token with a custom audience and subject claim:

```bash
TOKEN=$(buildkite-agent oidc request-token \
  --audience "https://your-service.example.com" \
  --subject-claim cluster_id \
  --lifetime 600)
```

The token's claims always include the immutable identifier corresponding to the `--subject-claim` value, plus the audience set by `--audience`. Configure the consumer to match on:

- `iss` = `https://agent.buildkite.com`
- `aud` = the audience configured above
- `sub` = the immutable UUID expected for the scope

## Choosing a subject claim

Prefer immutable identifiers over slugs and branch names. Renaming a pipeline slug, for example, silently breaks any trust policy that conditioned on it. The default `sub` is structured for org-wide scoping with `RequestTag`-style narrowing; override to `cluster_id`, `queue_id`, or `pipeline_id` when a single UUID match is sufficient and simpler than tag conditions.
