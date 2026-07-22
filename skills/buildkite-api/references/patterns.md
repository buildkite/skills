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

## Create a pipeline with the required repository checks

Require `write_pipelines` and pipeline access for creation. When the user supplies a repository URL and only needs a pipeline, skip repository discovery and create directly.

```bash
set -euo pipefail

org="my-org"
cluster_id="CLUSTER_UUID"
repository_url="git@github.com:my-org/my-repo.git"
default_branch="main"
base="https://api.buildkite.com/v2/organizations/$org"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

payload=$(jq -n \
  --arg repository "$repository_url" \
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

Pipeline creation validates and mutates in one request; no REST dry run exists.

Default to YAML `configuration`. Use `pipeline_template_uuid` when a template has been selected, and use visual `steps` only for a known legacy workflow. No public organization field reliably identifies the step mode before creation. Report a `422` validation response instead of silently retrying with a different mode.

### Verify an existing GitHub connection when the outcome depends on it

When the requested result depends on an existing GitHub connection—for example, verify access before configuring pull request builds, commit statuses, or repository webhooks—require organization admin and `read_organization_repository_connections`, then discover before creating the pipeline. Discovery supports eligible GitHub and GitHub Enterprise Server connection variants.

```bash
set -euo pipefail

org="my-org"
connection_id="CONNECTION_UUID"
repository="my-org/my-repo"
base="https://api.buildkite.com/v2/organizations/$org"
auth="Authorization: Bearer $BUILDKITE_API_TOKEN"

repo=$(curl -sS --fail-with-body --get -H "$auth" \
  --data-urlencode "repository=$repository" \
  "$base/repository_connections/$connection_id/repositories")

jq . <<<"$repo"
if [ "$(jq 'length' <<<"$repo")" -ne 1 ]; then
  printf 'Expected one repository match; refusing connection-dependent setup\n' >&2
  exit 1
fi

repository_url=$(jq -er '.[0].clone_url' <<<"$repo")
default_branch=$(jq -er '.[0].default_branch' <<<"$repo")
```

The exact repository filter is case-insensitive. Use the returned `repository_url` and `default_branch` in the create payload above only after the check succeeds. Do not block ordinary pipeline creation when discovery is unsupported; explain the remaining provider or browser prerequisite instead.

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

Use `step_key` when every job for one step is relevant, including parallel jobs, and `group_key` for every job in a group. Apply either filter independently or combine them when both constraints are intended:

```bash
curl -sS --get -H "$auth" \
  --data-urlencode "step_key=test" \
  --data-urlencode "group_key=verification" \
  --data-urlencode "per_page=100" \
  "$base/jobs" | jq '.items[] | {id, name, state}'
```

Follow each `.links.next` URL as returned so filters remain applied across cursor pages. Diagnostic fields can explain failure timing but do not prove an external side effect did not occur.

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
