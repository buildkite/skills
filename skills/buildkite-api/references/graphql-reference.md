# GraphQL API Reference

Endpoint: `https://graphql.buildkite.com/v1`

Use GraphQL for typed nested reads and mutations that fit the workflow. GraphQL access requires the **Enable GraphQL API Access** token permission rather than granular REST scopes.

Use the REST Audit Events endpoint for audit-event retrieval.

## Basic Query

```bash
curl -sS -X POST "https://graphql.buildkite.com/v1" \
  -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { viewer { user { name email } } }"
  }'
```

## Cursor-Based Pagination

GraphQL uses cursor-based pagination via the `Connection` pattern:

```graphql
query PaginatedBuilds($cursor: String) {
  pipeline(slug: "my-org/my-pipeline") {
    builds(first: 50, after: $cursor) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
          number
          state
          message
          createdAt
        }
      }
    }
  }
}
```

| Parameter | Description |
|-----------|-------------|
| `first` | Return the first N results (forward pagination) |
| `after` | Cursor to start after (from `pageInfo.endCursor`) |
| `last` | Return the last N results (backward pagination) |
| `before` | Cursor to start before (from `pageInfo.startCursor`) |

`PageInfo` fields:

| Field | Description |
|-------|-------------|
| `hasNextPage` | More results exist after the current page |
| `hasPreviousPage` | More results exist before the current page |
| `startCursor` | Cursor of the first item in this page |
| `endCursor` | Cursor of the last item in this page |

To paginate: query with `first: N`, read `pageInfo.endCursor`, pass it as `after` in the next request. Loop until `hasNextPage` is `false`.

## Key Queries

**Get build with job details:**

```graphql
query {
  build(slug: "my-org/my-pipeline/42") {
    number
    state
    message
    branch
    commit
    createdAt
    finishedAt
    jobs(first: 50) {
      edges {
        node {
          ... on JobTypeCommand {
            label
            state
            exitStatus
            startedAt
            finishedAt
          }
        }
      }
    }
  }
}
```

**List clusters and queues:**

```graphql
query {
  organization(slug: "my-org") {
    clusters(first: 10) {
      edges {
        node {
          name
          uuid
          queues(first: 20) {
            edges { node { key description } }
          }
        }
      }
    }
  }
}
```

## Key Mutations

**Create a build:**

```graphql
mutation {
  buildCreate(input: {
    pipelineID: "UGlwZWxpbmUtLS0..."
    commit: "HEAD"
    branch: "main"
    message: "Triggered via GraphQL"
    env: ["DEPLOY_TARGET=staging"]
  }) {
    build {
      number
      url
      state
    }
  }
}
```

Note: `pipelineID` is the opaque GraphQL node ID, not the pipeline slug or REST UUID. Retrieve it with a pipeline query rather than deriving it.

**Create a pipeline** (use `clusterId` to associate with a cluster):

```graphql
mutation {
  pipelineCreate(input: {
    organizationId: "T3JnYW5pemF0aW9uLS0t..."
    clusterId: "Q2x1c3Rlci0tLQ..."
    name: "My New Pipeline"
    repository: { url: "git@github.com:my-org/my-repo.git" }
    steps: { yaml: "steps:\n  - label: ':test_tube: Test'\n    command: 'make test'" }
    defaultBranch: "main"
  }) {
    pipeline {
      slug
      url
    }
  }
}
```

**Create a cluster queue:**

```graphql
mutation {
  clusterQueueCreate(input: {
    organizationId: "T3JnYW5pemF0aW9uLS0t..."
    clusterId: "Q2x1c3Rlci0tLQ..."
    key: "linux-large"
    description: "Large Linux instances for monorepo builds"
  }) {
    clusterQueue {
      id
      key
      description
    }
  }
}
```

Other key mutations: `pipelineUpdate`, `pipelineTemplateCreate` (Enterprise), `agentTokenCreate`, `agentTokenRevoke`.

**Delete an artifact:**

```graphql
mutation DeleteArtifact($id: ID!) {
  artifactDelete(input: { id: $id }) {
    artifact {
      id
      state
    }
  }
}
```

Pass the artifact global GraphQL ID, not its REST UUID. GraphQL API access alone is insufficient: deletion also requires **Build & Read** access or higher on the artifact's pipeline. Require explicit confirmation and apply the artifact-deletion safeguards in the main skill.

## Introspection

Use standard GraphQL introspection (`__schema`, `__type`) to discover available fields and types. The Buildkite GraphQL API supports full schema introspection.
