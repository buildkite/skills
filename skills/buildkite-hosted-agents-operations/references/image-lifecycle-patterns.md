# Hosted agent image lifecycle patterns

Anchor: Linear A-500 (Groq) — *"the only way to update images is copy-paste Dockerfile in UI, breaking auth-bootstrap flows."* This reference is the long-form workshop for that gap.

## Mode 1 — Default Buildkite image

Ubuntu 22.04, pre-installed: `docker`, `docker-compose`, `docker-buildx`, `git-lfs`, `node`, `aws-cli`. The `buildkite-agent` and `docker` binaries are layered into the job environment at runtime, so the base image does not bundle them.

Use this mode for:
- Proof-of-concept and first-week pipelines.
- Workloads whose tooling fully matches the default set.
- Single-language pipelines where Homebrew (macOS) or `apt-get` in a single early step is acceptable.

Do not stay on this mode if any of the following hold:
- The pipeline runs more than a handful of times per day and the tooling install is non-trivial — every job pays the cost.
- Tool versions need pinning for reproducibility.
- Network installs in CI have caused flakes.

## Mode 2 — Custom agent image via Buildkite UI Dockerfile editor

Created under **Agents → cluster → Agent Images → New Image**. The Dockerfile must extend the fixed `FROM` line that the UI provides; user changes to `FROM`, `USER`, or `UID`/`GID` env vars are unsupported.

Required tools in the image (verbatim from `linux/custom_agent_images.md`):

- `git`
- `ca-certificates`
- `bash`

Skipping `ca-certificates` is the single most common silent failure: the agent cannot establish TLS to the Buildkite control plane and the job never starts. There is no obvious error in the build page.

Example Dockerfile body — `awscli` and `kubectl`:

```dockerfile
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git \
    ca-certificates \
    bash \
    awscli \
 && rm -rf /var/lib/apt/lists/*

RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl \
 && chmod +x kubectl \
 && mv kubectl /usr/local/bin/
```

### The immutable image factory rule

Once an image is created in the UI, **the Dockerfile cannot be edited**. To update an image:

1. Detach the image from any queue using it (Base image tab → switch to another image).
2. Delete the image (Agent Images page → Delete).
3. Create a new image with the corrected Dockerfile.
4. Re-attach the new image to the queue.

Treat the UI editor as an immutable image factory: write the Dockerfile in your repo first, paste it in once, and version-control it locally. The UI is not a working surface — A-500 surfaced exactly this friction.

### Attaching the image to a queue

**Set the default image for a queue** (Buildkite UI):

1. Agents → cluster → Queues → the hosted Linux queue.
2. Base image tab.
3. Agent image dropdown → select the image.
4. Save settings.

**Per-step image override** (pipeline.yml):

```yaml
agents:
  queue: "hosted-linux"
  image: "DevOps Agent Image"

steps:
  - label: "Build"
    command: "make build"

  - label: "Run integration tests"
    command: "make integration-test"
    agents:
      image: "Default Agent Image"
```

The `image:` value in YAML must match the image's Name field in the UI exactly.

## Mode 3 — Custom Image URL via the internal container registry

Build the image in a pipeline step, push to `$BUILDKITE_HOSTED_REGISTRY_URL`, and reference the resulting tag from the queue's **Image URL** field (or per-step in pipeline.yml). This is the mode A-500 was asking for.

> Constraints. The internal container registry is **Enterprise-only**. The custom **Image URL** feature (`agentImageRef`) is currently in **private preview** — contact `support@buildkite.com` to enable. Flag both constraints to the customer before recommending this path.

### Full build-and-push pipeline (verbatim docs pattern)

```yaml
agents:
  queue: "linux-small"

steps:
  - key: create_custom_base_image
    label: ":docker: Create custom base image"
    if_changed:
      - ".buildkite/Dockerfile.build"
      - ".buildkite/pipeline.yml"
    command: |
      docker buildx build \
        --file .buildkite/Dockerfile.build \
        --build-arg BUILDKITE_BUILD_NUMBER="$$BUILDKITE_BUILD_NUMBER" \
        --platform linux/amd64 \
        --tag "${BUILDKITE_HOSTED_REGISTRY_URL}/base:latest" \
        --progress plain \
        --push .

  - key: use_custom_base_image
    label: ":package: Use custom base image"
    image: "${BUILDKITE_HOSTED_REGISTRY_URL}/base:latest"
    parallelism: 3
    depends_on: create_custom_base_image
    command: |
      echo "Using ${BUILDKITE_HOSTED_REGISTRY_URL}/base:latest"
```

### Multi-arch build

For mixed AMD64 + ARM64 hosted Linux queues, build both platforms in one push:

```bash
docker buildx build \
  --file .buildkite/Dockerfile.build \
  --platform linux/amd64,linux/arm64 \
  --tag "${BUILDKITE_HOSTED_REGISTRY_URL}/base:${BUILDKITE_BUILD_NUMBER}" \
  --tag "${BUILDKITE_HOSTED_REGISTRY_URL}/base:latest" \
  --push .
```

### Setting the queue's Image URL

- **UI:** Agents → cluster → Queues → queue → Base image tab → **Image URL** field → save. Format: `registry.url/image-name:tag`. For internal registry: `${BUILDKITE_HOSTED_REGISTRY_URL}/base:latest`.
- **REST API:** `PATCH` the queue with `agentImageRef` inside the `hostedAgents` object. `instanceShape` must also be specified on the same request (re-send the current value if unchanged).
- **GraphQL:** `clusterQueueUpdate` mutation, `agentImageRef` field on `hostedAgents` input.
- **Terraform:** `agent_image_ref` on the `hosted_agents.linux` block of `buildkite_cluster_queue`.

### Public-registry fallback

If the Enterprise / private-preview constraints rule out the internal registry, a public registry image works:

```
docker.io/your-org/your-image:tag
my-registry.example.com/your-org/your-image:tag
```

Caveat from `linux/custom_agent_images.md`: Docker Hub and other public registries can rate-limit Buildkite's image pulls. The docs explicitly recommend mirroring to the internal container registry to avoid this. Public registry is a stepping stone, not a final destination.

## Hooks embedded in a custom image

Job-lifecycle hooks supported: `environment`, `pre-checkout`, `checkout`, `post-checkout`, `pre-command`, `command`, `post-command`, `pre-artifact`, `post-artifact`, `pre-exit`.

Not supported on hosted: `pre-bootstrap`, agent-lifecycle hooks. Those run outside the job and have no execution surface on hosted.

### Single hooks directory

```dockerfile
ENV BUILDKITE_ADDITIONAL_HOOKS_PATHS=/custom/hooks
COPY ./hooks/*.sh /custom/hooks/
RUN chmod +x /custom/hooks/*.sh
```

### Multiple hooks directories

```dockerfile
ENV BUILDKITE_ADDITIONAL_HOOKS_PATHS=/custom/global-hooks:/custom/team-hooks
COPY ./global-hooks/*.sh /custom/global-hooks/
COPY ./team-hooks/*.sh /custom/team-hooks/
RUN chmod +x /custom/global-hooks/*.sh /custom/team-hooks/*.sh
```

### Do not target `/buildkite/agent/hooks`

`/buildkite/agent/hooks` is the global agent hooks location. On hosted it is fixed and read-only when a job starts. Files copied into that path during image build are overwritten before the first hook runs. Always use a separate path under `BUILDKITE_ADDITIONAL_HOOKS_PATHS`.

> For what hook scripts should contain at runtime — when to use `environment` vs `pre-command`, exit codes, redaction — see the **buildkite-agent-runtime** skill.

## "Issues with starting a job" — decoder

From `linux/custom_agent_images.md`, expanded with the operational signals:

| Signal | Most likely cause | First check |
|---|---|---|
| Job hangs in "waiting for agent" indefinitely; no logs | Configured image not found in the cluster's registry | Confirm image tag exists in `$BUILDKITE_HOSTED_REGISTRY_URL` (or public registry); confirm the image is in the *same cluster* as the queue (images are cluster-scoped) |
| Agent starts but immediately exits with no TLS-ish log | `ca-certificates` missing from the image | Rebuild image with `ca-certificates`; confirm with `update-ca-certificates --verbose` in a layer |
| Intermittent "image pull failed" from public registry | Docker Hub or other public-registry rate-limit | Mirror the image into `$BUILDKITE_HOSTED_REGISTRY_URL` and reference it from there |
| Job starts but `git clone` fails | `git` missing from the image | Add `git` (and `git-lfs` if LFS objects are present) |
| Hooks do not run | `BUILDKITE_ADDITIONAL_HOOKS_PATHS` set to `/buildkite/agent/hooks` (overwritten); or hook scripts not executable | Set `BUILDKITE_ADDITIONAL_HOOKS_PATHS` to a different path; `chmod +x` in the Dockerfile |
| Image change does not appear to take effect | Old image still cached on the queue; UI Dockerfile cannot be edited | If using UI image: delete and recreate; if using Image URL: bump the tag (`:v2`, not `:latest`, for cache busting) |

## Versioning recommendation

For Mode 3, do not push everything as `:latest`. Tag with both a stable rolling tag (e.g. `:latest` or `:main`) and an immutable build-pinned tag (e.g. `:<git-sha>` or `:<build-number>`). Set the queue's **Image URL** to the immutable tag for production queues, and bump it through CI when the build-and-push step succeeds. The bundled `scripts/hosted-image-build-and-push.sh` outputs both tags.
