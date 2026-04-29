# Package Registry Publishing Guide

## npm Publishing

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

## Helm Chart Publishing (OCI)

Push Helm charts to a Buildkite Helm OCI registry:

```yaml
steps:
  - label: ":helm: Publish Chart"
    commands:
      - helm package ./chart
      - buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/helm-charts" --lifetime 300 | helm registry login packages.buildkite.com/acme-inc/helm-charts --username buildkite --password-stdin
      - helm push my-chart-1.0.0.tgz oci://packages.buildkite.com/acme-inc/helm-charts
```

## Python / Ruby / Generic Publishing

For ecosystems that use direct HTTP upload, request an OIDC token and pass it as a Bearer token:

```yaml
steps:
  - label: ":python: Publish Package"
    commands:
      - export OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/python-packages" --lifetime 300)
      - python -m build
      - curl -X POST "https://api.buildkite.com/v2/packages/organizations/acme-inc/registries/python-packages/packages" -H "Authorization: Bearer ${OIDC_TOKEN}" -F "file=@dist/my-package-1.0.0.tar.gz"
```

The same pattern applies to Ruby gems, Debian packages, RPMs, Alpine packages, Terraform modules, and generic artifacts -- change the file path and registry slug.

## Terraform Module Publishing

Terraform module filenames must follow the naming convention `terraform-{provider}-{module}-{major.minor.patch}.tgz`:

```yaml
steps:
  - label: ":terraform: Publish Module"
    commands:
      - export OIDC_TOKEN=$(buildkite-agent oidc request-token --audience "https://packages.buildkite.com/acme-inc/terraform-modules" --lifetime 300)
      - tar czf terraform-buildkite-pipeline-1.0.0.tgz -C modules .
      - curl -X POST "https://api.buildkite.com/v2/packages/organizations/acme-inc/registries/terraform-modules/packages" -H "Authorization: Bearer ${OIDC_TOKEN}" -F "file=@terraform-buildkite-pipeline-1.0.0.tgz"
```

## Installing from Package Registry

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

## Ruby Gem Secure Publish Flow

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
