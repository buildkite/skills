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

Test Engine is Buildkite's testing product for splitting test suites across parallel machines and identifying flaky tests. It operates through two components: **test collectors** that gather timing and reliability data from test runs, and **bktec** (the Test Engine Client CLI) that uses that data for intelligent test splitting and automatic flaky test management.

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

This splits the test suite across 10 parallel agents, balanced by historical runtime, and automatically excludes quarantined flaky tests.

> For `parallelism:` YAML syntax and pipeline structure, see the **buildkite-pipelines** skill.

## How Test Engine Works

Test Engine is a two-phase system:

**Phase 1 — Data collection:** Test collectors (language-specific gems, npm packages, or JUnit XML uploads) send execution timing, pass/fail results, and error details to the Test Engine API after every test run. This builds a historical profile for each test in the suite.

**Phase 2 — Smart splitting + flaky management:** bktec reads the historical data to (a) partition tests across parallel agents so each agent finishes in roughly the same time, and (b) identify and quarantine flaky tests so they stop failing builds.

The data dependency is critical: bktec needs ~1-2 weeks of collector data before timing-based splitting is effective. Without data, bktec falls back to splitting by file count, which produces uneven partitions when test files vary in runtime.

### The Two Token Types

This is the most common source of confusion. Test Engine uses two different tokens for different purposes:

| Token | Environment Variable | Purpose | Where to get it |
|-------|---------------------|---------|-----------------|
| **Suite API token** | `BUILDKITE_ANALYTICS_TOKEN` | Collectors use this to send test data to a specific suite | Test suite settings page |
| **API access token** | `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN` | bktec uses this to fetch timing data and test plans | Personal Settings > API Access Tokens (requires `read_suites` scope) |

These are not interchangeable. The suite API token routes data to a suite. The API access token authenticates bktec to read from the Test Engine API.

## Creating Test Suites

### Via the Buildkite dashboard

1. Select **Test Suites** in the global navigation
2. Select **New test suite**
3. Select **Set up suite**
4. If the teams feature is enabled, select relevant teams and continue

The suite settings page shows the **suite API token** (for collectors) and the **suite slug** (for bktec).

### Via the REST API

```bash
curl -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -X POST "https://api.buildkite.com/v2/analytics/organizations/{org.slug}/suites" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backend RSpec",
    "default_branch": "main",
    "show_api_token": true
  }'
```

Set `show_api_token: true` to include the suite API token in the response. The response also contains the `slug` field needed for `BUILDKITE_TEST_ENGINE_SUITE_SLUG`.

> For full REST API details, see the **buildkite-api** skill.

### Suites and pipelines

Pipelines and test suites do not need a one-to-one relationship. Multiple pipelines can report to the same suite (useful for monorepos with a shared test suite), and one pipeline can report to multiple suites (useful for separate unit and integration suites).

## Test Collectors

Collectors send test execution data to Test Engine. Install the collector for the test framework, set `BUILDKITE_ANALYTICS_TOKEN`, and run tests normally. Every framework needs a collector configured before bktec splitting works.

### Ruby — RSpec

Add the gem to the Gemfile:

```ruby
group :test do
  gem "buildkite-test_collector"
end
```

Configure in `spec_helper.rb` (require gems that patch `Net::HTTP` before this):

```ruby
require "buildkite/test_collector"

Buildkite::TestCollector.configure(hook: :rspec)
```

Pipeline step:

```yaml
steps:
  - label: ":rspec: Tests"
    command: "bundle exec rspec"
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

### Ruby — Minitest

Same gem, different hook. Configure in `test_helper.rb`:

```ruby
require "buildkite/test_collector"

Buildkite::TestCollector.configure(hook: :minitest)
```

### JavaScript — Jest

Install the npm package:

```bash
npm install --save-dev buildkite-test-collector
```

Add the reporter to `jest.config.js`:

```javascript
module.exports = {
  reporters: [
    "default",
    "buildkite-test-collector/jest/reporter"
  ],
  testLocationInResults: true
};
```

Pipeline step:

```yaml
steps:
  - label: ":jest: Tests"
    command: "npm test"
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

