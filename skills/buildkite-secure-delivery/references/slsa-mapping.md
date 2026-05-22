# Buildkite features mapped to SLSA

The [SLSA framework](https://slsa.dev/) defines four levels of supply-chain integrity. This reference maps Buildkite features to the SLSA requirements an organization most commonly tries to satisfy with them. It is a mapping aid, not an authoritative compliance attestation — confirm with an internal auditor before claiming a SLSA level.

## SLSA L1 — Documentation of the build process

L1 requires that the build process is fully scripted and that provenance is generated.

Buildkite features that satisfy L1:

- Pipeline-as-code via `.buildkite/pipeline.yml` in the source repository.
- Immutable build steps after `buildkite-agent pipeline upload` — uploaded steps cannot be edited in flight.
- Standard build metadata (organization, pipeline, build, job, commit, branch, agent) recorded against every job.

## SLSA L2 — Hosted build platform with signed provenance

L2 adds that the build runs on a hosted platform and that provenance is signed.

Buildkite features that satisfy L2:

- Signed pipelines (`buildkite-agent tool sign` + `signing-jwks-file` / `verification-jwks-file`).
- `verification-failure-behavior=block` (default) — unsigned jobs are refused.
- Provenance attached as a build artifact (in-toto attestation, `*.intoto.jsonl`).
- OIDC-based deploy credentials so the deploy identity is provable from CloudTrail / Entra logs.

## SLSA L3 — Hardened builds

L3 adds isolation between builds, hardened build platform, and non-falsifiable provenance.

Buildkite features that satisfy L3:

- Two-pool agent architecture: separate uploader and runner queues, each with its own IAM role and key access (signing private key on uploaders only, verification public key on runners only).
- Ephemeral agent infrastructure (one job per agent instance; container or VM destroyed after the job).
- Cluster-scoped secrets — no cross-cluster secret access.
- Audit log + CloudTrail / Entra sign-in logs as non-falsifiable provenance sources.

## Attestation template

Attach an in-toto attestation as a build artifact:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "myapp-v1.2.3.tar.gz",
      "digest": {
        "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://buildkite.com/build-types/v1",
      "externalParameters": {
        "repository": "https://github.com/example-org/myapp",
        "ref": "refs/heads/main",
        "commit": "1da177e4c3f41524e886b7f1b8a0c1fc7321cac2"
      },
      "internalParameters": {
        "buildkite_organization_id": "ab3883b1-9596-4312-a09c-4527ae997ba7",
        "buildkite_pipeline_slug": "example-pipeline",
        "buildkite_build_id": "01951944-87df-428f-ad92-90709ee78a59",
        "buildkite_job_id": "01951945-1234-5678-9abc-def012345678"
      }
    },
    "runDetails": {
      "builder": {
        "id": "https://agent.buildkite.com"
      },
      "metadata": {
        "invocationId": "buildkite-job-01951945-1234-5678-9abc-def012345678",
        "startedOn": "2026-05-20T13:34:48Z",
        "finishedOn": "2026-05-20T13:36:12Z"
      }
    }
  }
}
```

Produce this file from the OIDC claims, write it to the build workspace, and attach it:

```yaml
steps:
  - label: "Build and attest"
    command: |
      ./scripts/build.sh
      ./scripts/generate-attestation.sh > myapp.intoto.jsonl
    artifact_paths:
      - "dist/myapp-*.tar.gz"
      - "myapp.intoto.jsonl"
```

## Verification in the consumer

`cosign` (or any other in-toto-aware verifier) can validate the attestation in the downstream consumer:

```bash
cosign verify-attestation \
  --type slsaprovenance1 \
  --certificate-identity-regexp '^https://agent\.buildkite\.com$' \
  --certificate-oidc-issuer-regexp '^https://agent\.buildkite\.com$' \
  myapp-v1.2.3.tar.gz
```

Adapt the certificate-identity regex to match the OIDC subject claim format your pipeline emits.

## What L3 still does not give

SLSA L3 does not assert that the source repository is well-governed. A signed, isolated build of malicious source code is still malicious. Pair the SLSA setup with branch protection, required reviews, and an independent code review process.
