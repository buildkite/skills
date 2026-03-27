---
name: buildkite-secure-delivery
description: >
  This skill should be used when the user asks to "publish to package registry",
  "push a Docker image", "set up OIDC authentication", "request an OIDC token",
  "authenticate without static credentials", "set up SLSA provenance",
  "generate attestation", "sign pipelines", "verify pipeline signatures",
  or "secure the supply chain".
  Also use when the user mentions OIDC, SLSA, provenance, attestation, cosign,
  JWKS, pipeline signing, pipeline verification, packages.buildkite.com,
  Package Registry, artifact signing, or asks about credential-free publishing,
  supply chain security, or secure delivery in Buildkite.
---

# Buildkite Secure Delivery

Secure delivery covers the end-to-end flow of publishing artifacts with zero static credentials and proving supply chain integrity. This skill teaches OIDC-based authentication, Package Registry publishing, SLSA provenance attestation, and pipeline signing with JWKS.

## Quick Start

Build, authenticate via OIDC, and push a Docker image — no static credentials:

```yaml
steps:
  - key: "docker-publish"
    label: ":docker: Build & Push"
    commands:
      - docker build --tag packages.buildkite.com/my-org/my-registry/my-app:latest .
      - buildkite-agent oidc request-token --audience "https://packages.buildkite.com/my-org/my-registry" --lifetime 300 | docker login packages.buildkite.com/my-org/my-registry --username buildkite --password-stdin
      - docker push packages.buildkite.com/my-org/my-registry/my-app:latest
    plugins:
      - generate-provenance-attestation#v1.1.0:
          artifacts: "my-app:latest"
          attestation_name: "docker-attestation.json"
```

This single step authenticates with a short-lived OIDC token (5 minutes), pushes the image, and generates a SLSA provenance attestation. No API keys or registry passwords stored anywhere.

> For `buildkite-agent oidc request-token` flag details, see the **buildkite-agent-runtime** skill.

## OIDC Authentication

OpenID Connect (OIDC) eliminates static credentials from pipelines. Instead of storing long-lived API keys or passwords, each job requests a short-lived JWT from Buildkite and exchanges it with external services.

### How It Works

1. A pipeline step calls `buildkite-agent oidc request-token`
2. The Buildkite backend issues a signed JWT containing build metadata (org, pipeline, branch, commit, step)
3. The external service (cloud provider, registry) validates the JWT against Buildkite's OIDC provider
4. If the token's claims match the service's trust policy, access is granted

The token issuer is always `https://agent.buildkite.com`. Tokens are short-lived (default 5 minutes) and scoped to a single job.

### Token Claims

Every OIDC token contains these claims:

```json
{
  "iss": "https://agent.buildkite.com",
  "sub": "organization:acme-inc:pipeline:deploy-app:ref:refs/heads/main:commit:9f3182061f1e:step:build",
  "aud": "https://packages.buildkite.com/acme-inc/docker-registry",
  "iat": 1669014898,
  "nbf": 1669014898,
  "exp": 1669015198,
  "organization_slug": "acme-inc",
  "pipeline_slug": "deploy-app",
  "build_number": 42,
  "build_branch": "main",
  "build_tag": "",
  "build_commit": "9f3182061f1e2cca4702c368cbc039b7dc9d4485",
  "step_key": "build",
  "job_id": "0184990a-477b-4fa8-9968-496074483cee",
  "agent_id": "0184990a-4782-42b5-afc1-16715b10b8ff",
  "build_source": "webhook",
  "runner_environment": "buildkite-hosted"
}
```

Key claims for trust policies:

| Claim | Use |
|-------|-----|
| `organization_slug` | Restrict to a specific Buildkite organization |
| `pipeline_slug` | Restrict to a specific pipeline |
| `build_branch` | Restrict to specific branches (e.g., `main` only for deploys) |
| `step_key` | Restrict to specific step within a pipeline |
| `runner_environment` | Distinguish hosted vs self-hosted agents |