### JavaScript — Playwright

Add the reporter to `playwright.config.js`:

```javascript
module.exports = {
  reporter: [
    ["list"],
    ["buildkite-test-collector/playwright/reporter"]
  ]
};
```

### JavaScript — Cypress

Configure in `cypress.config.js`:

```javascript
module.exports = {
  reporter: "buildkite-test-collector/cypress/reporter",
  reporterOptions: {}
};
```

### Python — pytest

bktec supports pytest directly as a test runner. No separate collector package is needed — bktec handles both splitting and result collection when `BUILDKITE_TEST_ENGINE_TEST_RUNNER` is set to `pytest`.

For collecting analytics data without bktec, use the JUnit XML upload method described below.

### Go

Generate JUnit XML with `gotestsum`, then upload to the analytics API:

```yaml
steps:
  - label: ":golang: Tests"
    command: |
      gotestsum --junitfile junit.xml -- ./...
      curl \
        -X POST \
        --fail-with-body \
        -H "Authorization: Token token=\"$$BUILDKITE_ANALYTICS_TOKEN\"" \
        -F "data=@junit.xml" \
        -F "format=junit" \
        -F "run_env[CI]=buildkite" \
        -F "run_env[key]=$BUILDKITE_BUILD_ID" \
        -F "run_env[number]=$BUILDKITE_BUILD_NUMBER" \
        -F "run_env[job_id]=$BUILDKITE_JOB_ID" \
        -F "run_env[branch]=$BUILDKITE_BRANCH" \
        -F "run_env[commit_sha]=$BUILDKITE_COMMIT" \
        -F "run_env[message]=$BUILDKITE_MESSAGE" \
        -F "run_env[url]=$BUILDKITE_BUILD_URL" \
        https://analytics-api.buildkite.com/v1/uploads
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

### JUnit XML Upload — Universal Fallback

Any language that produces JUnit XML can upload results to Test Engine via the analytics API. This is the fallback for languages without a dedicated collector.

```bash
curl \
  -X POST \
  --fail-with-body \
  -H "Authorization: Token token=\"$BUILDKITE_ANALYTICS_TOKEN\"" \
  -F "data=@test-results.xml" \
  -F "format=junit" \
  -F "run_env[CI]=buildkite" \
  -F "run_env[key]=$BUILDKITE_BUILD_ID" \
  -F "run_env[number]=$BUILDKITE_BUILD_NUMBER" \
  -F "run_env[branch]=$BUILDKITE_BRANCH" \
  -F "run_env[commit_sha]=$BUILDKITE_COMMIT" \
  https://analytics-api.buildkite.com/v1/uploads
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `data` | Yes | The JUnit XML file (`@path/to/file.xml`) |
| `format` | Yes | Always `junit` for XML uploads |
| `run_env[CI]` | No | CI platform identifier (e.g., `buildkite`, `github_actions`) |
| `run_env[key]` | Yes | Unique identifier for this build run |
| `run_env[number]` | No | Build number |
| `run_env[branch]` | No | Git branch |
| `run_env[commit_sha]` | No | Git commit SHA |
| `run_env[job_id]` | No | Job ID (for parallel builds) |
| `run_env[message]` | No | Commit message |
| `run_env[url]` | No | URL to the build |

Maximum 5000 test results per upload. For larger suites, split into multiple uploads using the same `run_env[key]` value.

### test-collector Plugin

As an alternative to framework-specific collectors, the `test-collector` plugin uploads test result files directly:

```yaml
steps:
  - label: ":test_tube: Tests"
    command: "make test"
    plugins:
      - test-collector#v2.0.0:
          files: "tmp/junit-*.xml"
          format: "junit"
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `files` | Yes | Glob pattern for test result files |
| `format` | Yes | Result format: `junit`, `json` |

The plugin runs after the test command, collects matching files, and uploads them to Test Engine. Pin the plugin version (`test-collector#v2.0.0`, not `test-collector#v2`).

