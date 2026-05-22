# Cache volume sizing and tuning

Cache volumes are off by default. Enable per pipeline via `cache:` in YAML, or globally via cluster **Cache Storage → Settings**. Retention is up to 14 days from last use, best-effort. Volumes are non-deterministic — design steps to handle a miss.

This reference is the depth file for the Cache Volumes section of the skill.

## Sizing math

Rough rule: **cache volume size ≥ 2× the largest artifact set the step touches**, with a floor of the default 20 GB.

Examples:

| Workload | Artifact set | Recommended size |
|---|---|---|
| Node monorepo, single `node_modules` | ~3 GB | 20 GB (default) |
| Node monorepo, 50 packages each with `node_modules` | ~25 GB | 50 GB |
| Ruby app, `vendor/bundle` only | ~1.5 GB | 20 GB |
| Go module + build cache | ~10 GB | 30 GB |
| iOS DerivedData + Pods + ~/Library/Caches | 15-40 GB | 60-80 GB |
| Docker layer cache, mid-size app | 5-20 GB | Container cache volumes (cluster toggle); no manual sizing |
| Monorepo git clone, 5+ GB repo | Repo size | Git mirror volumes (cluster toggle); auto-grown |

The minimum size is 20 GB; specifying smaller has no effect. Units are gigabytes specified as `Ng` (e.g. `50g`).

### Step-level vs root-level cache

Root-level `cache:` applies to all steps in the pipeline; step-level merges with the root and overrides size where names collide. Same `name:` at both levels means paths from both are mounted.

```yaml
cache:
  paths:
    - "node_modules"
  size: "100g"

steps:
  - command: "yarn build"
    cache: ".build"

  - command: "rspec"
    cache:
      paths:
        - "vendor/bundle"
      size: "20g"
      name: "bundle-volume"
```

> For YAML key reference (`cache:`, `name:`, `size:`, `paths:`), see the **buildkite-pipelines** skill. This file covers the operational decision of when to use which volume class.

## Container cache vs Git mirror vs internal container registry

Three durable-ish persistence options on hosted Linux. Picking the right one is the central decision:

| Option | What it caches | Determinism | When to use |
|---|---|---|---|
| **Step-level `cache:` paths** | Build dependencies (`node_modules`, `vendor/bundle`), build outputs (`.build`, `dist/`) | Non-deterministic, best-effort, 14d | The default for most pipeline caches |
| **Container cache volumes** (Linux only, cluster toggle) | Docker images between builds, layered into the daemon | Non-deterministic; a `docker pull` may hit the cache or fall through to origin | Layer-cache for `docker build`; not for "I always need this exact image" |
| **Git mirror volumes** (cluster toggle) | Bare clones of source repositories | Non-deterministic but high hit rate for large repos | Monorepos slow to clone (>30s clone time) |
| **Internal container registry** (Enterprise only) | OCI images built in your pipeline | **Deterministic** — pulls from the registry are guaranteed to return exactly the pushed image | OCI images you need deterministically every job; custom agent base images (see `references/image-lifecycle-patterns.md`) |

The critical rule from `internal_container_registry.md`: *"If you need deterministic storage for OCI images... you can use your internal container registry instead of a cache volume."*

### Decision shortcuts

- "I need this image pulled to be exactly the image I pushed" → internal container registry.
- "I want `docker build` to be faster when layers haven't changed" → container cache volumes.
- "Our `git clone` is the slow step" → git mirror volumes.
- "Restore my `node_modules`" → step-level `cache:` paths.
- "Same iOS DerivedData every job" → step-level `cache:` paths (macOS) plus expect misses.

## `BUILDKITE_CACHE_CONCURRENCY`

Controls how many cache volumes the agent processes in parallel during save and restore. Default `2`.

```yaml
steps:
  - command: "your-build-command"
    env:
      BUILDKITE_CACHE_CONCURRENCY: 4
    cache:
      paths:
        - "node_modules"
        - ".build"
        - "vendor/bundle"
```

Setting `BUILDKITE_CACHE_CONCURRENCY: 0` (or any negative value) tells the agent to use the number of available CPU cores. Raise the value when:
- The step has 3+ named cache volumes.
- Cache save/restore time is a significant fraction of total step time.
- The instance shape has CPU headroom during save/restore (most do; the operations are I/O-bound).

Do not raise it if:
- The cache volumes are large (>50 GB each); parallelism amplifies I/O contention.
- The pipeline has a single cache volume — concurrency makes no difference.

## Workload-specific examples

### Node monorepo

```yaml
steps:
  - label: ":nodejs: Test"
    command: |
      yarn install --frozen-lockfile
      yarn test
    cache:
      paths:
        - "node_modules"
        - "**/node_modules"  # workspaces
      size: "50g"
      name: "node-monorepo"
```

### Go binary cache

```yaml
steps:
  - label: ":golang: Test"
    command: |
      go test ./...
    env:
      GOCACHE: /cache/bkcache/gocache
      GOMODCACHE: /cache/bkcache/gomodcache
    cache:
      paths:
        - "gocache"
        - "gomodcache"
      size: "30g"
      name: "go"
```

Note the explicit `GOCACHE` / `GOMODCACHE` env vars pointing to the cache mount root (`/cache/bkcache`). Without these, Go writes to `~/.cache/go-build`, which is not on the cache volume.

### Ruby with Bundler

```yaml
steps:
  - label: ":ruby: RSpec"
    command: |
      bundle config set path 'vendor/bundle'
      bundle install --jobs=4
      bundle exec rspec
    cache:
      paths:
        - "vendor/bundle"
      size: "20g"
      name: "bundler"
```

`bundle config set path 'vendor/bundle'` puts gems on disk where the cache picks them up. Default `bundle install` writes to `~/.bundle`, which is not cached.

### iOS — DerivedData and Pods

```yaml
steps:
  - label: ":ios: Build"
    command: |
      bundle install
      bundle exec pod install
      bundle exec fastlane build
    cache:
      paths:
        - "vendor/bundle"
        - "Pods"
        - "~/Library/Caches/CocoaPods"
        - "~/Library/Developer/Xcode/DerivedData"
      size: "80g"
      name: "ios-build"
```

iOS pipelines are the most cache-sensitive workload on hosted. DerivedData regeneration on a cache miss is the dominant cost of a cold build.

## macOS sparse-bundle caveat

Cache volumes on macOS are sparse bundle disk images, not bind mounts. Practical implications:

- First-touch read latency is higher than Linux NVMe-backed volumes.
- Random small-file I/O (Pods directory, DerivedData) is the slowest pattern; large sequential reads are fast.
- Sparse bundle integrity occasionally requires the volume to be reformatted on miss — the agent handles this transparently but it can extend a cold-start by tens of seconds.

Do not size macOS cache volumes minimally. The hit-rate floor on a small volume is lower because eviction is more aggressive.

## Cost implications

Cache volumes and Git mirroring carry no additional cost beyond the per-second agent execution. Internal container registry usage is included in Enterprise plans. The only volume-related cost is opportunity cost: agent time spent saving and restoring a volume that is rarely hit.

If the cache hit rate is < 30% over a 7-day window, the cache is more expensive (in agent-seconds) than running uncached. Measure before scaling out.

## Cross-references

- For OCI-image determinism via internal container registry, see `references/image-lifecycle-patterns.md`.
- For the macOS reserved-path trap (`/tmp`, `/private`), see `references/macos-build-gotchas.md`.
- For YAML syntax of `cache:`, `name:`, `size:`, `paths:`, see the **buildkite-pipelines** skill.
