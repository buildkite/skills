# Test Splitting Examples and Configuration

Detailed per-framework splitting examples, split-by-example vs split-by-file guidance, parallelism tuning, and custom test command configuration for bktec.

## Complete examples by framework

### RSpec with retry and split-by-example

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

### Jest

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

### pytest

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

### Go

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

## Split by example vs split by file

By default, bktec splits by **file** — each parallel agent gets a set of test files. Set `BUILDKITE_TEST_ENGINE_SPLIT_BY_EXAMPLE` to `true` to split by **individual test example** instead.

Split-by-example produces more even partitions when test files have widely varying numbers of tests (e.g., one file with 200 tests and another with 5). Currently only supported for RSpec.

## Choosing parallelism level

| Suite size | Suggested `parallelism` | Reasoning |
|------------|------------------------|-----------|
| < 100 tests | 2-4 | Overhead of splitting outweighs benefit at small scale |
| 100-500 tests | 4-8 | Good balance of speed improvement vs agent cost |
| 500-2000 tests | 8-16 | Significant time reduction |
| 2000+ tests | 16-32 | Large suites benefit most; diminishing returns above 32 |

The optimal value depends on test runtime distribution. Check Test Engine analytics to see if agents finish at roughly the same time — if one agent consistently takes much longer, increase parallelism or enable split-by-example.

## Custom test commands

Override the default test command when the test runner needs additional flags or setup:

```yaml
env:
  BUILDKITE_TEST_ENGINE_TEST_CMD: "bundle exec rspec --format documentation"
  BUILDKITE_TEST_ENGINE_RETRY_CMD: "bundle exec rspec --format documentation --only-failures"
```

bktec appends the assigned test files to the command automatically.
