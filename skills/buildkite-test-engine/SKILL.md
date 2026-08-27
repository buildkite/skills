---
name: buildkite-test-engine
description: >
  This skill should be used when the user asks to "split tests across machines",
  "set up test splitting", "parallelize test suite", "detect flaky tests",
  "quarantine flaky tests", "configure test collectors", "speed up tests",
  "set up bktec", "configure test engine", or "reduce flaky test failures".
  Also use when the user mentions bktec, Test Engine, test suites,
  BUILDKITE_TEST_ENGINE_* environment variables, BUILDKITE_ANALYTICS_TOKEN,
  test-collector plugin, test reliability scores, test timing data,
  or asks about Buildkite test splitting and flaky test management.
---

# Buildkite Test Engine

Test Engine splits test suites across parallel machines and identifies flaky tests. Two components: **test collectors** gather timing data from runs, and **bktec** (the CLI) uses that data for intelligent splitting and automatic flaky test management.

## Quick Start

Three steps: create a suite, add a collector, run bktec with parallelism.

**1. Create a test suite** in the Buildkite dashboard: Test Suites > New test suite > Set up suite. Copy the suite API token.

**2. Add the test-collector plugin** to start gathering timing data:

```yaml
steps:
  - label: ":rspec: Tests"
    command: "bundle exec rspec"
    plugins:
      - test-collector#v2.0.0:
          files: "tmp/rspec-*.xml"
          format: "junit"
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

**3. After ~1-2 weeks of data**, switch to bktec for intelligent splitting:

```yaml
steps:
  - label: ":rspec: Tests %n"
    command: bktec
    parallelism: 10
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "my-suite"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "rspec"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/rspec-result.json"
```

> For `parallelism:` YAML syntax and pipeline structure, see the **buildkite-pipelines** skill.

## How Test Engine Works

Test Engine is a two-phase system:

**Phase 1 — Data collection:** Test collectors send execution timing and pass/fail results to the Test Engine API after every run, building a historical profile for each test.

**Phase 2 — Smart splitting + flaky management:** bktec reads historical data to partition tests across parallel agents by runtime, and to identify and quarantine flaky tests.

### The Two Token Types

Test Engine uses two different tokens:

| Token | Environment Variable | Purpose | Where to get it |
|-------|---------------------|---------|-----------------|
| **Suite API token** | `BUILDKITE_ANALYTICS_TOKEN` | Collectors use this to send test data to a specific suite | Test suite settings page |
| **API access token** | `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN` | bktec uses this to fetch timing data and test plans | Personal Settings > API Access Tokens (requires `read_suites` scope) |

These are not interchangeable.

## Creating Test Suites

Create via the dashboard: **Test Suites > New test suite > Set up suite**. The suite settings page shows the **suite API token** (for collectors) and the **suite slug** (for bktec).

> For creating suites via REST API, see the **buildkite-api** skill.

### Suites and pipelines

Pipelines and suites do not need a one-to-one relationship. Multiple pipelines can report to the same suite (monorepos), and one pipeline can report to multiple suites (separate unit/integration suites).

## Test Collectors

Install the collector for the test framework, set `BUILDKITE_ANALYTICS_TOKEN`, and run tests normally. Collectors must be configured before bktec splitting works.

- **Ruby** — `buildkite-test_collector` gem (RSpec, Minitest)
- **JavaScript** — `buildkite-test-collector` npm package (Jest, Playwright, Cypress)
- **Python** — bktec handles collection directly when runner is `pytest`
- **Go / other languages** — JUnit XML upload via the analytics API
- **Any framework** — `test-collector` Buildkite plugin for file-based upload

> For per-framework setup instructions and configuration examples, see **`references/collectors.md`**.

## bktec CLI

bktec is the CLI that replaces the test runner command in pipeline steps. It fetches a test plan from the Test Engine API balanced by historical runtime, runs the assigned subset, uploads results, and optionally retries failed tests.

### Installation

Pre-installed on Buildkite hosted agents. For self-hosted agents:

```bash
curl -sL https://github.com/buildkite/test-engine-client/releases/latest/download/bktec-linux-amd64 -o /usr/local/bin/bktec
chmod +x /usr/local/bin/bktec
```

### Supported test runners

`rspec` (supports split-by-example), `jest`, `playwright`, `cypress`, `pytest`, `pytest-pants`, `go`, `cucumber` — all split by file/spec/package except RSpec which also supports split-by-example.

If bktec cannot reach the API or no timing data exists, it falls back to file-count splitting. Enable `BUILDKITE_TEST_ENGINE_DEBUG_ENABLED` to verify the splitting strategy.

## bktec Environment Variables

### Required variables

| Variable | Description |
|----------|-------------|
| `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN` | API access token for authenticating with Test Engine (requires `read_suites` scope) |
| `BUILDKITE_TEST_ENGINE_SUITE_SLUG` | Slug of the test suite to fetch timing data from |
| `BUILDKITE_TEST_ENGINE_TEST_RUNNER` | Test runner to use: `rspec`, `jest`, `playwright`, `cypress`, `pytest`, `pytest-pants`, `go`, `cucumber` |
| `BUILDKITE_TEST_ENGINE_RESULT_PATH` | Path where bktec writes test results (e.g., `tmp/rspec-result.json`) |

### Optional variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BUILDKITE_TEST_ENGINE_RETRY_COUNT` | `0` | Number of times to retry failed tests. Set to `2` for flaky detection |
| `BUILDKITE_TEST_ENGINE_SPLIT_BY_EXAMPLE` | `false` | Split by individual test example instead of by file (RSpec only) |
| `BUILDKITE_TEST_ENGINE_TEST_FILE_PATTERN` | Runner default | Glob pattern to select test files (e.g., `spec/**/*_spec.rb`) |
| `BUILDKITE_TEST_ENGINE_DEBUG_ENABLED` | `false` | Enable debug logging to see splitting strategy and file assignments |