### OIDC with Buildkite Package Registry

Authenticate to Buildkite Package Registry using OIDC — the audience must exactly match the registry URL:

```bash
buildkite-agent oidc request-token \
  --audience "https://packages.buildkite.com/{org-slug}/{registry-slug}" \
  --lifetime 300 \
  | docker login packages.buildkite.com/{org-slug}/{registry-slug} \
      --username buildkite --password-stdin
```

The `--audience` value must use `https://` and match the registry URL exactly. The username is always `buildkite`. The token acts as the password.

### OIDC with AWS

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

### OIDC with GCP

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

### OIDC with Azure

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

### Scoping OIDC Policies

Always restrict OIDC trust policies to the minimum required scope. Overly broad policies (e.g., any pipeline in the org) defeat the purpose of OIDC.

**Good — scoped to pipeline and branch:**
```
sub: organization:acme-inc:pipeline:deploy-prod:ref:refs/heads/main:*
```

**Bad — any pipeline in the org:**
```
sub: organization:acme-inc:*
```

Use `pipeline_slug` and `build_branch` conditions for cloud provider trust policies. For production deployments, require `build_branch: main` (or the release branch).

## Package Registry

Buildkite Package Registry hosts packages across multiple ecosystems with OIDC-native authentication. Registries are scoped to an organization and accessed at `packages.buildkite.com/{org-slug}/{registry-slug}`.

### Supported Ecosystems

| Ecosystem | Registry type | Publish tool | Auth method |
|-----------|--------------|-------------|-------------|
| Docker / OCI | OCI | `docker push` | `docker login` with OIDC token |
| npm | JavaScript | `npm publish` | `.npmrc` with OIDC token |
| Helm (OCI) | Helm OCI | `helm push` | `helm registry login` with OIDC token |
| Python (PyPI) | Python | `curl -F file=@pkg.tar.gz` | Bearer token header |
| Ruby (Gems) | Ruby | `curl -F file=@gem.gem` | Bearer token header |
| Terraform | Terraform | `curl -F file=@module.tgz` | Bearer token header |
| Debian / Ubuntu | Debian | `curl -F file=@pkg.deb` | Bearer token header |
| Alpine (apk) | Alpine | `curl -F file=@pkg.apk` | Bearer token header |
| RPM | RPM | `curl -F file=@pkg.rpm` | Bearer token header |
| Generic | Generic | `curl -F file=@artifact` | Bearer token header |

### Docker / OCI Publishing

The most common pattern — build, authenticate via OIDC, push:

```yaml
steps:
  - label: ":docker: Publish Image"
    commands:
      - docker build --tag packages.buildkite.com/acme-inc/docker-images/web-app:${BUILDKITE_BUILD_NUMBER} .
      - buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/docker-images" --lifetime 300 | docker login packages.buildkite.com/acme-inc/docker-images --username buildkite --password-stdin
      - docker push packages.buildkite.com/acme-inc/docker-images/web-app:${BUILDKITE_BUILD_NUMBER}
```

Tag images with `${BUILDKITE_BUILD_NUMBER}` or the git SHA for traceability. Avoid `latest` tags in production — they're not immutable.

### npm Publishing

Configure `.npmrc` with the registry URL and authenticate with an OIDC token:

```yaml
steps:
  - label: ":npm: Publish Package"
    commands:
      - export OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/npm-packages" --lifetime 300)
      - |
        cat > .npmrc << EOF
        //packages.buildkite.com/acme-inc/npm-packages/:_authToken=${OIDC_TOKEN}
        registry=https://packages.buildkite.com/acme-inc/npm-packages/
        EOF
      - npm publish
```

### Helm Chart Publishing (OCI)

Push Helm charts to a Buildkite Helm OCI registry:

```yaml
steps:
  - label: ":helm: Publish Chart"
    commands:
      - helm package ./chart
      - buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/helm-charts" --lifetime 300 | helm registry login packages.buildkite.com/acme-inc/helm-charts --username buildkite --password-stdin
      - helm push my-chart-1.0.0.tgz oci://packages.buildkite.com/acme-inc/helm-charts
```

### Python / Ruby / Generic Publishing

For ecosystems that use direct HTTP upload, request an OIDC token and pass it as a Bearer token:

```yaml
steps:
  - label: ":python: Publish Package"
    commands:
      - export OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/python-packages" --lifetime 300)
      - python -m build
      - curl -X POST "https://api.buildkite.com/v2/packages/organizations/acme-inc/registries/python-packages/packages" -H "Authorization: Bearer ${OIDC_TOKEN}" -F "file=@dist/my-package-1.0.0.tar.gz"
```

The same pattern applies to Ruby gems, Debian packages, RPMs, Alpine packages, Terraform modules, and generic artifacts — change the file path and registry slug.

### Terraform Module Publishing

Terraform module filenames must follow the naming convention `terraform-{provider}-{module}-{major.minor.patch}.tgz`:

```yaml
steps:
  - label: ":terraform: Publish Module"
    commands:
      - export OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/terraform-modules" --lifetime 300)
      - tar czf terraform-buildkite-pipeline-1.0.0.tgz -C modules .
      - curl -X POST "https://api.buildkite.com/v2/packages/organizations/acme-inc/registries/terraform-modules/packages" -H "Authorization: Bearer ${OIDC_TOKEN}" -F "file=@terraform-buildkite-pipeline-1.0.0.tgz"
```

### Installing from Package Registry

Pull packages using the same OIDC pattern. For Docker images:

```bash
buildkite-agent oidc request-token \
  --audience "https://packages.buildkite.com/acme-inc/docker-images" \
  --lifetime 300 \
  | docker login packages.buildkite.com/acme-inc/docker-images \
      --username buildkite --password-stdin

docker pull packages.buildkite.com/acme-inc/docker-images/web-app:42
```

For npm, configure `.npmrc` with the read token. For Helm, use `helm registry login` then `helm pull`.

## SLSA Provenance

SLSA (Supply-chain Levels for Software Artifacts) provenance records what was built, when, by whom, and from which source. Buildkite supports generating Build Level 1 attestations that are cryptographically signed and attached to published packages.

### How It Works

1. A build step produces an artifact (Docker image, gem, binary)
2. The `generate-provenance-attestation` plugin captures build metadata and generates a signed attestation
3. The `publish-to-packages` plugin uploads the artifact and its attestation together to Package Registry
4. Consumers verify the attestation to confirm the artifact's origin

### Generating Attestations

Use the `generate-provenance-attestation` plugin in the build step:

```yaml
steps:
  - label: ":hammer: Build"
    key: "build"
    command: "gem build my-library.gemspec"
    artifact_paths: "my-library-*.gem"
    plugins:
      - generate-provenance-attestation#v1.1.0:
          artifacts: "my-library-*.gem"
          attestation_name: "build-attestation.json"
```

Plugin parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `artifacts` | Yes | Glob pattern matching the artifacts to attest |
| `attestation_name` | Yes | Filename for the generated attestation JSON |

The attestation captures:
- **Builder**: Buildkite agent identity and environment
- **Source**: Repository URL, branch, commit SHA
- **Build**: Pipeline slug, build number, step key, timestamp
- **Materials**: Input artifacts and their digests (SHA-256)

### Publishing with Attestations

Use the `publish-to-packages` plugin to upload artifacts along with their attestations:

```yaml
steps:
  - label: ":hammer: Build"
    key: "build"
    command: "gem build my-library.gemspec"
    artifact_paths: "my-library-*.gem"
    plugins:
      - generate-provenance-attestation#v1.1.0:
          artifacts: "my-library-*.gem"
          attestation_name: "build-attestation.json"

  - label: ":package: Publish"
    depends_on: "build"
    plugins:
      - publish-to-packages#v2.2.0:
          artifacts: "my-library-*.gem"
          registry: "acme-inc/ruby-gems"
          attestations:
            - "build-attestation.json"
```

