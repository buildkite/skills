# GraphQL Mutations Reference — Platform Engineering

Complete mutation examples for managing Buildkite clusters, queues, agent tokens, pipeline templates, SSO providers, and audit events via the GraphQL API at `https://graphql.buildkite.com/v1`.

All mutations require an API token with appropriate scopes. Pass it as a Bearer token in the `Authorization` header.

## Prerequisites — Get Organization and Cluster IDs

```graphql
query {
  organization(slug: "my-org") {
    id
    teams(first: 100) {
      edges {
        node { id slug name }
      }
    }
    clusters(first: 50) {
      edges {
        node {
          id
          uuid
          name
          description
          color
          emoji
          defaultQueue { id key }
        }
      }
    }
  }
}
```

---

## Clusters

### Create a cluster

```graphql
mutation CreateCluster {
  clusterCreate(input: {
    organizationId: "T3JnYW5pemF0aW9uLS0tYWJjMTIz"
    name: "Production"
    description: "Production CI/CD cluster"
    emoji: ":rocket:"
    color: "#14CC80"
  }) {
    cluster {
      id
      uuid
      name
      description
      emoji
      color
      defaultQueue { id key }
      createdBy { name email }
    }
  }
}
```

### Update a cluster

```graphql
mutation UpdateCluster {
  clusterUpdate(input: {
    organizationId: "org-id"
    id: "cluster-id"
    name: "Production (Primary)"
    description: "Updated description"
    emoji: ":rocket:"
    color: "#0B79CE"
    defaultQueueId: "queue-id"
  }) {
    cluster { id name description defaultQueue { id key } }
  }
}
```

### Delete a cluster

```graphql
mutation DeleteCluster {
  clusterDelete(input: {
    organizationId: "org-id"
    id: "cluster-id"
  }) {
    deletedClusterId
  }
}
```

---

## Queues

### Create a self-hosted queue

```graphql
mutation CreateSelfHostedQueue {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "gpu-runners"
    description: "GPU-equipped self-hosted agents for ML workloads"
  }) {
    clusterQueue {
      id
      uuid
      key
      description
      dispatchPaused
      hosted
      createdBy { name email }
    }
  }
}
```

### Create a hosted queue (Linux)

```graphql
mutation CreateHostedLinuxQueue {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "linux-large"
    description: "Linux 8 vCPU / 32 GB for heavy compilation"
    hostedAgents: {
      instanceShape: LINUX_AMD64_8X32
    }
  }) {
    clusterQueue {
      id
      uuid
      key
      description
      hosted
      hostedAgents {
        instanceShape {
          name
          size
          vcpu
          memory
        }
      }
    }
  }
}
```

### Create a hosted queue (macOS)

```graphql
mutation CreateHostedMacOSQueue {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "macos-ci"
    description: "macOS M4 for Xcode builds"
    hostedAgents: {
      instanceShape: MACOS_M4_12X56
      macosVersion: SEQUOIA
    }
  }) {
    clusterQueue {
      id
      key
      hostedAgents {
        instanceShape { name vcpu memory }
      }
    }
  }
}
```

### Create a hosted queue with custom agent image

```graphql
mutation CreateHostedCustomImageQueue {
  clusterQueueCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    key: "custom-linux"
    description: "Custom Linux image with pre-installed toolchain"
    hostedAgents: {
      instanceShape: LINUX_AMD64_4X16
      agentImageRef: "my-org.registry.buildkite.com/ci-image:latest"
    }
  }) {
    clusterQueue {
      id
      key
      hostedAgents { instanceShape { name vcpu memory } }
    }
  }
}
```

### Update a queue

```graphql
mutation UpdateQueue {
  clusterQueueUpdate(input: {
    organizationId: "org-id"
    id: "queue-id"
    description: "Updated queue description"
  }) {
    clusterQueue { id key description }
  }
}
```

### Pause dispatch

