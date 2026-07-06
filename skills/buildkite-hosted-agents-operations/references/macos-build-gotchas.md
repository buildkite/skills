# macOS hosted agent build gotchas

Anchors: 7 customers escalated Mac/iOS or hosted-image pain in the last 12 months — Tinder, SafetyCulture, Doordash, Twilio, Ramp, Airtable, Improbable. Linear PS-1000 (Equilibrium Energy) anchors the reserved-path filesystem trap. This reference is the depth file for the macOS section of the skill.

## Hard rules

- **No custom macOS base image.** Apple silicon only. Software is installed in-job via Homebrew; persistence is via cache volumes. There is no Dockerfile-like surface for macOS.
- **Xcode tracks Apple by one week.** Buildkite catches up one week after each Apple release (Beta, RC, official). Pin Xcode explicitly. Never assume "latest available".
- **`/tmp` and `/private` are reserved cache paths.** Mount sub-paths only.
- **macOS jobs run up to 4 hours by default.** Longer is available on request — `support@buildkite.com`.
- **Cache volumes on macOS use sparse bundle disk images**, not bind mounts. Functionally similar but performance characteristics differ from Linux NVMe-backed volumes.

## Xcode and runtime matrix

As of 2026-05-20, sourced from `macos.md`. This table rotates — confirm against the docs page before quoting versions to a customer.

| macOS | Xcode versions available | iOS runtimes (selected) |
|---|---|---|
| **Tahoe** 26.3.1 | 26.3, 26.2, 26.1.1, 26.1, 26.0.1, 26.0, 16.4 | 26.2, 26.1, 26.0, 18.6, 17.5 |
| **Sequoia** 15.7.4 | 26.4-Beta2, 26.4-Beta, 26.3-RC2, 26.3, 26.2, 26.1.1, 26.1, 26.0.1, 26.0, 16.4, 16.3, 16.2, 16.1, 16.0, 15.4 | 26.4-beta2 through 15.5 |
| **Sonoma** 14.8.3 | 16.3, 16.2, 16.1, 16.0, 15.4, 15.3, 15.2, 15.1, 14.3.1 | 18.4 through 15.5 |

Decision rule: for Xcode ≥26, choose Tahoe or Sequoia. Sonoma is end-of-life for new Xcode adoption.

For tvOS, visionOS, and watchOS runtimes, consult `macos.md` directly — the runtime lists are long and rotate independently of the Xcode list.

## Pinning Xcode in CI

In a Fastfile lane:

```ruby
lane :build do
  xcversion(version: "16.4")
  build_app(scheme: "AppName", workspace: "AppName.xcworkspace")
end
```

Or directly via `xcodebuild`:

```bash
sudo xcode-select -s /Applications/Xcode_16.4.app
xcodebuild -version
```

Pin to a specific point release, not a major. `xcversion(version: "16")` is ambiguous and may drift.

## Homebrew packages available by default

Default-installed (as of 2026-05-20, versions rotate per macOS version): `ant`, `applesimutils`, `aria2`, `awscli`, `azcopy`, `azure-cli`, `bazelisk`, `bicep`, `carthage`, `cmake`, `cocoapods`, `curl`, `deno`, `docker`, `docker-buildx`, `fastlane`, `gcc@13`, `gh`, `git`, `git-lfs`, `gmp`, `gnu-tar`, `gnupg`, `go`, `gradle`, `httpd`, `jq`, `kotlin`, `libpq`, `llvm`, `llvm@15`, `maven`, `mint`, `nginx`, `node`, `openssl@3`, `p7zip`, `packer`, `perl`, `php`, `pkgconf`, `postgresql@14`, `python@3.14`, `r`, `rbenv`, `rbenv-bundler`, `ruby`, `ruby@3.4`, `rust`, `rustup`, `selenium-server`, `swiftformat`, `swiftlint`, `tmux`, `unxip`, `wget`, `wireguard-go`, `wireguard-tools`, `xcbeautify`, `xcodes`, `yq`, `zstd`.

To identify the exact version your queue has: Agents → cluster → queue → Base image tab → **Specifications → Homebrew packages**.

Custom Homebrew installs in-job are supported; cache the `/opt/homebrew` install via a cache volume to avoid reinstalling on every job. `BREW_PATH_TO_CACHE=/opt/homebrew/Cellar` is a reasonable starting point.

## fastlane troubleshooting tree

