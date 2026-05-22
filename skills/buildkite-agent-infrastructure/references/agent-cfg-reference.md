# Agent configuration reference

`buildkite-agent.cfg` flag table, environment variable equivalents, corresponding Agent Stack for Kubernetes chart values, and lifecycle-hook directory layout per platform. For exhaustive flag detail, see [the agent configuration docs](https://buildkite.com/docs/agent/self-hosted/configure).

## Configuration file location per platform

| Platform | Default `buildkite-agent.cfg` path | Default `hooks-path` |
|---|---|---|
| Linux (Debian/Ubuntu via package) | `/etc/buildkite-agent/buildkite-agent.cfg` | `/etc/buildkite-agent/hooks` |
| Linux (RedHat/CentOS via package) | `/etc/buildkite-agent/buildkite-agent.cfg` | `/etc/buildkite-agent/hooks` |
| macOS (Homebrew) | `/opt/homebrew/etc/buildkite-agent/buildkite-agent.cfg` (Apple Silicon) or `/usr/local/etc/buildkite-agent/buildkite-agent.cfg` (Intel) | `/opt/homebrew/etc/buildkite-agent/hooks` |
| Windows | `C:\buildkite-agent\buildkite-agent.cfg` | `C:\buildkite-agent\hooks` |
| Docker image (`buildkite/agent`) | `/buildkite/buildkite-agent.cfg` | `/buildkite/hooks` |
| Agent Stack for Kubernetes (command container) | Not a file — config is the controller's Helm values | Mounted via the controller's volume layout |

Override with `--config <path>` or `BUILDKITE_AGENT_CONFIG=<path>`.

## Common configuration settings

Settings shown with their config-file key, environment variable, and corresponding Agent Stack for Kubernetes chart value (`values.yml` under `config:` or `agent-config:` depending on the chart version).

| Setting | Config key | Environment variable | Chart value | Notes |
|---|---|---|---|---|
| Cluster agent token | `token` | `BUILDKITE_AGENT_TOKEN` | `agentToken` (literal — avoid) or `agentStackSecret` (K8s Secret name — recommended) | Inject from secret store at boot |
| Agent name template | `name` | `BUILDKITE_AGENT_NAME` | `config.agent.name` | `%hostname`, `%spawn`, `%n` substitutions |
| Agent tags | `tags` | `BUILDKITE_AGENT_TAGS` | `config.tags` | Comma-separated `k=v` pairs; `queue=<key>` is mandatory |
| Hooks directory | `hooks-path` | `BUILDKITE_HOOKS_PATH` | Not directly exposed — uses controller's volume layout | Self-hosted only |
| Plugin directory | `plugins-path` | `BUILDKITE_PLUGINS_PATH` | `config.plugins-path` | Plugin checkouts cached here |
| Build directory | `build-path` | `BUILDKITE_BUILD_PATH` | Workspace volume layout — pinned via chart version | Changing this between chart versions has broken pipelines (Phase 3 gotcha) |
| Disconnect after job | `disconnect-after-job` | `BUILDKITE_AGENT_DISCONNECT_AFTER_JOB` | `config.disconnect-after-job` | Single-job agent mode |
| Idle timeout | `disconnect-after-idle-timeout` | `BUILDKITE_AGENT_DISCONNECT_AFTER_IDLE_TIMEOUT` | `config.disconnect-after-idle-timeout` | Seconds before idle agent disconnects |
| Debug mode | `debug` | `BUILDKITE_AGENT_DEBUG` | `config.debug` | Verbose logging; do not run in steady state |
| Experimental features | `experiment` | `BUILDKITE_AGENT_EXPERIMENT` | `config.experiment` | Comma-separated experiment names |
| Git clean flags | `git-clean-flags` | `BUILDKITE_GIT_CLEAN_FLAGS` | `config.git-clean-flags` | Default: `-ffxdq` |
| Git mirror | `git-mirrors-path` | `BUILDKITE_GIT_MIRRORS_PATH` | `config.git-mirrors-path` | Speeds large monorepo checkouts |
| Pre-bootstrap hook | `pre-bootstrap-hook` | `BUILDKITE_PRE_BOOTSTRAP_HOOK` | Implicit — file under `hooks-path` | Block unauthorized jobs |

## Example agent configuration

```ini
# /etc/buildkite-agent/buildkite-agent.cfg
token="${BUILDKITE_AGENT_TOKEN}"
name="%hostname-%spawn"
tags="queue=linux-amd64-large,os=linux,arch=amd64,size=large"
hooks-path="/etc/buildkite-agent/hooks"
plugins-path="/var/lib/buildkite-agent/plugins"
build-path="/var/lib/buildkite-agent/builds"
git-clean-flags="-ffxdq"
disconnect-after-job=false
disconnect-after-idle-timeout=600
debug=false
```

## Example Agent Stack for Kubernetes values

```yaml
# values.yml
agentStackSecret: "buildkite-agent-token"  # K8s Secret containing BUILDKITE_AGENT_TOKEN
config:
  tags:
    - queue=kubernetes
    - os=linux
    - arch=amd64
  debug: false
  pod-spec-patch:
    containers:
      - name: agent
        imagePullPolicy: Always
      - name: checkout
        imagePullPolicy: Always
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
```

## Lifecycle hook directory layout

Self-hosted agent hooks directory layout (under `hooks-path`):

```
/etc/buildkite-agent/hooks/
├── pre-bootstrap          # Agent lifecycle — blocks unauthorized jobs
├── agent-startup          # Agent lifecycle — fires once at agent start
├── agent-shutdown         # Agent lifecycle — fires once at agent stop
├── environment            # Job lifecycle — runs before every job's other hooks
├── pre-checkout
├── checkout               # Overrides default git checkout
├── post-checkout
├── pre-command
├── command                # Overrides default command execution
├── post-command
├── pre-artifact
├── post-artifact
└── pre-exit               # Always runs; useful for cleanup
```

Each file must be executable by the agent user. Sample scripts are installed alongside as `*.sample`; remove the suffix to activate.

Repository hooks live at `.buildkite/hooks/<hook-name>` inside the pipeline's repository and run for every job using that repository.

Plugin hooks ship inside plugin packages and run only for steps that include the plugin.

## Common `experiment` flags

Experiment names worth knowing (these change; verify against the agent version in use):

| Experiment | Purpose |
|---|---|
| `job-api` | Enables the in-job HTTP API consumed by `buildkite-agent` polyglot hooks |
| `polyglot-hooks` | Promotes polyglot hook support; mostly default in 3.85.0+ |
| `agent-api` | Newer agent-API surface; check release notes per version |

Promoted experiments graduate to default behaviour. The full list and current status: [Agent experiments](https://buildkite.com/docs/agent/self-hosted/configure/experiments).

## Token bootstrap patterns

| Platform | Pattern |
|---|---|
| AWS EC2 (Elastic CI Stack or self-managed) | Instance profile + SSM Parameter Store; user-data script reads the token at boot and writes it to `/etc/buildkite-agent/buildkite-agent.cfg` |
| GCP GCE | Workload identity + Secret Manager; metadata script reads the token at boot |
| Kubernetes (Agent Stack for Kubernetes) | `agentStackSecret` chart value pointing at a K8s Secret reconciled by External Secrets Operator, sealed-secrets, or CSI driver |
| Bare metal / VM with chef/ansible | Configuration management writes the token to the config file; rotation requires a config-management run |
| Docker (self-managed) | `BUILDKITE_AGENT_TOKEN` env var injected via docker run / docker-compose secret |

Never commit a token literal to a Helm values file, an AMI, or a container image. Even ephemeral secrets that "only live in CI" become long-lived once they enter version control.