`publish-to-packages` plugin parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `artifacts` | Yes | Glob pattern matching artifacts to publish |
| `registry` | Yes | Target registry in `{org-slug}/{registry-slug}` format |
| `attestations` | No | List of attestation files to attach to the package |

### SLSA Build Levels

| Level | Requirement | Buildkite support |
|-------|-------------|-------------------|
| Level 1 | Provenance exists and is signed | `generate-provenance-attestation` plugin |
| Level 2 | Hosted build service, authenticated provenance | Buildkite Hosted Agents + plugin |
| Level 3 | Hardened build platform, non-falsifiable provenance | Requires additional controls (pipeline signing, isolated agents) |

The `generate-provenance-attestation` plugin satisfies SLSA Build Level 1. To move toward Level 2 and Level 3, combine with Buildkite Hosted Agents and pipeline signing (see below).

## Pipeline Signing (JWKS)

Pipeline signing ensures that the steps an agent runs are exactly the steps that were uploaded. When enabled, agents cryptographically sign pipeline definitions during upload and verify signatures before executing jobs. If an agent detects a tampered or unsigned step, it refuses to run the job.

### How It Works

1. Generate a JWKS key pair (private key for signing, public key for verification)
2. Configure **uploading agents** with the signing key — they sign steps during `pipeline upload`
3. Configure **executing agents** with the verification key — they verify signatures before running jobs
4. Optionally start in `warn` mode to identify unsigned pipelines before enforcing `block`

### Step 1: Generate JWKS Keys

```bash
buildkite-agent tool keygen --alg EdDSA --key-id my-signing-key
```

This outputs two files in the current directory:
- `EdDSA-my-signing-key-private.json` — private key (signing)
- `EdDSA-my-signing-key-public.json` — public key (verification)

Store the private key securely. Distribute only the public key to verification-only agents.

### Step 2: Configure Agents

**Agents that upload and execute pipelines** (both signing and verification):

```ini
# buildkite-agent.cfg
signing-jwks-file=/etc/buildkite-agent/EdDSA-my-signing-key-private.json
signing-jwks-key-id=my-signing-key
verification-jwks-file=/etc/buildkite-agent/EdDSA-my-signing-key-public.json
```

**Agents that only execute** (verification only — cannot upload new steps):

```ini
# buildkite-agent.cfg
verification-jwks-file=/etc/buildkite-agent/EdDSA-my-signing-key-public.json
```

**Verification failure behavior** controls what happens when a job's signature is invalid or missing:

| Value | Behavior |
|-------|----------|
| `block` (default) | Agent refuses to run the job |
| `warn` | Agent logs a warning but runs the job anyway |

Set during rollout:

```ini
verification-failure-behavior=warn
```

### Step 3: Gradual Rollout

Rolling out pipeline signing safely:

1. **Generate keys** — create the JWKS key pair
2. **Deploy signing** — configure uploading agents with `signing-jwks-file` and `signing-jwks-key-id`
3. **Deploy verification in warn mode** — configure executing agents with `verification-jwks-file` and `verification-failure-behavior=warn`
4. **Monitor warnings** — check agent logs for unsigned or invalid pipeline warnings
5. **Fix unsigned pipelines** — ensure all pipelines route through agents with signing keys, or sign Pipeline Settings steps manually
6. **Switch to block** — remove `verification-failure-behavior=warn` (default is `block`)

### Signing Steps in Pipeline Settings

Steps defined in the Buildkite UI (Pipeline Settings) are not signed by an agent. Sign them manually:

```bash
buildkite-agent tool sign \
  --graphql-token $BUILDKITE_GRAPHQL_TOKEN \
  --jwks-file /path/to/private-key.json \
  --jwks-key-id my-signing-key \
  --organization-slug acme-inc \
  --pipeline-slug deploy-prod \
  --update
```

This downloads the pipeline definition from Buildkite, signs each step, and uploads the signed version. Re-run after any change to Pipeline Settings steps.

### Kubernetes Configuration

For the Buildkite Agent Stack for Kubernetes, mount JWKS keys as Kubernetes secrets:

```bash
kubectl create secret generic my-signing-key \
  --from-file='key'="./EdDSA-my-signing-key-private.json"

kubectl create secret generic my-verification-key \
  --from-file='key'="./EdDSA-my-signing-key-public.json"
```

Configure the agent stack values:

```yaml
config:
  agent-config:
    signing-jwks-file: key
    signing-jwks-key-id: my-signing-key
    signingJWKSVolume:
      name: buildkite-signing-jwks
      secret:
        secretName: my-signing-key

    verification-jwks-file: key
    verification-failure-behavior: warn
    verificationJWKSVolume:
      name: buildkite-verification-jwks
      secret:
        secretName: my-verification-key
```

Once all pipelines are signed, remove the `verification-failure-behavior: warn` line (defaults to `block`).

> For `buildkite-agent.cfg` configuration details, see the **buildkite-platform-engineering** skill.

## End-to-End Secure Publish Flow

A complete pipeline that builds, authenticates via OIDC, pushes to Package Registry, and generates SLSA provenance:

```yaml
steps:
  # Step 1: Build and attest
  - label: ":hammer: Build & Attest"
    key: "build"
    commands:
      - docker build --tag packages.buildkite.com/acme-inc/docker-images/web-app:${BUILDKITE_COMMIT:0:8} .
      - docker save packages.buildkite.com/acme-inc/docker-images/web-app:${BUILDKITE_COMMIT:0:8} -o web-app.tar
    artifact_paths:
      - "web-app.tar"
    plugins:
      - generate-provenance-attestation#v1.1.0:
          artifacts: "web-app.tar"
          attestation_name: "docker-attestation.json"

  # Step 2: Push to registry with attestation
  - label: ":rocket: Publish"
    key: "publish"
    depends_on: "build"
    commands:
      - buildkite-agent artifact download "web-app.tar" .
      - docker load -i web-app.tar
      - buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/docker-images" --lifetime 300 | docker login packages.buildkite.com/acme-inc/docker-images --username buildkite --password-stdin
      - docker push packages.buildkite.com/acme-inc/docker-images/web-app:${BUILDKITE_COMMIT:0:8}
    plugins:
      - publish-to-packages#v2.2.0:
          artifacts: "web-app.tar"
          registry: "acme-inc/docker-images"
          attestations:
            - "docker-attestation.json"

  # Step 3: Deploy (OIDC to cloud provider)
  - label: ":aws: Deploy to ECS"
    depends_on: "publish"
    command: ./scripts/deploy-ecs.sh
    env:
      AWS_DEFAULT_REGION: us-east-1
    plugins:
      - aws-assume-role-with-web-identity#v1.2.0:
          role-arn: arn:aws:iam::012345678910:role/ecs-deploy-role
          session-tags:
            - organization_slug
            - pipeline_slug
```

This pipeline demonstrates the full secure delivery chain:
- **Build** produces an artifact and generates provenance attestation
- **Publish** authenticates to Package Registry via OIDC (no static credentials), pushes the image, and attaches the SLSA attestation
- **Deploy** authenticates to AWS via OIDC and deploys the published image

### Ruby Gem Secure Publish Flow

A non-Docker example using the `publish-to-packages` plugin directly:

