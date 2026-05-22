# Agent Stack for Kubernetes troubleshooting

The expanded gotcha table, controller log spelunking, `podSpec` vs `podSpecPatch` worked examples, and chart-pinning patterns. Pair with `scripts/agent-stack-k8s-diagnose.sh` for one-shot triage.

## podSpec vs podSpecPatch — pick the right tool

The Agent Stack for Kubernetes controller composes a final PodSpec from these inputs, in order:

1. A baseline PodSpec containing one container with the controller's default image and `BUILDKITE_COMMAND`.
2. If the `kubernetes` plugin includes a `podSpec`, that **replaces** the baseline.
3. The `/workspace` volume is applied.
4. Any `extra-volume-mounts` from the plugin are applied.
5. Containers defined by the plugin have their `command` and `args` overridden by the controller.
6. The `agent` container is added.
7. The `checkout` container is added (unless `skip.checkout: true`).
8. `imagecheck-N` init containers are added per unique image.
9. `pod-spec-patch` from controller config is applied (strategic merge patch).
10. `podSpecPatch` from the `kubernetes` plugin is applied (strategic merge patch).
11. Duplicate `VolumeMounts` are removed.

Two implications:

- `podSpec` replaces the baseline entirely. Use it when defining custom command containers from scratch.
- `podSpecPatch` is the *last* mutation. Use it when overriding controller-managed containers (`agent`, `checkout`, `imagecheck-*`) or when applying constraints that must survive the controller's defaults.

### Worked example — set `imagePullPolicy: Always` on every container

The controller's `image-pull-policy` config applies only to command containers. To apply the policy to `agent`, `checkout`, and `imagecheck-*` containers, patch each by name:

```yaml
steps:
  - label: ":docker: Build"
    agents:
      queue: kubernetes
    plugins:
      - kubernetes:
          podSpecPatch:
            containers:
              - name: agent
                imagePullPolicy: Always
              - name: checkout
                imagePullPolicy: Always
              - name: container-0  # First command container
                imagePullPolicy: Always
```

Init containers (`imagecheck-N`) are generated per unique image; patch them in the controller's `pod-spec-patch` rather than the plugin's `podSpecPatch` when the image list is stable.

### Worked example — hugepages resource on the command container

The controller's viper config loader lowercases all keys; Kubernetes resource names like `hugepages-2Mi` are case-sensitive. Set hugepage resources via the plugin's `podSpecPatch`, where keys pass through unmodified:

```yaml
steps:
  - label: ":memory: Hugepages workload"
    agents:
      queue: kubernetes
    plugins:
      - kubernetes:
          podSpecPatch:
            containers:
              - name: container-0
                resources:
                  limits:
                    hugepages-2Mi: "256Mi"
                    memory: "2Gi"
                  requests:
                    hugepages-2Mi: "256Mi"
                    memory: "2Gi"
```

## Expanded gotcha table