Standard Buildkite environment variables (`BUILDKITE_BUILD_ID`, `BUILDKITE_PARALLEL_JOB`, `BUILDKITE_PARALLEL_JOB_COUNT`, etc.) are used automatically by bktec. When running in Docker, expose them explicitly via the plugin `environment` list.

## Test Splitting

### Timing-based splitting

With historical timing data, bktec assigns files to agents based on cumulative runtime so each agent finishes in approximately the same time. The test plan updates every build, so splitting improves continuously as more data accumulates.

Pipeline configuration is shown in Quick Start step 3. Use `%n` in the label to show the parallel job index.

> For complete per-framework pipeline examples (RSpec, Jest, pytest, Go), split-by-example vs split-by-file guidance, parallelism tuning table, and custom test command configuration, see **`references/splitting-examples.md`**.

## Flaky Test Detection

Test Engine flags a test as flaky when the same test on the same commit produces both pass and fail results.

### Automatic retry for flaky detection

Set `BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"` to retry failed tests. If a test fails then passes on retry, it is flagged as flaky. The build passes if all tests eventually pass.

> For listing flaky tests via the REST API, see the **buildkite-api** skill.

### MCP tools for flaky test investigation

When the Buildkite MCP server is available: `list_test_runs` (pass/fail trends), `get_test_run` (run details), `get_failed_executions` (error messages and stack traces), `get_build_test_engine_runs` (runs for a build).

Triage: identify flaky tests via MCP tools or the dashboard, quarantine confirmed flakes, fix root causes, then remove from quarantine. Target < 3% flaky rate.

## Test States and Quarantine

### Test states

| State | Meaning | bktec behavior |
|-------|---------|----------------|
| **Active** | Test runs normally | Included in test runs |
| **Muted** | Test runs but failures are suppressed | Included in test runs; failures do not fail the build |
| **Quarantined** | Test is excluded from runs | Excluded from test runs entirely |

### How quarantine works

- bktec automatically excludes quarantined tests from runs, so they cannot fail the build
- Supported for RSpec, Jest, and Playwright runners

No special pipeline configuration is needed — bktec reads test states automatically. Change states through the dashboard. Fix root causes, then move tests back to Active.

## Docker and Containerized Environments

When running tests inside Docker, expose both `BUILDKITE_TEST_ENGINE_*` and standard Buildkite variables via the Docker plugin `environment` list:

```yaml
steps:
  - label: ":docker: Tests %n"
    command: bktec
    parallelism: 10
    plugins:
      - docker#v5.12.0:
          image: "myapp:test"
          environment:
            - BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN
            - BUILDKITE_TEST_ENGINE_SUITE_SLUG
            - BUILDKITE_TEST_ENGINE_TEST_RUNNER
            - BUILDKITE_TEST_ENGINE_RESULT_PATH
            - BUILDKITE_BUILD_ID
            - BUILDKITE_PARALLEL_JOB
            - BUILDKITE_PARALLEL_JOB_COUNT
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "my-suite"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "rspec"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/rspec-result.json"
```

## End-to-End Setup Walkthrough

- **Week 1:** Run the collector pipeline (Quick Start step 2) for ~1-2 weeks to accumulate timing data.
- **Week 2+:** Switch to bktec (Quick Start step 3). Add `BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"`.
- **Week 3+:** Review the dashboard for flaky tests. Quarantine confirmed flakes. Target < 3% flaky rate.
- **Ongoing:** Verify parallel agents finish within ~10% of each other. Review quarantined tests weekly. Monitor suite trends for regressions.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Confusing the two tokens | `BUILDKITE_ANALYTICS_TOKEN` is for collectors (suite-scoped). `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN` is for bktec (user-scoped, `read_suites`). |
| Running bktec before enough data | Run collectors for 1-2 weeks first. Enable `DEBUG_ENABLED` to verify timing-based splitting. |
| Missing env vars in Docker | Pass `BUILDKITE_PARALLEL_JOB`, `BUILDKITE_PARALLEL_JOB_COUNT`, and other vars via Docker plugin `environment` list. |
| `parallelism` > test file count | Agents receive zero tests and waste compute. Set at most the number of test files. |
| Omitting `RESULT_PATH` | bktec cannot write results back. Always set it. |
| Wrong `TEST_RUNNER` value | Use exact values: `rspec`, `jest`, `playwright`, `cypress`, `pytest`, `pytest-pants`, `go`, `cucumber`. |
| Not pinning `test-collector` version | Always pin: `test-collector#v2.0.0`, not `test-collector#v2`. |
| `RETRY_COUNT` above 3 | Use `2`. Higher values waste compute and mask genuine failures. |

## Additional Resources

- **`references/collectors.md`** — Per-framework collector setup (Ruby, JavaScript, Python, Go, JUnit XML, test-collector plugin)
- **`references/splitting-examples.md`** — Per-framework bktec examples, split-by-example, parallelism tuning
- **`examples/collector-pipeline.yml`** — Minimal collector pipeline
- **`examples/bktec-splitting.yml`** — bktec with parallelism, retry, and result path

## Further Reading

- [Test Engine overview](https://buildkite.com/docs/test-engine.md)
- [Configuring bktec](https://buildkite.com/docs/test-engine/bktec/configuring.md)
- [Test collection](https://buildkite.com/docs/test-engine/test-collection.md)
- [Test states and quarantine](https://buildkite.com/docs/test-engine/test-suites/test-state-and-quarantine.md)
- [bktec source (GitHub)](https://github.com/buildkite/test-engine-client)