Symptoms surface bottom-up from `fastlane` to the underlying tool. Always run with `--verbose` first; the simplified errors mask the actual failure.

| Symptom | Likely cause | First fix |
|---|---|---|
| `The sandbox is not in sync with the Podfile.lock` | `Pods` directory is (correctly) not committed but `pod install` is not running in CI | Add `cocoapods()` to the lane; if persists, `cocoapods(clean_install: true)` |
| `bundler: failed to load command: fastlane` with `mutex_m`/`ostruct`/`abbrev` warnings | Ruby ≥3.4 dropped these from default gems; hosted Macs ship Ruby 3.4+ | Add `gem 'mutex_m'`, `gem 'ostruct'`, `gem 'abbrev'` to the `Gemfile` |
| `CodeSign ... Exit status: 65` | Cert, profile, keychain, or team-ID mismatch | Switch to `fastlane match`; verify with `security find-identity -v -p codesigning` |
| `error: No profile for team 'XYZ' matching 'AppName Dev' found` | Provisioning profile missing or bundle-ID mismatch | `match(type: "development")` to fetch fresh profile; confirm bundle ID in `build_app` |
| `error: There is no account for team 'XYZ'` | App Store Connect API key not loaded | Provide `APP_STORE_CONNECT_API_KEY_KEY_ID`, `_ISSUER_ID`, and `_KEY` via cluster secrets |
| `Could not find action 'cocoapods'` | `fastlane-plugin-cocoapods` not in `Pluginfile` | `fastlane add_plugin cocoapods` locally, commit `Pluginfile` |
| `xcodebuild: error: Unable to find a destination matching the provided destination specifier` | Simulator runtime for the target iOS not installed | Pin to an available runtime from the macOS version's runtime list; or fall back to `generic/platform=iOS Simulator` |
| Build hangs at `Code signing` phase indefinitely | Keychain locked or prompting for password | `security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"` before `build_app` |
| `bundle install` slow on every job | `vendor/bundle` not cached | Add `vendor/bundle` to the step's `cache:` paths |
| `pod install` slow on every job | `Pods` and CocoaPods spec repo not cached | Cache `Pods` plus `~/.cocoapods` and `~/Library/Caches/CocoaPods` |

### Essential debugging commands

Run via terminal access on a stuck job:

```bash
# Code signing identities
security find-identity -v -p codesigning

# Keychain state
security list-keychains
security default-keychain

# Provisioning profiles
ls -la ~/Library/MobileDevice/Provisioning\ Profiles/

# Fastlane gym logs
ls -la "$HOME/Library/Logs/gym/"
```

## `fastlane match` setup walkthrough

The hosted Mac is ephemeral. Every job starts with no signing identities loaded. `fastlane match` makes that fast; hand-rolling makes it a nightmare.

Initial setup (one-time, run locally):

```bash
fastlane match init
# Choose storage: git, s3, gcs, or google_cloud
# Configure the Matchfile
fastlane match development
fastlane match appstore
```

In CI, the lane:

```ruby
lane :build do
  setup_ci  # creates a temporary keychain for the CI job
  match(type: "appstore", readonly: true)
  build_app(scheme: "AppName", workspace: "AppName.xcworkspace")
end
```

Set `readonly: true` in CI so the build cannot accidentally rotate certificates. Store the match decryption password and (if using git storage) the deploy key as cluster secrets, not in the repo.

## Reserved-path filesystem trap (PS-1000)

On macOS hosted, the instance is a full macOS snapshot. The OS owns `/tmp` and `/private`. Cache volume mounts at exactly those paths are silently rejected.

| Path | Cache mount OK? |
|---|---|
| `/tmp` | No |
| `/tmp/volume` | Yes |
| `/private` | No |
| `/private/var/cache/things` | Yes |
| `$HOME/Library/Caches/Whatever` | Yes |
| `/Users/agent/buildkite/builds/...` | Yes (this is the working directory) |

PS-1000 caused build-directory paths to change in `agent-stack-k8s` v0.30.1 — that issue is self-hosted-side, but the read-only filesystem rule is the same family of trap on hosted macOS.

## Cross-references

- macOS cache-volume sizing math: see `references/cache-volume-sizing.md`.
- Custom Linux image build, push, and queue attachment: see `references/image-lifecycle-patterns.md`.
- For self-hosted macOS agents (your own Mac mini fleet) — outside this skill's scope, see **buildkite-agent-infrastructure**.
