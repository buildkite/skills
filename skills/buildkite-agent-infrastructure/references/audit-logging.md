# Audit Logging and SIEM Integration

Audit logging (Enterprise-only) tracks organization-level events for compliance and security monitoring.

## Query audit events

```graphql
query {
  organization(slug: "my-org") {
    auditEvents(
      first: 50
      occurredAtFrom: "2026-03-01T00:00:00Z"
      occurredAtTo: "2026-03-26T23:59:59Z"
    ) {
      edges {
        node {
          type
          occurredAt
          actor { name type uuid }
          subject { name type uuid }
          data
        }
      }
    }
  }
}
```

| Filter | Description |
|--------|-------------|
| `occurredAtFrom` / `occurredAtTo` | ISO 8601 time range |
| `type` | Specific audit event type (e.g., `ORGANIZATION_UPDATED`) |
| `subjectType` | Filter by subject type (e.g., `PIPELINE`, `AGENT_TOKEN`) |
| `subjectUUID` | Filter by specific subject |
| `order` | `RECENTLY_OCCURRED` (default) or `OLDEST_OCCURRED` |

## High-severity events to monitor

| Event type | Why it matters |
|------------|---------------|
| `agent_token.created` / `.deleted` | Agent authentication changes |
| `member.invited` / `.removed` | Team membership changes |
| `sso_provider.created` / `.updated` | SSO configuration changes |
| `pipeline_schedule.created` | New automated triggers |
| `cluster_secret.created` / `.deleted` | Secret management changes |
| `organization.updated` | Org-level setting changes |

## SIEM integration via Amazon EventBridge

Stream audit events to a SIEM in real time using EventBridge:

- **Source:** `aws.partner/buildkite.com/buildkite/<partner-event-source-id>`
- **Detail type:** `"Audit Event Logged"`

Event payload structure:

```json
{
  "organization": {
    "uuid": "org-uuid",
    "graphql_id": "T3JnYW5pemF0aW9u...",
    "slug": "my-org"
  },
  "event": {
    "uuid": "event-uuid",
    "occurred_at": "2026-03-26T14:30:00Z",
    "type": "agent_token.created",
    "data": { },
    "subject_type": "AgentToken",
    "subject_uuid": "token-uuid",
    "subject_name": "Production agents",
    "context": {
      "request_id": "req-uuid",
      "request_ip": "203.0.113.42",
      "session_user_uuid": "user-uuid",
      "request_user_agent": "Mozilla/5.0..."
    }
  },
  "actor": {
    "name": "Jane Engineer",
    "type": "USER",
    "uuid": "user-uuid"
  }
}
```

Route high-severity events to PagerDuty, Splunk, or Datadog via EventBridge rules matching on `detail.event.type`.
