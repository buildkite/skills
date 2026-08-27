# Buildkite Cache Configuration Reference

Detailed semantics for `.buildkite/cache.yml`, cache key resolution, storage URLs, and the save/restore lifecycle.

## Configuration file resolution

1. `--cache-config-file` / `BUILDKITE_CACHE_CONFIG_FILE`, when set, is used as-is.
2. Otherwise exactly one of `.buildkite/cache.yml` or `.buildkite/cache.yaml` (relative to the working directory) must exist. Zero matches or both present is an error.

## Validation rules

- `name`: non-empty, must match `^[a-zA-Z0-9_]+$`. Names identify caches for `--name` filtering and log output; they are not part of the cache key.
- `cache_key`: non-empty ordered list. At most one part may set `fallback_limit: true`.
- `target_paths`: non-empty, no duplicates, no null bytes. A path may be relative, absolute, or `~`-prefixed, but must not be a bare anchor (`~`, `.`, `/`, or a Windows volume root). Resolved target paths must not overlap (one nested inside another).

## Key part reference

Every part resolves to a string at command run time, against the live environment and filesystem.

### Literal

```yaml
cache_key:
  - v1
```

Any plain YAML scalar. Use a leading literal as a manual generation/version number: bumping it abandons all previous entries.

### `agent`

```yaml
- { agent: os }        # runtime GOOS: linux, darwin, windows
- { agent: arch }      # runtime GOARCH: amd64, arm64
- { agent: branch }    # $BUILDKITE_BRANCH
- { agent: pipeline }  # $BUILDKITE_PIPELINE_SLUG
- { agent: step }      # $BUILDKITE_STEP_KEY, falling back to $BUILDKITE_STEP_ID
```

`os` and `arch` come from the agent binary itself, not environment variables. `step` prefers the human-assigned step key; only steps without a `key:` fall back to the (per-build, random) step ID — give steps stable keys when using `{ agent: step }`, or caches never match across builds.

### `env`

```yaml
- { env: NODE_VERSION }
```

Resolves to the variable's value; an unset variable resolves to the empty string (not an error). Prefer `env` parts over baking versions into literals when the version is already exported in the job environment.

### `checksum`

```yaml
- { checksum: package-lock.json }
- { checksum: [go.sum, "**/go.mod", "patches/*.patch"] }
```

- Accepts one path or an array of paths and glob patterns. Globs support `*`, `?`, and `**`.
- Paths resolve relative to the working directory. `~` is **not** expanded in checksum paths.
- Glob traversal does not follow symlinked directories.
- A single literal (non-glob) path is hashed by contents alone — renaming that file while keeping its contents identical produces the same digest.
- With an array or any glob pattern, all matched regular files are deduplicated and sorted, then folded into one SHA-256 digest that covers each file's path and contents — renaming a matched file changes the digest even if contents are identical.
- A literal (non-glob) path must exist and be a regular file, or the command errors.
- If all patterns together match zero files, the command errors ("matched no files") rather than producing an empty digest.

### `fallback_limit`

```yaml
- { agent: arch, fallback_limit: true }
- { checksum: package-lock.json, fallback_limit: true }   # also valid on checksum and env parts
```

Marks the mandatory/optional boundary. Parts at or before the marked part are mandatory; parts after it are optional. Fallback matching drops optional parts from right to left and returns the **newest** entry matching the remaining prefix. Only one part per cache may carry the marker. Key part values must not contain the `#` character.

`fallback_limit` attaches only to mapped sources (`agent`, `checksum`, `env`). A literal part is a plain scalar and cannot carry the marker — `{ literal: v1, fallback_limit: true }` is rejected as an unknown source. To put the boundary after a literal, attach the marker to the mapped part preceding the optional parts instead.

## Environment variables