### Running collectors locally

Test locally to verify collector configuration before committing:

```bash
BUILDKITE_ANALYTICS_TOKEN=your-suite-api-token \
BUILDKITE_ANALYTICS_MESSAGE="Local test run" \
bundle exec rspec
```

Results appear in the Test Engine dashboard within seconds.

## bktec CLI

bktec (Buildkite Test Engine Client) is the CLI tool that fetches test plans from Test Engine and runs tests with intelligent splitting. It replaces the test runner command in pipeline steps.

### How bktec works

1. bktec reads `BUILDKITE_PARALLEL_JOB` and `BUILDKITE_PARALLEL_JOB_COUNT` to determine which partition this agent handles
2. It fetches the test plan from the Test Engine API using timing data from previous runs
3. It assigns a subset of test files (or examples) to this agent, balanced by historical runtime
4. It runs the test subset using the configured test runner
5. It uploads results back to Test Engine
6. If `BUILDKITE_TEST_ENGINE_RETRY_COUNT` is set, it automatically retries failed tests

### Installation

**Hosted agents (Debian/Ubuntu):**

bktec is pre-installed on Buildkite hosted agents. If not available, install via:

```bash
curl -sL https://github.com/buildkite/test-engine-client/releases/latest/download/bktec-linux-amd64 -o /usr/local/bin/bktec
chmod +x /usr/local/bin/bktec
```

**macOS:**

```bash
curl -sL https://github.com/buildkite/test-engine-client/releases/latest/download/bktec-darwin-amd64 -o /usr/local/bin/bktec
chmod +x /usr/local/bin/bktec
```

### Supported test runners

| Runner | `BUILDKITE_TEST_ENGINE_TEST_RUNNER` value | Notes |
|--------|------------------------------------------|-------|
| RSpec | `rspec` | Full support including split-by-example |
| Jest | `jest` | Splits by test file |
| Playwright | `playwright` | Splits by test file |
| Cypress | `cypress` | Splits by spec file |
| pytest | `pytest` | Splits by test file |
| pytest-pants | `pytest-pants` | For Pants build system |
| Go | `go` | Splits by test package |
| Cucumber | `cucumber` | Splits by feature file |

### Fallback behavior

If bktec cannot reach the Test Engine API or no timing data exists, it falls back to splitting by file count. This produces less even partitions but ensures tests still run. Enable `BUILDKITE_TEST_ENGINE_DEBUG_ENABLED` to see which splitting strategy bktec used.

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
| `BUILDKITE_TEST_ENGINE_TEST_CMD` | Runner default | Override the test command bktec executes |
| `BUILDKITE_TEST_ENGINE_RETRY_CMD` | Runner default | Override the retry command for failed tests |
| `BUILDKITE_TEST_ENGINE_SPLIT_BY_EXAMPLE` | `false` | Split by individual test example instead of by file (RSpec only) |
| `BUILDKITE_TEST_ENGINE_TEST_FILE_PATTERN` | Runner default | Glob pattern to select test files (e.g., `spec/**/*_spec.rb`) |
| `BUILDKITE_TEST_ENGINE_TEST_FILE_EXCLUDE_PATTERN` | — | Glob pattern to exclude test files from splitting |
| `BUILDKITE_TEST_ENGINE_DEBUG_ENABLED` | `false` | Enable debug logging to see splitting strategy and file assignments |

### Predefined variables (automatic in Buildkite)

These standard Buildkite variables are available automatically and used by bktec internally. When running tests in Docker or other containers, expose these variables explicitly:

| Variable | Description |
|----------|-------------|
| `BUILDKITE_BUILD_ID` | Unique build identifier |
| `BUILDKITE_JOB_ID` | Unique job identifier |
| `BUILDKITE_PARALLEL_JOB` | Index of this parallel job (0-based) |
| `BUILDKITE_PARALLEL_JOB_COUNT` | Total number of parallel jobs |
| `BUILDKITE_BRANCH` | Git branch |
| `BUILDKITE_COMMIT` | Git commit SHA |
| `BUILDKITE_MESSAGE` | Commit message |
| `BUILDKITE_BUILD_URL` | URL to the build page |

