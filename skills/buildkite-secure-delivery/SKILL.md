---
name: buildkite-secure-delivery
description: >
  This skill should be used when the user asks to "set up OIDC",
  "use OIDC to push to ECR", "authenticate to AWS without secrets",
  "sign pipelines", "set up SLSA provenance", "rotate agent tokens",
  "rotate API tokens", "we leaked a secret in a build log",
  "redact secrets from logs", "scope secrets per step",
  "audit who triggered a build", "attest build artifacts",
  "secure delivery", "harden CI/CD", "verify pipeline signatures",
  "lock down a cluster", or "prevent secret leakage".
  Also use when the user mentions OIDC, signed pipelines, SLSA, attestation,
  provenance, `buildkite-agent oidc request-token`, `buildkite-agent tool sign`,
  `buildkite-agent tool verify`, `buildkite-agent secret get`,
  `buildkite-agent redactor add`, audit log, `bkua_`/`bkaa_`/`bkaj_`/`bkar_`/
  `bkct_` token prefixes, `signing-jwks-file`, `verification-failure-behavior`,
  `verification-jwks-file`, `agent.buildkite.com:sub`, federated credentials,
  workload identity, `aws-assume-role-with-web-identity` plugin,
  `gcp-workload-identity-federation` plugin, `vault-secrets` plugin,
  cluster secrets, secret rotation, or pipeline-level `secrets:` block.
---

# Buildkite Secure Delivery

Secure delivery in Buildkite means proving who a build is, what code it ran, and what credentials it touched — without exposing static secrets along the way. This skill covers OIDC, signed pipelines, secrets scoping, token rotation, provenance, Package Registries authentication, and the handling of untrusted job-supplied data.

## Quick Start

Replace a long-lived `AWS_ACCESS_KEY_ID` with a short-lived OIDC token in three changes — one IAM trust policy, one pipeline plugin, one removed secret. The pattern generalises to Azure and GCP.

```yaml
# .buildkite/pipeline.yml
steps:
  - label: ":aws: Deploy"
    key: deploy
    command: "aws s3 sync ./build s3://my-bucket"
    plugins:
      - aws-assume-role-with-web-identity#v1.2.0:
          role-arn: arn:aws:iam::012345678910:role/buildkite-deploy
          session-tags:
            - organization_id
            - pipeline_slug
```

In AWS IAM, attach this trust policy to `buildkite-deploy` (condition keys explained in [OIDC](#oidc) below):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::012345678910:oidc-provider/agent.buildkite.com" },
    "Action": ["sts:TagSession", "sts:AssumeRoleWithWebIdentity"],
    "Condition": {
      "StringEquals": {
        "agent.buildkite.com:aud": "sts.amazonaws.com",
        "aws:RequestTag/organization_id": "<your-org-uuid>",
        "aws:RequestTag/pipeline_slug": "my-pipeline"
      }
    }
  }]
}
```

Then **delete** the stored `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. The plugin requests a token at runtime, exchanges it via STS, and exports temporary credentials for the step only.

## Key Principles