```graphql
mutation PauseQueue {
  clusterQueuePauseDispatch(input: {
    organizationId: "org-id"
    id: "queue-id"
    note: "Maintenance window 2026-03-26 22:00-23:00 UTC"
  }) {
    clusterQueue { id key dispatchPaused }
  }
}
```

### Resume dispatch

```graphql
mutation ResumeQueue {
  clusterQueueResumeDispatch(input: {
    organizationId: "org-id"
    id: "queue-id"
  }) {
    clusterQueue { id key dispatchPaused }
  }
}
```

### Delete a queue

```graphql
mutation DeleteQueue {
  clusterQueueDelete(input: {
    organizationId: "org-id"
    id: "queue-id"
  }) {
    deletedClusterQueueId
  }
}
```

---

## Agent Tokens

### Create a clustered agent token

```graphql
mutation CreateClusterToken {
  clusterAgentTokenCreate(input: {
    organizationId: "org-id"
    clusterId: "cluster-id"
    description: "Backend CI agents - production"
    allowedIpAddresses: "10.0.0.0/8,172.16.0.0/12"
  }) {
    clusterAgentTokenEdge {
      node {
        id
        uuid
        description
        allowedIpAddresses
        token  # Only returned at creation — store immediately
        createdAt
      }
    }
  }
}
```

### Create an unclustered agent token

```graphql
mutation CreateUnclusteredToken {
  agentTokenCreate(input: {
    organizationId: "org-id"
    description: "Legacy unclustered agents"
  }) {
    agentTokenEdge {
      node {
        id
        description
        token  # Only returned at creation
      }
    }
  }
}
```

### Revoke a token

```graphql
mutation RevokeToken {
  agentTokenRevoke(input: {
    id: "token-id"
    reason: "Compromised — rotated to new token"
  }) {
    agentToken { id description revokedAt revokedReason }
  }
}
```

---

## Pipeline Templates

Enterprise-only. Templates define standard pipeline YAML that pipelines can inherit.

### Create a template

```graphql
mutation CreateTemplate {
  pipelineTemplateCreate(input: {
    organizationId: "org-id"
    name: "Standard CI Template"
    description: "Organization-standard pipeline with security scanning"
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
    retry:
      automatic:
        - exit_status: -1
          limit: 2

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
      description
      available
      configuration
    }
  }
}
```

### Update a template

```graphql
mutation UpdateTemplate {
  pipelineTemplateUpdate(input: {
    id: "template-id"
    name: "Standard CI Template v2"
    description: "Updated with artifact signing step"
    available: true
    configuration: "..."
  }) {
    pipelineTemplate { id name available }
  }
}
```

### Delete a template

```graphql
mutation DeleteTemplate {
  pipelineTemplateDelete(input: {
    id: "template-id"
  }) {
    deletedPipelineTemplateId
  }
}
```

---

## SSO Providers

### Create a SAML provider

```graphql
mutation CreateSAMLProvider {
  ssoProviderCreate(input: {
    organizationId: "org-id"
    type: SAML
    emailDomain: "example.com"
    emailDomainVerificationAddress: "admin@example.com"
  }) {
    ssoProvider {
      id
      state
      emailDomain
      emailDomainVerificationAddress
      serviceProvider {
        metadata { url }
        ssoURL     # ACS URL — configure this in the IdP
        issuer     # Entity ID — configure this in the IdP
      }
    }
  }
}
```

### Update provider with IdP metadata URL

```graphql
mutation UpdateSSOWithMetadataURL {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      metadata: {
        url: "https://idp.example.com/app/abc123/sso/saml/metadata"
      }
    }
  }) {
    ssoProvider {
      id
      state
      ... on SSOProviderSAML {
        identityProvider {
          ssoURL
          issuer
          metadata { url }
        }
      }
    }
  }
}
```

### Update provider with manual configuration

