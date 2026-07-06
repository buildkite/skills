# Buildkite token types and rotation playbooks

Source: `platform/security/tokens.md`, `agent/self_hosted/tokens.md`, `apis/managing_api_tokens.md`.

## All Buildkite token prefixes

| Prefix | Full name | Used by | Created via | Auto-revoked on GitHub leak? |
|---|---|---|---|---|
| `bkua_` | API access token (Buildkite user access) | A human or service calling REST or GraphQL | User Settings → API Access Tokens, or GraphQL `apiAccessTokenCreate` | **Yes** (public repos only) |
| `bkaa_` | Agent session token (Buildkite agent access) | Agent → agent-api after registration | Issued automatically on agent registration | Notify Buildkite support |
| `bkaj_` | Agent job token | Per-job auth for `buildkite-agent` subcommands | Issued automatically per job | Notify Buildkite support |
| `bkar_` | Unclustered agent token (registration) | Legacy pre-cluster agent registration | Org settings (legacy) | Notify Buildkite support |
| `bkct_` | Cluster agent token | Bootstrapping agents into a cluster | Agents → cluster → Agent Tokens → New Token, or `clusterAgentTokenCreate` | Notify Buildkite support |
| `bkpt_` | Package Registries token (registry / temporary) | Pull/push packages | Package Registries UI | Notify Buildkite support |
| `bkpat_` | Portal access token | Portal authentication | Portal Security page | Notify Buildkite support |
| `bkps_` | Portal secret | Generating ephemeral portal tokens | Portal Security page | Notify Buildkite support |

## Rotation cadence guidance

| Token type | Rotation cadence | Trigger an immediate rotation when |
|---|---|---|
| `bkua_` API access | 90 days for human tokens; 180 days for service tokens | Human offboarded; service decommissioned; token seen in any log not under your control |
| `bkct_` cluster agent | At fleet rebuild; at minimum annually | Agent host imaged for unrelated purposes; suspected agent compromise |
| `bkar_` unclustered (legacy) | Migrate to `bkct_` rather than rotating | Always |
| `bkaa_` agent session | Managed by the agent; not human-rotated | Agent process restart |
| `bkaj_` agent job | Auto-expires with the job; do not export | N/A |
| OIDC (JWT) | 600s default lifetime | N/A |

## Rotation playbook — API access token (`bkua_`)

1. Identify the consumers of the token (CI scripts, integrations, dashboards).
2. Create a new `bkua_` with the same scopes (User Settings → API Access Tokens → New Token).
3. Roll the new token to consumers one at a time. For consumers stored as Buildkite secrets, update the secret value — the change is picked up on the next job that consumes it.
4. Monitor the audit log for usage of the old token. Wait until it shows no recent activity (usually 24–48 hours covers the long tail of scheduled jobs).
5. Revoke the old token (User Settings → API Access Tokens → Revoke).

## Rotation playbook — Cluster agent token (`bkct_`) without breaking running jobs

The cluster agent token is the bootstrap secret for an agent process. Once registered, an agent uses its session token (`bkaa_`) for ongoing communication, so rotating the cluster token does not interrupt connected agents.

1. Create the new cluster agent token (`clusterAgentTokenCreate` GraphQL mutation, or Agents → cluster → Agent Tokens → New Token). Note its `expires_at` if setting one.
2. Roll the new token to the agent fleet one host at a time. Connected agents continue to use their cached `bkaa_`; only new registrations require the cluster token.
3. Allow jobs against the old token to drain. Agents that have not re-registered in the rotation window will fail their next registration.
4. Revoke the old token (`clusterAgentTokenRevoke`).

For a phased fleet rotation, set the new token's `expires_at` long enough to cover the rollout window plus a margin.

## Rotation playbook — Migrating from unclustered (`bkar_`) to clustered (`bkct_`)

The unclustered agent token (`bkar_`) is the legacy pre-cluster registration mechanism. Treat it as deprecated.

1. Create a Buildkite cluster (Agents → Clusters → New Cluster) if one does not already exist for the target queue.
2. Create a `bkct_` cluster agent token in that cluster.
3. Update agent configuration on each host: replace the `bkar_` token in `buildkite-agent.cfg` with the `bkct_` token.
4. Restart the agent process on each host.
5. After all agents have re-registered against the cluster, revoke the `bkar_` token.

## What GitHub secret-scanning covers

From `platform/security/tokens.md`: "In the case of Buildkite API access tokens leaked on _public_ repositories, GitHub will notify Buildkite directly and any valid tokens will be automatically revoked and their owner's and associated organizations notified."

This applies only to `bkua_` and only to public repositories. For all other token prefixes, and for `bkua_` leaked privately (private repo, log file, screenshot, chat message), notify Buildkite support and rotate manually.

## What to do when a token leaks

1. Revoke the leaked token immediately. Do not wait for the rotation window.
2. Audit log activity for the leaked token's recent calls. The audit log records API token usage; review for unexpected actions.
3. If the leak is in a public GitHub repo and the token is `bkua_`, GitHub may have already revoked it — verify in User Settings.
4. Rotate any downstream credentials the leaked token might have minted (build artifacts, deploy tokens fetched via API, etc.).
5. Notify `security@buildkite.com` for any token type other than `bkua_` so the audit trail can be cross-referenced.