## Test Splitting

### Timing-based splitting

When Test Engine has historical timing data, bktec partitions tests so each parallel agent finishes in approximately the same time. Without timing data, a naive file-count split assigns equal numbers of files to each agent — but if one file takes 60 seconds and another takes 1 second, agents finish at wildly different times.

Timing-based splitting solves this by assigning files to agents based on cumulative runtime. The test plan updates with every build, so splitting improves continuously as more data accumulates.

### Pipeline configuration

Set `parallelism: N` on the step and use `bktec` as the command:

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

The `%n` in the label expands to the parallel job index (e.g., "Tests 0", "Tests 1", ..., "Tests 9").

### Complete examples by framework

**RSpec with retry and split-by-example:**

```yaml
steps:
  - label: ":rspec: Tests %n"
    command: bktec
    parallelism: 10
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "backend-rspec"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "rspec"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/rspec-result.json"
      BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"
      BUILDKITE_TEST_ENGINE_SPLIT_BY_EXAMPLE: "true"
```

**Jest:**

```yaml
steps:
  - label: ":jest: Tests %n"
    command: bktec
    parallelism: 8
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "frontend-jest"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "jest"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/jest-result.json"
```

**pytest:**

```yaml
steps:
  - label: ":python: Tests %n"
    command: bktec
    parallelism: 6
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "backend-pytest"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "pytest"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/pytest-result.json"
      BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"
```

**Go:**

```yaml
steps:
  - label: ":golang: Tests %n"
    command: bktec
    parallelism: 4
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "backend-go"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "go"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/go-result.json"
```

### Split by example vs split by file

By default, bktec splits by **file** — each parallel agent gets a set of test files. Set `BUILDKITE_TEST_ENGINE_SPLIT_BY_EXAMPLE` to `true` to split by **individual test example** instead.

Split-by-example produces more even partitions when test files have widely varying numbers of tests (e.g., one file with 200 tests and another with 5). Currently only supported for RSpec.

### Choosing parallelism level

| Suite size | Suggested `parallelism` | Reasoning |
|------------|------------------------|-----------|
| < 100 tests | 2-4 | Overhead of splitting outweighs benefit at small scale |
| 100-500 tests | 4-8 | Good balance of speed improvement vs agent cost |
| 500-2000 tests | 8-16 | Significant time reduction |
| 2000+ tests | 16-32 | Large suites benefit most; diminishing returns above 32 |

The optimal value depends on test runtime distribution. Check Test Engine analytics to see if agents finish at roughly the same time — if one agent consistently takes much longer, increase parallelism or enable split-by-example.

### Custom test commands

Override the default test command when the test runner needs additional flags or setup:

```yaml
env:
  BUILDKITE_TEST_ENGINE_TEST_CMD: "bundle exec rspec --format documentation"
  BUILDKITE_TEST_ENGINE_RETRY_CMD: "bundle exec rspec --format documentation --only-failures"
```

bktec appends the assigned test files to the command automatically.

## Flaky Test Detection

A flaky test produces different results (pass/fail) on the same commit. Flaky tests erode trust in CI — developers stop investigating failures because "it's probably just a flake."

### How Test Engine detects flakes

Test Engine tracks every execution of every test. When the same test on the same commit produces both pass and fail results (across different builds or retries), Test Engine flags it as flaky.

### Automatic retry for flaky detection

Set `BUILDKITE_TEST_ENGINE_RETRY_COUNT` to automatically retry failed tests within the same job. If a test fails on first run but passes on retry, Test Engine records it as flaky:

```yaml
env:
  BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"
```

This retries each failed test up to 2 times. The build passes if all tests eventually pass (including on retry). Recommended value is `2` — higher values waste compute without meaningfully improving detection.

### Listing flaky tests via the REST API