```graphql
mutation UpdateSSOManual {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      ssoURL: "https://idp.example.com/saml/sso"
      issuer: "https://idp.example.com"
      certificate: "-----BEGIN CERTIFICATE-----\nMIID...base64...==\n-----END CERTIFICATE-----"
    }
  }) {
    ssoProvider { id state }
  }
}
```

### Enable a provider

```graphql
mutation EnableSSO {
  ssoProviderEnable(input: {
    id: "sso-provider-id"
  }) {
    ssoProvider { id state enabledAt }
  }
}
```

### Disable a provider

```graphql
mutation DisableSSO {
  ssoProviderDisable(input: {
    id: "sso-provider-id"
    disabledReason: "Migrating to new IdP"
  }) {
    ssoProvider { id state }
  }
}
```

### Query all SSO providers

```graphql
query ListSSOProviders {
  organization(slug: "my-org") {
    ssoProviders(first: 10) {
      edges {
        node {
          id
          type
          state
          emailDomain
          emailDomainVerificationAddress
          emailDomainVerifiedAt
          createdAt
          enabledAt
          url
          ... on SSOProviderSAML {
            identityProvider {
              ssoURL
              issuer
              certificate
              metadata { url xml }
            }
          }
          ... on SSOProviderGoogleGSuite {
            googleHostedDomain
            discloseGoogleHostedDomain
          }
        }
      }
    }
  }
}
```

---

## Audit Events

### Query recent audit events

```graphql
query RecentAuditEvents {
  organization(slug: "my-org") {
    auditEvents(
      first: 100
      occurredAtFrom: "2026-03-01T00:00:00Z"
      occurredAtTo: "2026-03-31T23:59:59Z"
      order: RECENTLY_OCCURRED
    ) {
      edges {
        node {
          type
          occurredAt
          actor { name type uuid }
          subject { name type uuid }
          data
          context
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
```

### Filter by event type

```graphql
query AgentTokenEvents {
  organization(slug: "my-org") {
    auditEvents(
      first: 50
      type: AGENT_TOKEN_CREATED
    ) {
      edges {
        node {
          type
          occurredAt
          actor { name }
          subject { name type }
        }
      }
    }
  }
}
```

### Filter by subject

```graphql
query PipelineAuditTrail {
  organization(slug: "my-org") {
    auditEvents(
      first: 50
      subjectType: PIPELINE
      subjectUUID: "pipeline-uuid"
    ) {
      edges {
        node {
          type
          occurredAt
          actor { name }
          data
        }
      }
    }
  }
}
```

---

## Pipelines — Create with Cluster and Team Assignment

### Create a pipeline in a cluster

```graphql
mutation CreatePipeline {
  pipelineCreate(input: {
    organizationId: "org-id"
    name: "backend-api"
    repository: {
      url: "git@github.com:my-org/backend-api.git"
    }
    clusterId: "cluster-id"
    steps: {
      yaml: """
steps:
  - label: ":pipeline: Upload"
    command: buildkite-agent pipeline upload
"""
    }
    teams: [
      { id: "team-id" }
    ]
  }) {
    pipeline {
      id
      slug
      name
      cluster { id name }
    }
  }
}
```

---

## Organization — Teams and Permissions

### List teams with pipeline creation permissions

```graphql
query TeamsWithPipelineCreation {
  organization(slug: "my-org") {
    teams(first: 100) {
      edges {
        node {
          id
          slug
          name
          membersCanCreatePipelines
          members(first: 100) {
            edges {
              node {
                role
                user { name email }
              }
            }
          }
        }
      }
    }
  }
}
```

### Check organization permissions

```graphql
query OrgPermissions {
  organization(slug: "my-org") {
    permissions {
      ssoProviderCreate { allowed }
      ssoProviderUpdate { allowed }
      teamAdmin { allowed }
      teamCreate { allowed }
      teamEnabledChange { allowed }
    }
  }
}
```
