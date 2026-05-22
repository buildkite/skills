# Migration: Elastic CI Stack for AWS to Agent Stack for Kubernetes

Expanded checklist for SKILL.md Phase 7. Most migrations stall at hook parity (Phase 7.3). Treat hook translation as the critical path.

## Phase 7.1 — Inventory

Catalogue, per queue:

- Queue key (`queue=<key>` tag value)
- Custom AMI (base image, packages, configuration)
- Agent version range (per pipeline if relevant)
- Hook files on the agent host (`hooks-path` directory contents)
- Repository hooks (`.buildkite/hooks/*` in each pipeline's repo)
- Plugin hooks (vendored vs non-vendored)
- Docker daemon variant (DinD, Docker socket mount, Buildkit, Kaniko, etc.)
- Secret injection mechanism (Secrets Manager, env file, instance profile)
- Build-dir path and any pipeline scripts that hardcode it

## Phase 7.2 — Run Agent Stack for Kubernetes in parallel

Install the controller in the Kubernetes cluster targeting a separate queue (e.g., `kubernetes-canary`). Mirror exactly one production queue:

```yaml
# values.yml
agentStackSecret: "buildkite-agent-token"
config:
  tags:
    - queue=kubernetes-canary
  debug: false
```

Route 5% of jobs to the canary queue:

```yaml
# In the pipeline
steps:
  - label: ":canary: Tests"
    command: "make test"
    agents:
      queue: ${USE_CANARY:-linux-amd64-large}
```

Toggle `USE_CANARY=kubernetes-canary` on selected builds (PR label, env, etc.). Resist the urge to flip all jobs at once.

## Phase 7.3 — Hook parity (the bottleneck)

The single biggest behavioural difference: on Elastic CI Stack for AWS, every job-lifecycle hook runs in one agent process; on Agent Stack for Kubernetes, **checkout and command phases run in separate containers**. Environment variables exported by `pre-checkout` / `checkout` / `post-checkout` are **not** visible in `pre-command` / `command` / `post-command`. The `environment` hook runs once per container, not once per job.

### Translation pattern — sharing values across phases via the workspace

EC2 pattern (works on Elastic CI Stack):

```bash
# .buildkite/hooks/post-checkout
export MY_CUSTOM_VAR="$(determine-value)"
```

```bash
# .buildkite/hooks/pre-command
echo "$MY_CUSTOM_VAR"  # works on EC2, broken on K8s
```

Kubernetes-compatible pattern (works on both):

```bash
# .buildkite/hooks/post-checkout
determine-value > /workspace/my_custom_var
```

```bash
# .buildkite/hooks/pre-command
MY_CUSTOM_VAR=$(cat /workspace/my_custom_var)
```

Alternative: set the variable at pipeline level (`env:` on the step) so the controller injects it into every container.

### Translation pattern — `environment` hook runs once per container

```bash
# .buildkite/hooks/environment
# Guard one-time logic by inspecting the bootstrap phase list
if [[ "$BUILDKITE_BOOTSTRAP_PHASES" == *"checkout"* ]]; then
  echo "Running once in the checkout container"
fi

if [[ "$BUILDKITE_BOOTSTRAP_PHASES" == *"command"* ]]; then
  echo "Running in each command container"
fi
```

### Translation pattern — `checkout: skip: true`

On EC2, hooks still run in the agent process even when checkout is skipped. On Kubernetes, the checkout container is not created; checkout-related hooks do not run at all. If a step depends on a checkout hook side-effect, move the logic into the command phase or into pipeline-level setup.

### Translation pattern — plugin permission on non-root containers

When the command container runs as a non-root user, plugins copied in by the controller (root-owned by default) cause `permission denied` errors. Either run command containers as root (security trade-off) or extend the base controller image to relax permissions:

```dockerfile
# Custom controller image
FROM ghcr.io/buildkite/agent-stack-k8s:0.30.1
RUN chmod -R 755 /buildkite/plugins
```

### Hook audit checklist

For every hook in scope:

- [ ] Does it export environment variables consumed later? If yes, rewrite to workspace files or pipeline `env:`.
- [ ] Does it assume `$BUILDKITE_BUILD_PATH` / `$BUILDKITE_BUILD_CHECKOUT_PATH`? Verify the value under the pinned chart version.
- [ ] Does it call `docker` directly assuming a daemon on the host? See Phase 7.4.
- [ ] Does it write to absolute paths outside `/workspace`? Container filesystems are ephemeral; paths must be volume-mounted.
- [ ] Does it run logic intended for once-per-job in `environment`? Add the bootstrap-phase guard.

## Phase 7.4 — Docker daemon parity

EC2 stacks typically run Docker on the host. Kubernetes provides several alternatives, each with trade-offs.

| Option | When to use | Trade-offs |
|---|---|---|
| **Docker-in-Docker (DinD)** | Direct port of EC2 Docker behaviour | Requires privileged containers; weaker security boundary |
| **Buildkit** | Modern Docker builds, registry caching | Build-only — not a full Docker daemon for arbitrary `docker run` |
| **Kaniko** | Building images in unprivileged pods | Build-only; no `docker run` support; slower than Buildkit |
| **Depot** | Hosted remote-builder service | External dependency, paid; fastest builds in many benchmarks |
| **namespace.so** | Hosted ephemeral environments | External dependency; admin surface separate from Buildkite UI |

See `pages/agent/self_hosted/agent_stack_k8s/{dind,buildkit,kaniko,depot,namespace}_container_builds.md` for each integration's worked example.

Decision rule: if the existing EC2 pipeline uses `docker run` for non-build workloads (test isolation, side-car databases), choose DinD. If the pipeline only builds and pushes images, prefer Buildkit or Kaniko.

## Phase 7.5 — Cutover queue by queue

For each queue:

1. Replicate the queue on Kubernetes (same key, prefixed with `-k8s` during transition).
2. Route 5% of traffic via the routing toggle from Phase 7.2.
3. Monitor for 7 days. Track P95 wait time, failure rate, and stalled-job count.
4. If green, raise to 25%, then 50%, then 100% over a further 7 days.
5. Once at 100%, rename the K8s queue to the canonical key and decommission the EC2 stack for that queue.

Never cut over the full cluster in one shot.

## Phase 7.6 — Decommission

After 30 days of green builds on Kubernetes for a given queue:

- Stop the corresponding Elastic CI Stack CloudFormation stack
- Revoke the AWS-side cluster tokens used by that stack
- Archive the AMI build pipeline for the queue
- Remove the queue's EC2-specific hooks from the agent hooks directory

Document the rollback runbook: if a regression appears after decommission, the recovery path is "re-deploy the CloudFormation stack from the archived template + re-issue cluster tokens", not "live-restore an EC2 fleet".

## Rollback runbook

If a cutover step degrades the queue's reliability:

1. Set the routing toggle back to the EC2 queue.
2. Drain the K8s queue (`kubectl scale deployment agent-stack-k8s -n buildkite --replicas=0`).
3. Confirm new jobs land on EC2.
4. Open a post-incident review captured against the per-queue checklist above.

## Reference docs

- Hook execution differences: `pages/agent/self_hosted/agent_stack_k8s/migrate_from_elastic_ci_stack_for_aws/hook_execution_differences.md`
- Docker daemon migration: `pages/agent/self_hosted/agent_stack_k8s/migrate_from_elastic_ci_stack_for_aws/docker_daemon.md`
- Docker login / ECR / Packages: `pages/agent/self_hosted/agent_stack_k8s/migrate_from_elastic_ci_stack_for_aws/{docker_login,ecr,packages}.md`
- Secrets: `pages/agent/self_hosted/agent_stack_k8s/migrate_from_elastic_ci_stack_for_aws/secrets.md`
