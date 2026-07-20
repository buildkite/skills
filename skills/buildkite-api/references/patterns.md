# API usage patterns

Keep these workflows read-first and explicit about access. Set `BUILDKITE_API_TOKEN` before running them.

## Inventory organization API posture

Read API controls, pipeline defaults, and recent administrative activity before proposing an organization-level mutation. These are independent resources, not one transaction. Call each endpoint only when its scope, permission, and plan requirements are available.

API settings and pipeline settings require organization admin and `read_organization_settings`. Audit Events additionally require Enterprise and `read_audit_events`.

```bash
org="my-org"
base="https://api.buildkite.com/v2/organizations/$org"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

# Run these settings reads independently when authorized.
curl -sS -H "$auth" "$base/api-settings" | jq .
curl -sS -H "$auth" "$base/pipeline-settings" | jq .

# Run the Audit Events read independently when authorized.
next="$base/audit_events"
while [ -n "$next" ]; do
  page=$(curl -sS -H "$auth" "$next")
  jq -c '.items[]' <<<"$page"
  next=$(jq -r '.links.next // empty' <<<"$page")
done
```

Do not write either settings resource from this inventory loop. Review feature-gated fields and lockout risk before any API allowlist change.

## Discover a repository and create a pipeline

Require organization admin and `read_organization_repository_connections` for discovery, then `write_pipelines` and pipeline access for creation. Discovery supports eligible GitHub and GitHub Enterprise Server connection variants; other providers can return `422`.

Use discovery only when the repository URL or default branch must come from an organization connection. Otherwise, create the pipeline directly.

```bash
set -euo pipefail

org="my-org"
connection_id="CONNECTION_UUID"
repository="my-org/my-repo"
cluster_id="CLUSTER_UUID"
base="https://api.buildkite.com/v2/organizations/$org"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

repo=$(curl -sS --fail-with-body --get -H "$auth" \
  --data-urlencode "repository=$repository" \
  "$base/repository_connections/$connection_id/repositories")

jq . <<<"$repo"
if [ "$(jq 'length' <<<"$repo")" -ne 1 ]; then
  printf 'Expected one repository match; refusing to create pipeline\n' >&2
  exit 1
fi
clone_url=$(jq -er '.[0].clone_url' <<<"$repo")
default_branch=$(jq -er '.[0].default_branch' <<<"$repo")
payload=$(jq -n \
  --arg repository "$clone_url" \
  --arg cluster_id "$cluster_id" \
  --arg default_branch "$default_branch" '{
  name: "My Repository",
  cluster_id: $cluster_id,
  repository: $repository,
  default_branch: $default_branch,
  configuration: "steps:\n  - label: Test\n    command: make test"
}')

curl -sS --fail-with-body -X POST -H "$auth" -H "Content-Type: application/json" \
  "$base/pipelines" \
  -d "$payload" | jq '{slug, web_url, repository}'
```

The exact repository filter is case-insensitive. Verify the result before the mutating create. Pipeline creation validates and mutates in one request; no REST dry run exists. YAML-enabled pipelines require `configuration`; legacy visual-step organizations can use `steps`, and templates use `pipeline_template_uuid`.

## Reconcile a notification webhook safely

Require `read_notification_services`, `write_notification_services`, and organization administrator access or the **Manage Notification Services** permission. Start with inventory and provider-specific docs because list body shape and secret behavior must not be guessed.

```bash
org="my-org"
base="https://api.buildkite.com/v2/organizations/$org/services"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

next="$base"
while [ -n "$next" ]; do
  page=$(curl -sS --fail-with-body -H "$auth" "$next")
  jq '.items[] | select(.provider.id == "webhook") | {
      id, provider: .provider.id, description, enabled, scope,
      destination: .settings.url
    }' <<<"$page"
  next=$(jq -r '.links.next // empty' <<<"$page")
done
```

Match the destination across all pages. Show the selected service by ID, compare stable non-secret fields, then choose create, update, enable, or disable from the [notification services reference](https://buildkite.com/docs/apis/rest-api/organizations/notification-services). Never replace an omitted secret automatically and never delete a service as part of a generic reconciliation loop.

## Trigger, monitor, and diagnose a build

Require `write_builds` to create, cancel, or rebuild and `read_builds` to inspect builds. Use a bounded polling interval, stop at a terminal state, and do not rebuild automatically when the original command may have external side effects.

```bash
set -euo pipefail

org="my-org"
pipeline="my-pipeline"
base="https://api.buildkite.com/v2/organizations/$org/pipelines/$pipeline/builds"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

build=$(curl -sS --fail-with-body -X POST -H "$auth" -H "Content-Type: application/json" \
  "$base" \
  -d '{"commit":"HEAD","branch":"main","message":"API-triggered build"}')
number=$(jq -er '.number' <<<"$build")

for attempt in $(seq 1 60); do
  state=$(curl -sS --fail-with-body -H "$auth" \
    "$base/$number?exclude_jobs=true&exclude_pipeline=true" | jq -er '.state')
  case "$state" in
    passed|failed|canceled|skipped|not_run) break ;;
  esac
  sleep 10
done

case "$state" in
  passed|failed|canceled|skipped|not_run) ;;
  *) printf 'Timed out while build %s remained in state %s\n' "$number" "$state" >&2; exit 1 ;;
esac
printf 'Build %s finished in state %s\n' "$number" "$state"
```

Cancel a running build with `PUT $base/$number/cancel`. Rebuild with `PUT $base/$number/rebuild` only when replaying the original commit, branch, environment, message, and pull request context is intended. To fetch current source-control state, create a new build instead.

### Diagnose failed jobs

Require `read_builds`. This command inspects the first response page only; follow `.links.next` before treating the results as complete. Inspect signal and embedded agent context before deciding whether a retry is safe.

```bash
org="my-org"
pipeline="my-pipeline"
build="42"
base="https://api.buildkite.com/v2/organizations/$org/pipelines/$pipeline/builds/$build"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

curl -sS -H "$auth" \
  "$base/jobs?state[]=failed&include_retried_jobs=false&per_page=100" \
  | jq '.items[] | {
      id, name, exit_status, signal, signal_reason,
      agent: (.agent | {os_id, arch, queue, connected_at, disconnected_at, lost_at, stopped_at})
    }'
```

Diagnostic fields can explain failure timing but do not prove an external side effect did not occur.

### Filter artifacts when build output is needed

Require `read_artifacts`. This command inspects the first response page only; follow the HTTP `Link` header before treating the results as complete.

```bash
org="my-org"
pipeline="my-pipeline"
build="42"
base="https://api.buildkite.com/v2/organizations/$org/pipelines/$pipeline/builds/$build"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

curl -sS --get -H "$auth" \
  --data-urlencode "state=finished" \
  --data-urlencode "path=test-results/*.xml" \
  "$base/artifacts" \
  | jq '.[] | {id, path, state, job_id}'
```

Path matching is exact unless the value contains `*`.