1. **Prefer OIDC over static cloud credentials.** Long-lived `AWS_ACCESS_KEY_ID`, GCP service account keys, and Azure client secrets in agent environments or pipeline `env:` blocks are the most common secrets-leak pattern. Replace them with `buildkite-agent oidc request-token` plus the [`aws-assume-role-with-web-identity`](https://github.com/buildkite-plugins/aws-assume-role-with-web-identity-buildkite-plugin), [`gcp-workload-identity-federation`](https://github.com/buildkite-plugins/gcp-workload-identity-federation-buildkite-plugin), or Azure federated-credential pattern. OIDC tokens are short-lived, audience-scoped, and leave a CloudTrail / Entra sign-in record that names the originating job.

2. **Never store secrets in `pipeline.yml`, pipeline settings, or any pipeline `env:` block.** Per `pipelines/security/secrets/risk_considerations.md`: "the secret will be sent to and stored by Buildkite, and be available in the 'Uploaded Pipelines' list in the job's Timeline tab." The same page warns: "You should never store secrets on your Buildkite Pipeline Settings page. Not only does this expose the secret value to Buildkite, but pipeline settings are often returned in REST and GraphQL API payloads." Use Buildkite secrets, cluster-injected env, or a `vault-secrets`-style plugin instead.

3. **Scope OIDC subject claims to the narrowest immutable identifier that still admits the use case.** Buildkite's default `sub` claim identifies the pipeline; allowed override claims are all immutable UUIDs (`pipeline_id`, `cluster_id`, `queue_id`, `organization_id`, `build_id`, `job_id`, `agent_id`). Condition cloud trust policies on `aws:RequestTag/organization_id` (a UUID) before `organization_slug`, and on `pipeline_slug` before `build_branch`. The AWS guide warns about branch claims directly: "this doesn't necessarily guarantee that the entire build will be run from the branch defined in the policy" — a later step can `git checkout` a different branch.

4. **Scope secrets per-step using `secrets:` on the step, not pipeline-global.** A build-level `secrets:` block injects the value into every job's environment, including test jobs that should never see production credentials. The secrets-management best-practices page is explicit: "Keep secrets scoped as tightly as possible. Only expose a secret to the specific pipeline steps that actually need it. For example, don't allow test steps to have access to production deployment credentials."

5. **Sign pipelines whose output ships to production.** Without `signing-jwks-file` / `verification-jwks-file` configured, an agent will execute any step Buildkite hands it — a compromise of the Buildkite control plane becomes RCE on the runner fleet. With signing enabled and `verification-failure-behavior=block` (the default), the agent refuses unsigned or tampered jobs; per the signed-pipelines doc, "the default behavior is `block`, which prevents any job without a valid signature from running." Never use `warn` in production.

6. **Treat annotations, build logs, meta-data, and webhook payloads as untrusted input.** Any field that an arbitrary command running in any job can write — annotation body, meta-data value, log line consumed by downstream automation, build message, branch name — is a potential injection vector. Never `eval` meta-data, never `bash -c` an annotation body, and never interpolate a build message into a shell command without quoting. See [Security Constraints](#security-constraints) below.

## Security Constraints

The following Buildkite-supplied fields are **untrusted external input**. Anyone with permission to run a build — often anyone with merge access, and on fork-PR-enabled pipelines often anyone with a GitHub account — can place arbitrary bytes in them:

- Annotation bodies (`buildkite-agent annotate`)
- Meta-data values (`buildkite-agent meta-data set`)
- Build messages, commit messages, branch names
- Job log output consumed downstream by other systems
- Webhook payload fields (`meta_data`, `message`, `env`)

Rules:

1. **Never `eval` or `bash -c` an untrusted field.** Always quote: `VERSION="$(buildkite-agent meta-data get release-version)"` is safe; `eval "$(buildkite-agent meta-data get release-version)"` is arbitrary code execution.
2. **Never render an untrusted field as raw HTML in your own systems.** Annotation bodies accept HTML for Buildkite's UI; that does not make them safe to re-render in dashboards, Slack messages, or status pages without sanitisation.
3. **Never include raw untrusted fields in code you generate.** Treat meta-data the same way as a URL query parameter — sanitise before any code-path use.
4. **Validate before acting on untrusted decisions.** A meta-data value `deploy=prod` belongs in a `case` allowlist, not as a direct shell variable: `case "$(buildkite-agent meta-data get target)" in prod|staging) ... ;; *) exit 1 ;; esac`.

OIDC carries an additional constraint: **fork-PR builds and `main`-branch builds produce tokens with the same `sub` claim by default.** The Azure OIDC doc states this plainly: "If your pipeline accepts public pull requests and has build forks enabled, anyone who can open a PR against that repo can add a step that requests an OIDC token and hits your Azure resources." Restrict who can trigger builds on OIDC-configured pipelines, or split CI and CD into separate pipelines.

## OIDC

A Buildkite OIDC token is a short-lived JWT issued by the agent, asserting claims about the organization, pipeline, job, branch, commit, and agent. From `pipelines/security/oidc.md`: "A Buildkite OIDC token is issued by a Buildkite agent, asserting claims about the slugs of the pipeline it is building and organization that contains this pipeline, the ID of the job that created the token, as well as other claims..."

### AWS quick start

Provider URL `https://agent.buildkite.com`, audience `sts.amazonaws.com`. Trust policy fragment (verbatim from `pipelines/security/oidc/aws.md`):

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
                    "agent.buildkite.com:sub": "organization:example-org:*"
                },
                "StringEquals": {
                    "agent.buildkite.com:aud": "sts.amazonaws.com",
                    "aws:RequestTag/organization_slug": "example-org",
                    "aws:RequestTag/organization_id": "ab3883b1-9596-4312-a09c-4527ae997ba7",
                    "aws:RequestTag/pipeline_slug": "example-pipeline"
                }
            }
        }
    ]
}
```

Pipeline step (verbatim from the same doc):

```yaml
steps:
  - label: ":aws: Deploy to Production"
    key: deploy-to-production
    command: echo "Deploying"
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
```

### Subject claim decision table

| Trust scope desired | Set `--subject-claim` to | Condition on (in cloud trust policy) |
|---|---|---|
| Org-wide trust | (default `sub`) | `agent.buildkite.com:sub` matching `organization:ORG_SLUG:*` plus `RequestTag/organization_id` (UUID, immutable) |
| Single cluster | `cluster_id` | `RequestTag/cluster_id` |
| Single pipeline | (default `sub`) or `pipeline_id` | `RequestTag/pipeline_slug` + `RequestTag/organization_id` |
| Single queue | `queue_id` | `RequestTag/queue_id` |
| Single pipeline + branch (with caveat) | (default) | Add `RequestTag/build_branch` — read the spoofing warning in Principle 3 |

### Provider matrix

| Provider | Buildkite doc | Plugin or mechanism |
|---|---|---|
| AWS | `pipelines/security/oidc/aws.md` | [`aws-assume-role-with-web-identity`](https://github.com/buildkite-plugins/aws-assume-role-with-web-identity-buildkite-plugin) |
| Azure | `pipelines/security/oidc/azure.md` | Federated credential in App Registration; audience `api://AzureADTokenExchange` |
| GCP | `pipelines/security/secrets/managing.md` | [`gcp-workload-identity-federation`](https://github.com/buildkite-plugins/gcp-workload-identity-federation-buildkite-plugin) |
| HashiCorp Vault | Generic OIDC role binding | [`vault-secrets`](https://buildkite.com/resources/plugins/buildkite-plugins/vault-secrets-buildkite-plugin/) |
| Generic OIDC | `pipelines/security/oidc.md` | `buildkite-agent oidc request-token --audience <url>` |

For per-provider trust-policy and federated-credential cookbook entries, see `references/oidc-subject-patterns.md`.

> For the `buildkite-agent oidc request-token` flag table, see the **buildkite-agent-runtime** skill.

## Secrets Workflow

### Which mechanism to use

| Situation | Mechanism | Why |
|---|---|---|
| Buildkite-hosted agents | Buildkite secrets via `secrets:` block + `buildkite-agent secret get` | Only mechanism that works on hosted; cluster-scoped, auto-redacted |
| Self-hosted, secret already in AWS Secrets Manager / SSM | OIDC + `aws-ssm` plugin | No copies of the secret outside source-of-truth |
| Self-hosted, secret in Vault | OIDC-to-Vault + `vault-secrets` plugin | Same — no copies |
| Self-hosted, no external secret store | `environment` hook on the agent with a pipeline-slug guard | Documented fallback in `secrets/managing.md` |
| Computed or derived secret inside a job | `buildkite-agent redactor add` before any path that could print it | Auto-redaction only covers declared secrets |

### Anti-pattern (verbatim from `secrets/risk_considerations.md`)

```yaml
env:
  # Security risk! The secret will be sent to and stored by Buildkite, and
  # be available in the "Uploaded Pipelines" list in the job's Timeline tab.
  GITHUB_MY_APP_DEPLOYMENT_ACCESS_TOKEN: "bd0fa963610b..."

steps:
  - command: scripts/trigger-github-deploy
```

The same doc lists which environment-variable name suffixes the agent auto-redacts: `*_PASSWORD`, `*_SECRET`, `*_TOKEN`, `*_PRIVATE_KEY`, `*_ACCESS_KEY`, `*_SECRET_KEY`, `*_CONNECTION_STRING`. Auto-redaction is a backstop, not a primary control.

### Per-step scoping

Build-level — every job sees `API_ACCESS_TOKEN`:

```yaml
steps:
  - command: do_something.sh
  - command: api_call.sh

secrets:
  - API_ACCESS_TOKEN
```

Per-step — only the API call step sees it:

```yaml
steps:
  - command: do_something.sh
  - command: api_call.sh
    secrets:
      - API_ACCESS_TOKEN
```

Use per-step scoping unless every job genuinely needs the secret. Test steps should not see production deploy credentials.

For the decision tree across hosted vs self-hosted with worked examples, see `references/secrets-workflow-decision-tree.md`.

> For the `secrets:` YAML key syntax, see the **buildkite-pipelines** skill.
> For `buildkite-agent secret get` and `buildkite-agent redactor add` flag tables, see the **buildkite-agent-runtime** skill.
> For creating cluster secrets via UI or API, see `pipelines/security/secrets/buildkite_secrets.md`.

## Signed Pipelines

Sign any pipeline whose output reaches production, any pipeline whose verifier-agent pool has higher privilege than its uploader pool, and any pipeline subject to SLSA L2+ requirements.

### Algorithm choice

The signed-pipelines doc states the recommendation directly: "`EdDSA` is proven to be secure, has a modern design, wasn't designed by a Nation State Actor, and produces nice short signatures. It's also the default when running `buildkite-agent tool keygen`." The agent also supports `PS512` and `ES512`. Both are nondeterministic — they produce different signatures each run — which breaks Terraform drift detection on persisted signed pipelines. Default to `EdDSA` unless there is a specific reason.

### Two-pool deployment pattern

From the doc, verbatim: "When using signed pipelines, we recommend having multiple disjoint pools of agents, each using a different queue. One pool should be the *uploaders* and have access to the private keys. Another pool should be the *runners* and have access to the public keys."

Uploader agent config:

```ini
signing-jwks-file=<path to private key set>
signing-jwks-key-id=<the key id you generated earlier>
verification-jwks-file=<path to public key set>
```

Runner agent config:

```ini
verification-jwks-file=<path to verification keys>
verification-failure-behavior=block
```

### `verification-failure-behavior`

| Value | Behaviour | Use when |
|---|---|---|
| `block` (default) | Job refused if signature missing or invalid | Production. Always. |
| `warn` | Job runs; warning emitted | Rollout only, with a hard cutover date |

### Signed fields

| Field | Signed? |
|---|---|
| Commands | yes |
| Pipeline-YAML-defined env vars | yes |
| Agent-, hook-, or shell-set env vars | **no** (can override step env at runtime) |
| Plugins and plugin config | yes |
| Matrix configuration (whole, not per-job) | yes |
| Repository URL | yes |

The unsigned-env caveat is important: a malicious agent hook can override env that a signed step depends on. Audit hook sources; do not let untrusted hooks set sensitive variables.

> For `buildkite-agent tool sign` and `buildkite-agent tool verify` flag tables, see the **buildkite-agent-runtime** skill.

## Token Lifecycle

### Token type matrix

| Token type | Prefix | Created for | Lifetime guidance |
|---|---|---|---|
| API access token (user) | `bkua_` | A human or service calling REST or GraphQL | Rotate within 90 days; revoke on offboarding |
| Cluster agent token | `bkct_` | Bootstrapping agents into a cluster | Set `expires_at`; rotate when the agent fleet rebuilds |
| Agent session token | `bkaa_` | Issued by the agent API after registration | Managed by the agent; no human rotation |
| Agent job token | `bkaj_` | Per-job scope; what `buildkite-agent` subcommands authenticate with | Auto-expires with the job; do not export from a job |
| Unclustered agent token | `bkar_` | Legacy pre-cluster agent registration | Migrate to clustered `bkct_` |
| OIDC token | (JWT, no prefix) | Per-job authentication to an external system | Default 600s; max useful 3600s |
| Registry token | `bkpt_` | Pulling or pushing packages | See Package Registries docs |

### Rotate agent tokens without breaking running jobs

1. Create the new token (`clusterAgentTokenCreate` GraphQL mutation, or REST equivalent).
2. Roll the new token to the agent fleet one host at a time. Already-connected agents continue using their cached session token (`bkaa_`); only registration requires the cluster token.
3. Wait for jobs running against the old token to drain.
4. Revoke the old token (`clusterAgentTokenRevoke`).

### GitHub secret-scanning safety net

From `platform/security/tokens.md`: "In the case of Buildkite API access tokens leaked on _public_ repositories, GitHub will notify Buildkite directly and any valid tokens will be automatically revoked and their owner's and associated organizations notified." This applies only to `bkua_` tokens leaked publicly — it is defense in depth, not a primary control.

For per-token-type rotation playbooks, see `references/token-types-and-rotation.md`.

> For `clusterAgentTokenCreate` / `clusterAgentTokenRevoke` mutations, see the **buildkite-api** skill.

## Package Registries Authentication

Package Registries support both static `bkpt_` registry tokens and OIDC. Prefer OIDC: same rationale as cloud-provider auth — short-lived, audience-scoped, audit-traceable.

```yaml
steps:
  - label: ":docker: Publish image"
    command: |
      OIDC_TOKEN=$(buildkite-agent oidc request-token \
        --audience "https://packages.buildkite.com/my-org/my-registry")
      echo "$OIDC_TOKEN" | docker login packages.buildkite.com \
        --username buildkite \
        --password-stdin
      docker push packages.buildkite.com/my-org/my-registry/myimage:$BUILDKITE_BUILD_NUMBER
```

The audience must match the registry URL exactly. The registry verifies the OIDC token against the issuer (`https://agent.buildkite.com`) and the configured subject-claim binding.

Static `bkpt_` registry tokens are still supported for non-Buildkite consumers (a developer machine, a third-party CI). For Buildkite jobs themselves, OIDC removes the rotation burden entirely.

> For `buildkite-agent oidc request-token` flag reference, see the **buildkite-agent-runtime** skill.
> For Package Registries product surface beyond authentication — repositories, retention, ecosystems — Buildkite docs at `buildkite.com/docs/package-registries` are the canonical reference.

## Build Provenance and Audit

### AWS CloudTrail trail

A successful OIDC role assumption produces a CloudTrail record. From `pipelines/security/oidc/aws.md`:

```json
{
    "eventVersion": "1.08",
    "userIdentity": {
        "type": "WebIdentityUser",
        "principalId": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/agent.buildkite.com:sts.amazonaws.com:organization:example-org:pipeline:example-pipeline:ref:refs/heads/main:commit:1da177e4c3f41524e886b7f1b8a0c1fc7321cac2:step:",
        "identityProvider": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/agent.buildkite.com"
    },
    "eventName": "AssumeRoleWithWebIdentity",
    "sourceIPAddress": "192.0.2.0",
    "requestParameters": {
        "principalTags": {
            "pipeline_slug": "example-pipeline",
            "organization_id": "ab3883b1-9596-4312-a09c-4527ae997ba7",
            "organization_slug": "example-org"
        },
        "roleSessionName": "buildkite-job-01951944-87df-428f-ad92-90709ee78a59"
    }
}
```

`roleSessionName` carries the job UUID — the receipt that proves which build assumed the role. `principalTags` carries the session-tag claims listed in the pipeline `plugins:` block.

### Buildkite audit log

The Buildkite audit log records org-level events (token creation, permission changes, agent token rotation, pipeline configuration changes). From `pipelines/best_practices/secrets_management.md`: "Track how your secrets are being used. Audit logs showing which steps consume which secrets help you maintain visibility into your security posture and make compliance reporting much easier."

### Attestation pattern

To attach SLSA provenance to a release artifact:

1. The artifact itself.
2. An in-toto attestation (`*.intoto.jsonl`) referencing the OIDC subject claim, commit SHA, and builder ID (`agent.buildkite.com`).
3. The signed pipeline JWS.

Attach all three with `artifact_paths:` on the release step; verify with `cosign verify-attestation` (or equivalent) in the consumer. For the full template and verifier example, see `references/slsa-mapping.md`.

## Common Mistakes

| Mistake | What happens | Fix |
|---|---|---|
| Putting `AWS_ACCESS_KEY_ID` in pipeline `env:` | Secret stored on Buildkite; shown in the Uploaded Pipelines tab; returned by REST and GraphQL | Use OIDC + `aws-assume-role-with-web-identity` |
| Trusting `build_branch` in the OIDC subject claim | A later step can `git checkout` another branch; the trust policy is bypassed | Condition on immutable claims (`organization_id`, `pipeline_slug`); treat branch as advisory only |
| Using `verification-failure-behavior=warn` in production | Unsigned or tampered jobs run with only a log warning | Use `block` (default) in production; `warn` is for rollout, with a cutover date |
| Pipeline-global `secrets:` block leaking prod creds into test jobs | Test runners can read production secrets | Move `secrets:` from build level to the specific deploy step |
| Reading meta-data into `eval` | The meta-data writer becomes arbitrary code execution on the agent | Quote and validate with a `case` allowlist |
| Storing cluster agent tokens in plaintext config files | Token theft equals unlimited build registrations | Store in a platform secret manager (SSM, Secrets Manager, Vault) |
| Using a single API token across multiple automations | Rotation forces an all-or-nothing migration | One token per automation; track in an asset inventory |
| Putting plugin config containing secrets in pipeline YAML | Plugin config is signed but visible; signing protects integrity, not confidentiality | Reference secrets by key (`secrets:`) and have the plugin fetch them at runtime |
| Forgetting that signed pipelines exclude hook-set env vars | Hook-injected env overrides a signed step's env | Audit hooks; do not let untrusted hooks set sensitive vars |
| Echoing a secret into an annotation | Annotation body is searchable, persists across the build, and is returned by REST | Add the value to `buildkite-agent redactor add` before any potential echo path |
| Enabling fork-PR builds on an OIDC-configured pipeline | Anyone who can open a PR can request a token and hit cloud resources | Split CI and CD pipelines; configure OIDC only on deploy |

## Additional Resources

Bundled references:

- `references/oidc-subject-patterns.md` — per-provider subject-claim cookbook (AWS, Azure, GCP, Vault, generic).
- `references/secrets-workflow-decision-tree.md` — expanded decision tree with worked examples for hosted and self-hosted.
- `references/slsa-mapping.md` — Buildkite features mapped to SLSA L1–L3, with attestation template and verifier example.
- `references/token-types-and-rotation.md` — full token-prefix table and rotation playbooks.

Bundled scripts:

- `scripts/check-pipeline-for-secrets.sh` — first-pass grep-based linter for inline secrets in pipeline YAML.
- `scripts/oidc-subject-claim-preview.sh` — render the OIDC `sub` claim string for a pipeline/branch/step without booting an agent.

## Anti-Scope

1. **Pipeline YAML syntax** — `secrets:` block grammar, `if:`, plugin pinning. See **buildkite-pipelines**.
2. **In-job `buildkite-agent` flag reference** — `oidc request-token`, `secret get`, `redactor add`, `tool sign/verify` flag tables. See **buildkite-agent-runtime**.
3. **REST and GraphQL mechanics** — endpoint shape, pagination, rate limits. See **buildkite-api** for `clusterAgentTokenCreate` / `clusterAgentTokenRevoke` schemas.
4. **Cloud-provider IAM policy authoring** — AWS IAM, GCP IAM, Azure RBAC details beyond the trust-policy / federated-credential setup shown here.
5. **Specific secret-manager product internals** — Vault auth-method tuning, AWS Secrets Manager pricing, GCP Secret Manager rotation jobs.
6. **Crypto primitives** — key-algorithm internals beyond the choice rule in [Signed Pipelines](#signed-pipelines).
7. **SSO / SAML configuration** — currently uncovered in this batch.
8. **Build-failure investigation methodology.** See **buildkite-build-investigation**.

## Further Reading

- [OIDC](https://buildkite.com/docs/pipelines/security/oidc) — overview and `--subject-claim` usage.
- [Buildkite secrets](https://buildkite.com/docs/pipelines/security/secrets/buildkite-secrets) — creating and using cluster-scoped secrets.
- [Secret risk considerations](https://buildkite.com/docs/pipelines/security/secrets/risk-considerations) — anti-patterns for storing secrets.
- [Signed pipelines](https://buildkite.com/docs/agent/v3/signed-pipelines) — full signing setup, including AWS KMS.
- [Audit log](https://buildkite.com/docs/platform/audit-log) — Buildkite audit log events and query patterns.
- [Package Registries OIDC](https://buildkite.com/docs/package-registries/security/oidc) — registry-scoped OIDC for `bkpt_` tokens.
