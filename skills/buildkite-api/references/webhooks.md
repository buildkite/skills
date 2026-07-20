# Webhooks

Use the main skill to identify whether the operation concerns an outbound notification, inbound GitHub processing, repository webhook registration, or the organization GitHub App connection. Changing one does not configure the others.

The inbound processing toggle requires `read_pipelines` or `write_pipelines`, Full Access, an eligible pipeline, and expanded webhook triggers. Unavailable configurations return `404`.

## Reconcile an outbound webhook

Use `read_notification_services` and `write_notification_services` plus organization administrator access or the **Manage Notification Services** permission.

1. List notification services and match the webhook by stable destination and provider fields.
1. Show the matched service before mutation.
1. Compare only fields managed by the integration.
1. Create when absent; update, enable, or disable when present; delete only with explicit destructive intent.
1. Re-read the service and verify non-secret fields.

Do not infer that an omitted or redacted response field must be replaced. Secret response behavior varies by provider. Follow the [notification services REST reference](https://buildkite.com/docs/apis/rest-api/organizations/notification-services) for request fields and provider behavior.

Common generally available service types include webhook, legacy Slack incoming webhook, EventBridge, Datadog, and OpenTelemetry. OAuth Slack Workspace and Linear require browser creation and authorization; common fields can be managed through the API afterward.

## Handle outbound events

Branch on the `X-Buildkite-Event` header or top-level `event` value. Payload shapes vary by event: do not require every event to contain the same build, job, pipeline, agent, or sender fields.

Keep handlers safe:

- Parse the raw request according to the documented content type and selected event.
- Validate the current authentication fields exactly as specified in the [webhooks documentation](https://buildkite.com/docs/apis/webhooks). Do not invent an HMAC contract or stale field names.
- Return success quickly and move slow work to a queue.
- Make processing idempotent because deliveries can repeat.
- Query REST or GraphQL by payload IDs when the event omits needed retry or relationship context.
- Record the event name and stable object IDs without logging tokens or secret values.

Do not auto-retry a build solely from a failure event. Verify retry history, command idempotency, and external side effects first.

## Diagnose inbound GitHub delivery

Check the layers independently:

1. Confirm the organization GitHub App or repository connection can access the repository.
1. Confirm the repository has a webhook registration or supported app-based delivery path.
1. Read the pipeline `github-webhooks` processing resource and distinguish `404` eligibility from an absent pipeline.
1. Check that expanded webhook triggers are configured before enrollment.
1. Inspect repository delivery and Buildkite processing results separately.

See the [pipelines REST reference](https://buildkite.com/docs/apis/rest-api/pipelines) for the current processing endpoints and [GitHub integration documentation](https://buildkite.com/docs/pipelines/source-control/github) for repository-side setup.
