# Test Collectors Reference

This file covers all framework-specific collector configurations for sending test execution data to Buildkite Test Engine. Install the collector for the test framework, set `BUILDKITE_ANALYTICS_TOKEN`, and run tests normally.

## Ruby — RSpec

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

## Ruby — Minitest

Same gem, different hook. Configure in `test_helper.rb`:

```ruby
require "buildkite/test_collector"

Buildkite::TestCollector.configure(hook: :minitest)
```

## JavaScript — Jest

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

## JavaScript — Playwright

Add the reporter to `playwright.config.js`:

```javascript
module.exports = {
  reporter: [
    ["list"],
    ["buildkite-test-collector/playwright/reporter"]
  ]
};
```

## JavaScript — Cypress

Configure in `cypress.config.js`:

```javascript
module.exports = {
  reporter: "buildkite-test-collector/cypress/reporter",
  reporterOptions: {}
};
```

## Python — pytest

bktec supports pytest directly as a test runner. No separate collector package is needed — bktec handles both splitting and result collection when `BUILDKITE_TEST_ENGINE_TEST_RUNNER` is set to `pytest`.

For collecting analytics data without bktec, use the JUnit XML upload method described below.

## Go (using the universal JUnit method)

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

## JUnit XML Upload — Universal Fallback

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

## test-collector Plugin

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

## Running collectors locally

Test locally to verify collector configuration before committing:

```bash
BUILDKITE_ANALYTICS_TOKEN=your-suite-api-token \
BUILDKITE_ANALYTICS_MESSAGE="Local test run" \
bundle exec rspec
```

Results appear in the Test Engine dashboard within seconds.
