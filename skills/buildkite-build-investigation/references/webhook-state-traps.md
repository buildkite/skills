# Webhook State Traps

Two well-documented Linear escalations capture the canonical webhook state traps:

- **PS-1300 (Spotify, Sev 3)** — Spotify's webhook consumer received `build.finished` events whose payload contained `"state":"running"`. They used Claude Code to root-cause the issue to replica-lag in `ServiceNotificationWorker`: the worker that builds the webhook payload was reading from a read replica that had not yet observed the build's terminal-state write.
- **PS-505 (Airtable, Sev 6)** — A "ghost build" ran for five hours: all jobs finished, but the build itself never reached a terminal state. Downstream automation that polled `build.state` saw `running` indefinitely; webhooks never fired for `build.finished`.

The pattern in both: **the webhook payload state and the REST API state can disagree, and the REST API is authoritative for terminal state**.

This reference covers the trap, the verification rule, and the recommended idempotency pattern for webhook consumers.

## The trap

The Buildkite event pipeline is eventually consistent. A `build.finished` event is emitted when the build's state machine transitions to a terminal state, but the payload is assembled from a query that may read a replica that has not yet observed the transition. The result: a `build.finished` event whose payload reads `"state":"running"`.

Three failure modes follow:

1. **State-staleness.** Payload state lags the canonical state. PS-1300.
2. **Missing terminal event.** The build never emits `build.finished` because internal reconciliation is wedged. PS-505.
3. **Out-of-order events.** A `job.finished` arrives after a `build.finished`. Less common but observed.

## The verification rule

When a webhook-driven action depends on build state — promote to production, post a status, close a ticket — verify with the REST API before acting:

```bash
# What the webhook said
echo "$WEBHOOK_PAYLOAD" | jq '.build.state'

# What the API says
bk api /organizations/my-org/pipelines/my-app/builds/42 | jq '.state'

# Or via MCP: get_build with build_number
```

If they disagree, the API is authoritative. If the API also says `running` and the user can see in the UI that all jobs finished, the build is in the PS-505 ghost state — escalate; this is a platform issue, not a configuration issue.

## Idempotency pattern for webhook consumers

The recommended pattern for a webhook consumer that triggers a downstream action:

1. Receive the webhook.
2. **Do not** trust the payload's `state` field. Treat the payload only as a notification that "something happened to build N".
3. Fetch the canonical state via `GET /organizations/:slug/pipelines/:slug/builds/:n`.
4. Make the decision based on the canonical state.
5. Record the action's outcome keyed by build ID, so a redelivered webhook is a no-op.

```python
def handle_webhook(payload):
    build_id = payload["build"]["id"]
    if already_processed(build_id):
        return
    build = buildkite_api.get_build(build_id)
    if build["state"] not in TERMINAL_STATES:
        # PS-1300 case — webhook fired but state not yet reconciled.
        # Either retry-with-backoff or drop and rely on later redelivery.
        schedule_retry(build_id, delay=30)
        return
    take_action(build)
    mark_processed(build_id)
```

The cost of the extra API call is one round trip. The cost of acting on a stale webhook is a wrong deploy.

## When to suspect a webhook state trap

| Symptom | Likely cause |
|---|---|
| Downstream system thinks build is still running while the UI shows finished | PS-1300 state-staleness — verify via API |
| Downstream system never received `build.finished` for a build that visibly completed | PS-505 ghost build — escalate |
| Same build action runs twice for the same build | Missing idempotency in the consumer (not a platform bug) |
| `job.finished` arrives after `build.finished` | Out-of-order event delivery — order is not guaranteed |
| Webhook payload's `state` differs from `bk build view` output | Webhook payload assembled from a stale replica — trust the API |

## Diagnostic queries

```bash
# Compare canonical state to whatever the consumer recorded
bk api /organizations/my-org/pipelines/my-app/builds/42 \
  | jq '{state, started_at, finished_at, canceled_at}'

# Per-job state — useful for PS-505-style ghost builds where all jobs are done
bk build view 42 --pipeline my-org/my-app --output json \
  | jq '.jobs[] | {id, state, finished_at}'
```

If every job has a `finished_at` timestamp and the build's `state` is still `running`, the build is in a PS-505 ghost state. File a support ticket with the build URL; the agent cannot recover the build from this state.

## Cross-references

- For webhook payload schemas, event types, and signature verification, see the **buildkite-api** skill.
- For agent-side reasons a job might stall (which can cascade into a build state issue), see `agent-disconnect-diagnostics.md`.
- For the failure-attribution mapping that includes `upstream-event-timing` and `upstream-stuck-state` categories, see `failure-attribution-decision-tree.md`.