| Variable | Equivalent flag | Notes |
|----------|-----------------|-------|
| `BUILDKITE_CACHE_NAMES` | `--name` | Comma-separated cache names; use repeated `--name` flags on the CLI |
| `BUILDKITE_AGENT_CACHE_REGISTRY` | `--registry` | Default `~` = cluster default registry |
| `BUILDKITE_AGENT_CACHE_STORE_URL` | `--cache-store-url` | Required on self-hosted agents |
| `BUILDKITE_CACHE_CONFIG_FILE` | `--cache-config-file` | Overrides default file resolution |
| `BUILDKITE_CACHE_CONCURRENCY` | `--concurrency` | Default 2; `0` or negative uses all CPUs. Currently applies only to save — restore ignores it and always uses one worker per CPU |

The commands also require the standard in-job agent environment (`BUILDKITE_AGENT_ACCESS_TOKEN`, agent endpoint), so they only work inside a running job or an environment that replicates it.

## Store URLs

| Scheme | Example | Use |
|--------|---------|-----|
| `s3://` | `s3://my-bucket/prefix?region=us-east-1` | Self-hosted agents with an S3(-compatible) bucket |
| `file://` | `file:///tmp/bk-cache` | Local testing only |

S3 URL query parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `region` | `us-east-1` | Bucket region. Not read from the AWS config chain — always set this explicitly for buckets outside `us-east-1` |
| `endpoint` | AWS default | Custom endpoint for S3-compatible stores (MinIO, R2) |
| `use_path_style` | `false` | Path-style addressing for S3-compatible stores |
| `concurrency` | SDK default (upload); tuned high (download) | Multipart transfer parallelism |
| `part_size_mb` | SDK default (upload); tuned high (download) | Multipart part size |

Credentials are **ambient**: the AWS default credential chain (instance profile, IRSA, environment variables, shared config). Buildkite issues no storage credentials. Required S3 actions: `s3:GetObject` and `s3:PutObject`. These also cover the self-copy the agent performs after a download to refresh the object's last-modified timestamp (so lifecycle rules keyed on last-modified retain hot blobs) — there is no separate `s3:CopyObject` IAM action. The refresh is best-effort and never fails the restore: copy errors are ignored, objects over S3's 5 GB CopyObject limit cannot be refreshed, and each object is refreshed at most once per 12 hours — so size lifecycle windows to tolerate missed refreshes, especially for large archives.

Hosted agents use a Buildkite-provided store automatically; do not set a store URL there.

## Save lifecycle

Per cache (in parallel, up to `--concurrency`):

1. Resolve the cache key against the live environment and filesystem.
2. Verify every target path exists (error if not).
3. Check the registry for an existing entry at the exact key — if present, stop: "Cache already exists, not saving".
4. Build a single zip archive of all target paths (zstd-compressed entries, deterministic timestamps) and compute its SHA-256.
5. Register the pending entry with the registry, upload the archive to the store under its digest (content-addressed), then commit the entry.

The existence check (step 3) is not atomic with the commit (step 5): concurrent saves under the same key can both observe a miss and both upload, and the later commit replaces the earlier entry. An uncommitted upload (for example, a job killed mid-save) is discarded automatically after a few minutes.

## Restore lifecycle

Per cache (in parallel, one worker per CPU — restore currently ignores `--concurrency`):

1. Resolve the cache key; ask the registry for an entry — exact match first, then fallback prefix matching (newest wins) when a `fallback_limit` is set.
2. No entry → cache miss; the command succeeds.
3. Download the archive from the store and verify its SHA-256.
4. Three specific blob problems — missing object, digest mismatch, unreadable archive — degrade to a cache miss and invalidate the stale registry entry so later builds skip it. Other failures (invalid configuration or store settings, registry/API errors after retries, store permission or network errors, cleanup or extraction errors) are returned as command errors and can fail the step.
5. Delete each target path (with guards against removing the working directory, home directory, or filesystem roots), then extract.

Archives are portable: paths are stored relative to anchors (home directory, working directory, or volume root) that re-resolve on the restoring machine, so caches move cleanly across agents, users, and checkout directories.

## Entry expiry

Cache entries expire automatically after a few days. An exact-key restore refreshes the expiry; fallback restores and existence checks do not. Store blobs are not deleted by Buildkite — on self-hosted stores, configure bucket lifecycle rules (keyed on last-modified time) to expire cold blobs.