```bash
curl -H "Authorization: Bearer $BUILDKITE_API_TOKEN" \
  -X GET "https://api.buildkite.com/v2/analytics/organizations/{org.slug}/suites/{suite.slug}/flaky-tests"
```

The response is a paginated list of tests flagged as flaky, with metadata including failure rate, last seen date, and affected branches.

> For full API pagination and authentication details, see the **buildkite-api** skill.

### Investigating flaky tests with MCP tools

When the Buildkite MCP server is available, use these tools to investigate test failures:

| MCP Tool | Use for |
|----------|---------|
| `list_test_runs` | List all runs for a test suite to see recent pass/fail trends |
| `get_test_run` | Get details of a specific test run including pass/fail/skip counts |
| `get_test` | Retrieve metadata for a specific test (name, suite, location) |
| `get_failed_executions` | Get failed executions with error messages and stack traces |
| `get_build_test_engine_runs` | Get Test Engine runs associated with a specific Pipelines build |

### Flaky test triage workflow

1. Use `list_test_runs` or the Test Engine dashboard to identify suites with high failure rates
2. Use `get_failed_executions` with expanded failure details to see error messages and stack traces
3. Determine if failures are environmental (timeouts, network), test-order-dependent, or timing-related
4. Quarantine confirmed flakes (see Test States and Quarantine below)
5. Fix the root cause, then remove from quarantine

Target: < 3% flaky test rate. Above this threshold, developers stop trusting CI results.

## Test States and Quarantine

Test Engine assigns a **state** to each test based on its execution history. bktec uses test states to automatically manage flaky tests during test runs.

### Test states

| State | Meaning | bktec behavior |
|-------|---------|----------------|
| **Active** | Test runs normally | Included in test runs |
| **Muted** | Test runs but failures are suppressed | Included in test runs; failures do not fail the build |
| **Quarantined** | Test is excluded from runs | Excluded from test runs entirely |

### How quarantine works

When a test is quarantined:
- bktec automatically excludes it from test runs
- The build is not affected by the quarantined test's pass/fail status
- Test Engine continues tracking the test's execution in other contexts
- Quarantine is supported for RSpec, Jest, and Playwright runners

Quarantining prevents flaky tests from causing build failures while the root cause is investigated. This is more targeted than retrying — a quarantined test is skipped entirely, saving both compute time and developer attention.

### Managing test states

Change test states through the Test Engine dashboard:
1. Navigate to the test suite
2. Find the test (use search or filter by state)
3. Select the test and change its state to Active, Muted, or Quarantined

### Pipeline example with quarantine

No special pipeline configuration is needed. bktec reads test states from the Test Engine API automatically:

```yaml
steps:
  - label: ":rspec: Tests %n (quarantined tests excluded)"
    command: bktec
    parallelism: 10
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "my-suite"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "rspec"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/rspec-result.json"
```

### Quarantine workflow

1. Identify flaky tests via Test Engine dashboard or `get_failed_executions` MCP tool
2. Quarantine confirmed flakes through the dashboard
3. Create tickets to fix the underlying issue
4. After fixing, change the test state back to Active
5. Monitor for regressions over the next few builds

## Docker and Containerized Environments

When running tests inside Docker or other containers, expose the Buildkite environment variables that bktec needs. These are available automatically on the host but not inside containers:

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
            - BUILDKITE_JOB_ID
            - BUILDKITE_PARALLEL_JOB
            - BUILDKITE_PARALLEL_JOB_COUNT
            - BUILDKITE_BRANCH
            - BUILDKITE_COMMIT
    env:
      BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN: "your-api-access-token"
      BUILDKITE_TEST_ENGINE_SUITE_SLUG: "my-suite"
      BUILDKITE_TEST_ENGINE_TEST_RUNNER: "rspec"
      BUILDKITE_TEST_ENGINE_RESULT_PATH: "tmp/rspec-result.json"