```yaml
steps:
  - label: ":ruby: Build Gem"
    key: "build-gem"
    command: "gem build my-library.gemspec"
    artifact_paths: "my-library-*.gem"
    plugins:
      - generate-provenance-attestation#v1.1.0:
          artifacts: "my-library-*.gem"
          attestation_name: "gem-attestation.json"

  - label: ":package: Publish Gem"
    depends_on: "build-gem"
    plugins:
      - publish-to-packages#v2.2.0:
          artifacts: "my-library-*.gem"
          registry: "acme-inc/ruby-gems"
          attestations:
            - "gem-attestation.json"
```

## Security Checklist

Use this checklist when reviewing a pipeline's security posture:

- [ ] **No static credentials** — all authentication uses OIDC tokens, never stored API keys or passwords
- [ ] **Audience scoped** — OIDC `--audience` matches the exact target service URL
- [ ] **Short-lived tokens** — `--lifetime` set to 300 seconds (5 minutes) or less
- [ ] **Trust policies scoped** — cloud provider policies restrict by `pipeline_slug`, `build_branch`, and `organization_slug`
- [ ] **Provenance attached** — published artifacts include SLSA attestation via `generate-provenance-attestation` plugin
- [ ] **Pipeline signed** — agents configured with JWKS signing and verification keys
- [ ] **Verification enforced** — `verification-failure-behavior` set to `block` (not `warn`) in production
- [ ] **Secrets redacted** — any dynamically-retrieved secrets added to the log redactor

> For `buildkite-agent redactor add` syntax, see the **buildkite-agent-runtime** skill.
> For `secrets:` pipeline YAML syntax, see the **buildkite-pipelines** skill.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| OIDC `--audience` doesn't match registry URL exactly | Token rejected — `invalid_grant` or `audience mismatch` error | Ensure `--audience` is `https://packages.buildkite.com/{org}/{registry}` with exact org and registry slugs |
| Using static API keys instead of OIDC | Credentials leaked in logs or compromised via secret rotation failures | Replace all `docker login -p $API_KEY` with the OIDC pipe pattern |
| `--lifetime` too long (e.g., 3600) | Token valid for an hour — if leaked, attacker has extended access | Set `--lifetime 300` (5 minutes) — enough for push, short enough to limit blast radius |
| Missing `generate-provenance-attestation` plugin | No SLSA attestation attached to published artifacts — compliance gaps | Add the plugin to every build step that produces publishable artifacts |
| Skipping `warn` phase during signing rollout | Unsigned pipelines immediately blocked — builds break across the org | Deploy with `verification-failure-behavior=warn` first, fix warnings, then switch to `block` |
| OIDC trust policy too broad (`sub: organization:*`) | Any pipeline in the org can assume the cloud role — no isolation | Scope trust policy to specific `pipeline_slug` and `build_branch` |
| Forgetting to sign Pipeline Settings steps | Steps defined in UI are unsigned — verification-enabled agents reject them | Run `buildkite-agent tool sign --update` for every pipeline with UI-defined steps |
| Terraform module filename doesn't follow convention | Package Registry rejects the upload with a naming error | Use the `terraform-{provider}-{module}-{major.minor.patch}.tgz` format |

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [OIDC with Buildkite Pipelines](https://buildkite.com/docs/pipelines/security/oidc) — overview of OIDC configuration and trust policies
- [OIDC with Package Registries](https://buildkite.com/docs/package-registries/security/oidc) — OIDC authentication for all registry types
- [OIDC with AWS](https://buildkite.com/docs/pipelines/security/oidc/aws) — AWS IAM federation setup
- [SLSA Provenance](https://buildkite.com/docs/package-registries/security/slsa-provenance) — attestation generation and verification
- [Signed Pipelines](https://buildkite.com/docs/agent/v3/signed-pipelines) — JWKS key generation, agent configuration, and rollout
- [Package Registries Overview](https://buildkite.com/docs/package-registries) — supported ecosystems, registry creation, and management
- [Buildkite Agent OIDC CLI](https://buildkite.com/docs/agent/v3/cli-oidc) — `buildkite-agent oidc` command reference
