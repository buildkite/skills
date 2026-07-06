# Evals — buildkite-secure-delivery

Ten trigger-prompt cases, each with the expected skill behaviour and the key assertion the response must satisfy. Prompts are drawn from real customer phrasing (PostHog candidate-3 evidence and Linear pain themes around tokens, secrets, and signing) plus generic secure-delivery asks.

| # | Prompt | Expected behaviour | Key assertion |
|---|---|---|---|
| 1 | "Use OIDC to push to ECR from a Buildkite job — we have an org-wide AWS account." | Skill triggers. Output uses `aws-assume-role-with-web-identity#v1.2.0`, conditions trust policy on `RequestTag/organization_id` (UUID) and `pipeline_slug`, recommends against trusting `build_branch`. | Mentions `aws-assume-role-with-web-identity`, `session-tags`, and `organization_id` UUID conditioning. |
| 2 | "Rotate our agent tokens without breaking running jobs." | Triggers. Output is the four-step playbook: create new `bkct_` → roll to fleet → wait for drain → revoke old via `clusterAgentTokenRevoke`. Notes that connected agents use cached `bkaa_` session tokens. | Mentions `bkct_`, `bkaa_`, `clusterAgentTokenRevoke`, and the drain step. |
| 3 | "We leaked a secret in a build log — how do we redact it?" | Triggers. Output: (1) rotate the secret immediately because log redaction is not retroactive, (2) `buildkite-agent redactor add` for future jobs, (3) contact `security@buildkite.com` for historical log scrubbing, (4) audit downstream log copies. | Explicitly states log redaction is not retroactive; rotation must happen first. |
| 4 | "Set up pipeline signing for our prod deploys." | Triggers. Output: `buildkite-agent tool keygen --alg EdDSA`, two-pool agent split (uploader private key, runner public key), `signing-jwks-file` on uploaders, `verification-jwks-file` on runners, `verification-failure-behavior=block`. | Mentions EdDSA, two-pool split, and `block` (not `warn`) for production. |
| 5 | "How do I audit who triggered a build last week?" | Triggers. Output points to `platform/audit_log.md` for org-level events; for OIDC-side audit, points to AWS CloudTrail `roleSessionName` carrying the job UUID, and Entra ID Service principal sign-in logs for Azure. | Mentions the Buildkite audit log AND CloudTrail / Entra sign-in logs as complementary sources. |
| 6 | "I want my Buildkite pipeline to authenticate to Google Cloud without storing a service account key." | Triggers. Output: `buildkite-agent oidc request-token` + `gcp-workload-identity-federation` plugin; configure a Workload Identity Pool provider with issuer `https://agent.buildkite.com`; map `google.subject = assertion.sub`. | Mentions `gcp-workload-identity-federation` and Workload Identity Pool provider. |
| 7 | "Add SLSA L2 provenance to our release artifacts." | Triggers. Output points to `references/slsa-mapping.md`; minimum viable: signed pipeline + in-toto attestation as artifact + cosign-verify in consumer. | Mentions signed pipelines, `*.intoto.jsonl`, and `cosign verify-attestation` (or equivalent). |
| 8 | "Why are our test runners getting our production deploy creds?" | Triggers. Diagnosis: build-level `secrets:` block leaks into all jobs. Fix: move `secrets:` to the specific deploy step. Quotes the secrets-management best practice on not letting test steps see production credentials. | Identifies pipeline-global `secrets:` as the cause and recommends per-step scoping. |
| 9 | "Can I trust the `build_branch` claim in the OIDC token?" | Triggers. Output cites the AWS doc warning verbatim: "this doesn't necessarily guarantee that the entire build will be run from the branch defined in the policy." Recommends conditioning on `pipeline_slug` + `organization_id` instead; treats branch as advisory. | Quotes the AWS doc spoofing warning and recommends immutable claims. |
| 10 | "Sign pipelines but only warn on bad signatures while we roll out." | Triggers. Output: `verification-failure-behavior=warn` is acceptable during rollout, with a hard cutover date documented; do not leave `warn` in place in production. References `signed_pipelines.md`. | Allows `warn` only for rollout with a cutover; defaults to `block` for steady state. |

## Bonus borderline case (should NOT trigger this skill)

| Prompt | Expected behaviour |
|---|---|
| "How do I write a `secrets:` block in pipeline YAML?" | Trigger **buildkite-pipelines** (YAML syntax), not secure-delivery. Boundary: syntax → pipelines; judgement about *which* secret mechanism → secure-delivery. |

## How to run

These are manual cases for now. Treat them as a regression checklist before publishing changes to `SKILL.md` or the references. A future automated harness can grade each response against the "Key assertion" column.
