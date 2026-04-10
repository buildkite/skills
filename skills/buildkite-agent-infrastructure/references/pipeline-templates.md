# Pipeline Templates

Pipeline templates (Enterprise-only) standardize pipeline YAML across the organization. Templates define a base configuration that pipelines inherit, ensuring consistency for security, compliance, or organizational standards.

## Create a template

```graphql
mutation {
  pipelineTemplateCreate(input: {
    organizationId: "org-id"
    name: "Standard CI Template"
    description: "Organization-standard CI pipeline with security scanning and artifact signing"
    available: true
    configuration: """
steps:
  - label: ":pipeline: Upload"
    command: buildkite-agent pipeline upload

  - wait

  - label: ":shield: Security Scan"
    command: "scripts/security-scan.sh"
    agents:
      queue: "security-scanners"

  - wait

  - label: ":rocket: Deploy"
    command: "scripts/deploy.sh"
    branches: "main"
    concurrency: 1
    concurrency_group: "deploy/production"
"""
  }) {
    pipelineTemplate {
      id
      uuid
      name
      available
    }
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `organizationId` | Yes | Organization GraphQL ID |
| `name` | Yes | Template name |
| `description` | No | What this template provides |
| `configuration` | Yes | Pipeline YAML string |
| `available` | No | Whether teams can select this template (default: `false`) |

## Update a template

```graphql
mutation {
  pipelineTemplateUpdate(input: {
    id: "template-id"
    name: "Standard CI Template v2"
    configuration: "..."
    available: true
  }) {
    pipelineTemplate { id name }
  }
}
```

## Template strategy

- Create a small number of templates (3-5) covering common patterns: basic CI, CI + deploy, CI + security scan + deploy
- Set `available: true` only for templates ready for teams to adopt
- Templates use standard pipeline YAML — test the YAML as a regular pipeline before promoting to a template
- Assign templates to pipelines via the Buildkite UI or API
