# OIDC Cloud Provider Integration

## OIDC with AWS

Request an OIDC token for AWS, then assume an IAM role using web identity federation:

```bash
buildkite-agent oidc request-token --audience sts.amazonaws.com
```

Use the `aws-assume-role-with-web-identity` plugin for a streamlined pipeline step:

```yaml
steps:
  - label: ":aws: Deploy"
    command: ./scripts/deploy.sh
    env:
      AWS_DEFAULT_REGION: us-east-1
      AWS_REGION: us-east-1
    plugins:
      - aws-assume-role-with-web-identity#v1.2.0:
          role-arn: arn:aws:iam::012345678910:role/my-deploy-role
          session-tags:
            - organization_slug
            - pipeline_slug
```

AWS IAM trust policy requirements:
- Set the OIDC provider to `https://agent.buildkite.com`
- Set the audience to `sts.amazonaws.com`
- Add conditions on `sub` or individual claims (`organization_slug`, `pipeline_slug`, `build_branch`) to restrict which pipelines can assume the role

To include AWS session tags in the token, use `--aws-session-tag`:

```bash
buildkite-agent oidc request-token \
  --audience sts.amazonaws.com \
  --aws-session-tag "organization_slug,organization_id"
```

This adds an `https://aws.amazon.com/tags` claim with `principal_tags` for use in tag-based IAM policies.

## OIDC with GCP

Use GCP Workload Identity Federation to exchange Buildkite OIDC tokens for GCP credentials:

1. Create a Workload Identity Pool and OIDC Provider:

```bash
gcloud iam workload-identity-pools create buildkite-pool \
  --display-name "Buildkite Pool"

gcloud iam workload-identity-pools providers create-oidc buildkite-provider \
  --workload-identity-pool buildkite-pool \
  --issuer-uri "https://agent.buildkite.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.pipeline_slug=assertion.pipeline_slug,attribute.organization_slug=assertion.organization_slug"
```

2. Grant the pool's service account the necessary IAM roles
3. Request a token in the pipeline step with the pool's audience:

```bash
buildkite-agent oidc request-token \
  --audience "//iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/buildkite-pool/providers/buildkite-provider"
```

Use attribute conditions on `pipeline_slug` or `organization_slug` to restrict which pipelines can authenticate.

## OIDC with Azure

Azure supports Workload Identity Federation with Buildkite OIDC:

1. Register an app in Azure AD with federated credentials
2. Set the issuer to `https://agent.buildkite.com`
3. Set the subject to the `sub` claim pattern for the target pipeline
4. Request a token in the pipeline step:

```bash
buildkite-agent oidc request-token \
  --audience "api://AzureADTokenExchange"
```

Use the Azure CLI or SDK to exchange the token for an access token.