| Symptom | Agent / chart range | Root cause | Fix | Verification |
|---|---|---|---|---|
| Repository pre-command hooks silently skipped in command containers | agent ≥3.106.0 with controller ≥0.32.0 | `localHookPath` resolution regression in the agent's hook-discovery refactor; the command container fails to locate `.buildkite/hooks/<phase>` | Pin agent ≤3.105.x on the queue, OR upgrade controller to the patched version; explicitly set `localHookPath` via env on the command container | Run a one-step pipeline whose `pre-command` hook writes a sentinel file; verify presence after the build |
| Pod spec rejected: `hugepages-2mi` not recognized | controller versions using lowercasing viper config | Viper lowercases config keys; K8s rejects non-canonical resource names | Set hugepage resources via the plugin's `podSpecPatch` (which bypasses viper key transform) | `kubectl describe pod` shows the resource accepted; pod schedules |
| Stalled job report contains no actionable failure detail | all current versions | Controller's stalled-job message does not include K8s `Events` (FailedScheduling, ImagePullBackOff, OOMKilled) | Cross-reference Buildkite Job ID against `kubectl -n buildkite get events --sort-by='.lastTimestamp'`; run `scripts/agent-stack-k8s-diagnose.sh` | Controller log + events from the time window identify the failed pod |
| Build directory path changed silently after chart upgrade | chart v0.30.x | Default workspace volume layout shifted in the chart; downstream scripts that hardcoded `$BUILDKITE_BUILD_PATH` broke | Pin chart version; set `workspaceVolume` explicitly; diff `helm template` output before any upgrade | New build dir matches the pinned configuration value |
| `image-pull-policy: Always` not applied to checkout/agent containers | all current versions | Controller `image-pull-policy` applies only to command containers | Apply via `podSpecPatch` per container by name (`agent`, `checkout`, `container-0`, `imagecheck-N`) | `kubectl describe pod` shows `imagePullPolicy: Always` on every container |
| Controller stops accepting new jobs from a cluster queue (`max-in-flight reached`) | controller versions older than v0.27.0 | Limiter state never decremented after some job-completion code paths | Upgrade to the latest controller version; as a workaround, `kubectl -n buildkite rollout restart deployment agent-stack-k8s` | Debug logs no longer show `max-in-flight reached` |
| Wrong exit code from init container affects retry rules | controller older than v0.29.0 | Pod exit code (e.g., 137 OOM) not propagated to the agent's reported job exit code (e.g., 1) | Upgrade to v0.29.0+, which adds the `stack_error` signal reason; add a retry rule for `signal_reason: stack_error` | Retried jobs show `signal_reason: stack_error` in the build UI |
| Job missing `queue` tag — silently skipped by the controller | all versions | Controller requires every job to have an explicit `queue=<key>` tag, even for default cluster queues | Set `agents: { queue: <key> }` at the pipeline or step level | Controller logs no longer show `job missing 'queue' tag, skipping...` |
| Plugin permission failures on non-root command containers | all versions when running command containers as non-root | Plugins owned by root in the controller's base image; non-root command containers cannot read them | Set permissions in the controller config or extend the base image to set `chmod 755` on plugin directories and `chmod 644` on plugin files | Build no longer fails with `permission denied` accessing plugin scripts |
| `environment` hook runs multiple times unexpectedly | all versions on Agent Stack for Kubernetes | The `environment` hook runs *once per container* — once in the checkout container, then again in each command container | Guard one-time logic with `$BUILDKITE_BOOTSTRAP_PHASES` checks; for environment-variable propagation, use shared files under `/workspace` or pipeline-level `env:` | Hook log shows the expected number of executions |
| Environment variables set in `post-checkout` not visible to `pre-command` | all versions on Agent Stack for Kubernetes | Checkout and command phases run in separate containers; bash environment does not cross container boundaries | Write the value to a file under `/workspace`; read it from the command container, OR set the variable at pipeline level (`env:` on the step) | The command container reads the expected value |
| Custom command image fails because `/bin/sh` missing | controller v0.30.0+ when using top-level `image:` attribute | The controller invokes `/bin/sh` to run the Buildkite agent inside the command container | Use a base image with a POSIX shell (Alpine, Debian, etc.); for `FROM scratch` images, switch to `podSpec` with `commandParams.interposer: vector` | Step runs without `executable file not found` error |
| Agents register, run one job, then disappear | all versions when stack runs as single replica without restart policy | Controller pod evicted or restarted; in-flight job state lost | Run two or more controller replicas with leader election; use the Helm chart's `replicaCount` value | `kubectl get pods -n buildkite` shows multiple controller pods; one leader |

## Controller log spelunking

```bash
# Live tail
kubectl logs -n buildkite -l app=agent-stack-k8s -f --tail=200

# Enable debug temporarily without a full redeploy
kubectl set env -n buildkite deployment/agent-stack-k8s BUILDKITE_DEBUG=true

# Grab the controller logs for the past hour
kubectl logs -n buildkite -l app=agent-stack-k8s --since=1h > controller.log
```

Common log signals:

| Log line | Meaning | Action |
|---|---|---|
| `job missing 'queue' tag, skipping...` | A scheduled job has no `queue` tag; controller will not process it | Add `agents: { queue: <key> }` at pipeline or step level |
| `max-in-flight reached` | Controller's in-flight job counter hit the limit | Upgrade controller; restart deployment as workaround |
| `FailedScheduling` event for a Job pod | Cluster lacks resources matching the pod's requests/affinities | Inspect node capacity; tune resource requests via `podSpecPatch` |
| `ImagePullBackOff` event for the command container | Registry credentials missing or image tag does not exist | Configure `imagePullSecrets`; verify image reference |
| `Init container failed` with exit 137 | OOMKilled — likely the `imagecheck-N` init container hit the controller's default memory limit | Raise the init container's memory via `pod-spec-patch` in controller config |

## Chart-pinning pattern

```bash
# Capture the rendered manifest for the current pinned chart
helm template agent-stack-k8s oci://ghcr.io/buildkite/helm/agent-stack-k8s \
    --version 0.29.5 \
    --namespace buildkite \
    --values values.yml \
    > rendered-0.29.5.yaml

# Before upgrading, render the target version and diff
helm template agent-stack-k8s oci://ghcr.io/buildkite/helm/agent-stack-k8s \
    --version 0.30.1 \
    --namespace buildkite \
    --values values.yml \
    > rendered-0.30.1.yaml

diff -u rendered-0.29.5.yaml rendered-0.30.1.yaml | less
```

Treat any change to `workspaceVolume`, `mountPath`, `image-pull-policy`, container names, or default resource requests as a breaking change. Stage the upgrade on a single non-production queue before promoting.

## When to escalate to Buildkite Support

Capture before opening a support ticket:

- Controller version (`kubectl get deploy agent-stack-k8s -n buildkite -o jsonpath='{.spec.template.spec.containers[0].image}'`)
- Chart version (the `--version` flag used in the most recent `helm upgrade`)
- Agent version distribution across the cluster
- Output of `scripts/agent-stack-k8s-diagnose.sh <build-id>` for a representative failure
- Rendered `helm template` output for the current values

The controller repository includes a [`utils/log-collector`](https://github.com/buildkite/agent-stack-k8s/blob/main/utils/log-collector) script that bundles these into a `logs.tar.gz` archive.