```

The `environment` list in the Docker plugin passes these variables from the host into the container. Without this, bktec cannot determine the parallel job index or authenticate with Test Engine.

## End-to-End Setup Walkthrough

Complete setup from zero to intelligent test splitting:

### Week 1: Collect data

```yaml
steps:
  - label: ":rspec: Tests"
    command: "bundle exec rspec --format progress --format RspecJunitFormatter --out tmp/rspec.xml"
    plugins:
      - test-collector#v2.0.0:
          files: "tmp/rspec.xml"
          format: "junit"
    env:
      BUILDKITE_ANALYTICS_TOKEN: "your-suite-api-token"
```

Run this for ~1-2 weeks across normal development. Test Engine accumulates timing data for every test in the suite.

### Week 2+: Enable splitting

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
      BUILDKITE_TEST_ENGINE_RETRY_COUNT: "2"
```

### Week 3+: Quarantine flakes

Review the Test Engine dashboard for tests flagged as flaky. Quarantine confirmed flakes. Target < 3% flaky rate.

### Ongoing: Monitor and tune

- Check that parallel agents finish within ~10% of each other. If not, adjust `parallelism` or enable split-by-example.
- Review quarantined tests weekly. Fix root causes and move tests back to Active.
- Monitor suite trends in the Test Engine dashboard for regressions in test count, runtime, or flaky rate.

## Common Mistakes

| Mistake | What happens | Fix |
|---------|-------------|-----|
| Using `BUILDKITE_ANALYTICS_TOKEN` where `BUILDKITE_TEST_ENGINE_API_ACCESS_TOKEN` is needed (or vice versa) | Collector uploads fail, or bktec cannot fetch test plans | Analytics token is for collectors (suite-scoped). API access token is for bktec (user-scoped with `read_suites`). |
| Running bktec before collectors have gathered enough data | bktec falls back to file-count splitting, producing uneven partitions | Run collectors for 1-2 weeks before switching to bktec. Enable `BUILDKITE_TEST_ENGINE_DEBUG_ENABLED` to verify timing-based splitting is active. |
| Not exposing Buildkite env vars in Docker containers | bktec cannot determine parallel job index, defaults to running all tests on every agent | Pass `BUILDKITE_PARALLEL_JOB`, `BUILDKITE_PARALLEL_JOB_COUNT`, and other required vars via the Docker plugin `environment` list. |
| Setting `parallelism` higher than the number of test files | Some agents receive zero tests and exit immediately, wasting compute | Set `parallelism` to at most the number of test files. Check Test Engine analytics for optimal value. |
| Omitting `BUILDKITE_TEST_ENGINE_RESULT_PATH` | bktec cannot write test results, preventing data from feeding back into Test Engine | Always set the result path (e.g., `tmp/rspec-result.json`). |
| Using an incorrect `BUILDKITE_TEST_ENGINE_TEST_RUNNER` value | bktec fails to start or uses wrong test execution strategy | Use exact values: `rspec`, `jest`, `playwright`, `cypress`, `pytest`, `pytest-pants`, `go`, `cucumber`. |
| Not pinning `test-collector` plugin version | Plugin updates may change behavior or introduce breaking changes | Always pin: `test-collector#v2.0.0`, not `test-collector#v2`. |
| Setting `BUILDKITE_TEST_ENGINE_RETRY_COUNT` above 3 | Excessive retries waste compute and mask genuine failures | Use `2` for flaky detection. Higher values rarely help and significantly increase build time for truly broken tests. |

## Further Reading

- [Buildkite Docs for LLMs](https://buildkite.com/docs/llms.txt)
- [Test Engine overview](https://buildkite.com/docs/test-engine)
- [Speed up builds with bktec](https://buildkite.com/docs/test-engine/speed-up-builds-with-bktec)
- [Configuring bktec](https://buildkite.com/docs/test-engine/bktec/configuring)
- [Test collection](https://buildkite.com/docs/test-engine/test-collection)
- [Test states and quarantine](https://buildkite.com/docs/test-engine/test-suites/test-state-and-quarantine)
- [Flaky tests REST API](https://buildkite.com/docs/apis/rest-api/test-engine/flaky-tests)
- [bktec source (GitHub)](https://github.com/buildkite/test-engine-client)
