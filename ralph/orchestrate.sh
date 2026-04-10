#!/usr/bin/env bash
# Ralph Wiggum Loop: Iterative skill improvement via Express.js migration
#
# Each iteration:
#   Phase 1: Fresh conversion agent (Docker) converts GHA -> Buildkite
#   Phase 2: Evaluator scores the conversion
#   Phase 3: Improvement agent (worktree) patches skills to address gaps
#
# Usage:
#   ./ralph/orchestrate.sh              # Run the full loop
#   ./ralph/orchestrate.sh --dry-run    # Skip Docker/Claude, just test evaluator
#   ./ralph/orchestrate.sh --skip-infra # Skip cluster creation (offline mode)

set -euo pipefail

# --- Load .env if present ---
if [[ -f "$(cd "$(dirname "$0")/.." && pwd)/.env" ]]; then
  set -a
  source "$(cd "$(dirname "$0")/.." && pwd)/.env"
  set +a
fi

# --- Configuration ---
SKILLS_REPO="$(cd "$(dirname "$0")/.." && pwd)"
RALPH_DIR="$SKILLS_REPO/ralph"
EXPRESS_DIR="$RALPH_DIR/express-checkout"
STATE_BASE="$RALPH_DIR/state"
STATE_DIR=""  # Set in init_state based on run ID
RUN_ID=""     # Short unique ID for this run, used in cluster names

MAX_ITERATIONS=20
PASS_THRESHOLD=90
PLATEAU_LIMIT=3  # stop after N iterations with no improvement
PLATEAU_MIN_DELTA=1  # minimum score improvement to reset plateau counter

CONVERSION_BUDGET=5   # max USD per conversion agent run
IMPROVEMENT_BUDGET=3  # max USD per improvement agent run
MODEL="sonnet"

DOCKER_IMAGE="ralph-agent"
# --- Parse flags ---
DRY_RUN=false
SKIP_INFRA=false
START_VERSION=""
RESUME=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --skip-infra) SKIP_INFRA=true; shift ;;
    --start-from) START_VERSION="$2"; shift 2 ;;
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --resume) RESUME=true; shift ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[ralph]${NC} $*" >&2; }
log_ok() { echo -e "${GREEN}[ralph]${NC} $*" >&2; }
log_warn() { echo -e "${YELLOW}[ralph]${NC} $*" >&2; }
log_err() { echo -e "${RED}[ralph]${NC} $*" >&2; }
log_section() { echo -e "\n${BOLD}=== $* ===${NC}\n" >&2; }

# --- Prerequisites ---
check_prerequisites() {
  log "Checking prerequisites..."

  if [[ "$DRY_RUN" == "false" ]]; then
    if ! command -v docker &>/dev/null; then
      log_err "Docker not found. Install Docker first."
      exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
      log_err "Docker daemon not running. Start Docker first."
      exit 1
    fi

    if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null 2>&1; then
      log_warn "Docker image '$DOCKER_IMAGE' not found. Building..."
      docker build -t "$DOCKER_IMAGE" "$RALPH_DIR"
    fi

    if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
      log_err "ANTHROPIC_API_KEY not set."
      exit 1
    fi

    if [[ -z "${BUILDKITE_API_TOKEN:-}" ]]; then
      log_warn "BUILDKITE_API_TOKEN not set. Infrastructure creation will fail."
    fi

    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
      log_warn "GITHUB_TOKEN not set. Agent won't be able to push to fork."
    fi
  fi

  if ! command -v bc &>/dev/null; then
    log_err "bc not found. Install bc (used for score comparison)."
    exit 1
  fi

  if ! command -v python3 &>/dev/null; then
    log_err "python3 not found."
    exit 1
  fi

  if ! python3 -c "import yaml" &>/dev/null 2>&1; then
    log_err "PyYAML not installed. Run: pip3 install pyyaml"
    exit 1
  fi
}

# --- Clone Express.js if needed ---
setup_express() {
  if [[ ! -d "$EXPRESS_DIR" ]]; then
    log "Cloning Express.js..."
    git clone https://github.com/expressjs/express.git "$EXPRESS_DIR"
  fi
}

# --- Initialize state ---
init_state() {
  mkdir -p "$STATE_BASE"

  if [[ "$RESUME" == "true" ]]; then
    # Find the latest run directory
    local latest
    latest=$(ls -1d "$STATE_BASE"/run-* 2>/dev/null | sort | tail -1)
    if [[ -z "$latest" ]]; then
      log_err "No previous run found to resume."
      exit 1
    fi
    STATE_DIR="$latest"
    # Recover the run ID from the saved file
    if [[ -f "$STATE_DIR/run_id.txt" ]]; then
      RUN_ID=$(cat "$STATE_DIR/run_id.txt")
    else
      # Legacy run without a saved ID — generate one from the directory name
      RUN_ID=$(echo "$(basename "$STATE_DIR")" | md5sum | head -c 5)
      echo "$RUN_ID" > "$STATE_DIR/run_id.txt"
    fi
    log "Resuming run: $(basename "$STATE_DIR") (id: $RUN_ID)"
  else
    # Create a new run directory
    local run_ts
    run_ts="run-$(date +%Y%m%d-%H%M%S)"
    STATE_DIR="$STATE_BASE/$run_ts"
    mkdir -p "$STATE_DIR"

    # Generate a short unique ID for cluster naming
    RUN_ID=$(echo "${run_ts}-$$-${RANDOM}" | md5sum | head -c 5)
    echo "$RUN_ID" > "$STATE_DIR/run_id.txt"
    log "New run: $run_ts (id: $RUN_ID)"

    echo "[]" > "$STATE_DIR/iterations.json"
    echo "0" > "$STATE_DIR/current_version.txt"
  fi

  # Update latest symlink
  ln -sfn "$STATE_DIR" "$STATE_BASE/latest"

  if [[ -n "$START_VERSION" ]]; then
    echo "$((START_VERSION - 1))" > "$STATE_DIR/current_version.txt"
  fi
}

# --- Get next version ---
next_version() {
  local current
  current=$(cat "$STATE_DIR/current_version.txt")
  echo $((current + 1))
}

# --- Reset Express.js to clean state ---
reset_express() {
  local version=$1
  local branch="ralph/iter-${version}"

  log "Resetting Express.js to clean state..."
  (
    cd "$EXPRESS_DIR"
    git fetch origin 2>/dev/null || true
    # Clean any dirty state from the previous conversion before switching branches
    git checkout -- . 2>/dev/null || true
    git clean -fd 2>/dev/null || true
    git checkout main 2>/dev/null || git checkout master 2>/dev/null
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null

    # Delete old branch if it exists, then create fresh
    git branch -D "$branch" 2>/dev/null || true
    git checkout -b "$branch"

    # Configure fork remote for pushing .buildkite/ files
    git remote add fork https://github.com/clbarrell/express.git 2>/dev/null || true
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
      git remote set-url fork "https://x-access-token:${GITHUB_TOKEN}@github.com/clbarrell/express.git"
    fi
  )
  log_ok "Express.js ready on branch $branch (fork remote configured)"
}

# --- Phase 1: Conversion Agent (Docker) ---
run_conversion() {
  local version=$1
  local cluster_name="ralph-express-${RUN_ID}-v${version}"
  local log_file="$STATE_DIR/conversion-v${version}.log"
  local prompt_file="$RALPH_DIR/PROMPT.md"

  log_section "PHASE 1: CONVERSION (v${version})"

  if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN: Skipping conversion agent"
    echo "[dry run] No conversion performed" > "$log_file"
    return 0
  fi

  local prompt_content
  prompt_content=$(cat "$prompt_file")

  local extra_flags=""
  if [[ "$SKIP_INFRA" == "true" ]]; then
    extra_flags="Do NOT create Buildkite infrastructure (cluster, queues, pipelines). Only write pipeline YAML files."
  fi

  local phase_start=$SECONDS
  log "Running conversion agent in Docker (budget: \$${CONVERSION_BUDGET})..."
  log "Cluster: $cluster_name"

  # Mount a .claude dir so session files persist after container exits
  local claude_home="$STATE_DIR/claude-home-v${version}"
  mkdir -p "$claude_home"

  local raw_log="$STATE_DIR/conversion-v${version}-raw.jsonl"

  # Mount customer research scripts if available
  local research_dir="${CUSTOMER_RESEARCH_DIR:-}"
  local -a docker_extra=()
  if [[ -d "$research_dir/scripts" ]]; then
    docker_extra+=(-v "$research_dir/scripts:/research:ro")
    log "Customer research scripts mounted at /research"
  else
    log_warn "No customer research scripts found. Set CUSTOMER_RESEARCH_DIR to enable."
  fi

  docker run --rm \
    -v "$EXPRESS_DIR:/workspace:rw" \
    -v "$SKILLS_REPO:/skills:ro" \
    -v "$claude_home:/home/ralph/.claude:rw" \
    -v "$RALPH_DIR/mcp-config.json:/mcp-config.json:ro" \
    "${docker_extra[@]}" \
    -e ANTHROPIC_API_KEY \
    -e "BUILDKITE_API_TOKEN=${BUILDKITE_API_TOKEN:-}" \
    -e "GITHUB_TOKEN=${GITHUB_TOKEN:-}" \
    -e "PLAIN_API_KEY=${PLAIN_API_KEY:-}" \
    -e "AVOMA_API_KEY=${AVOMA_API_KEY:-}" \
    "$DOCKER_IMAGE" \
      --print \
      --bare \
      --plugin-dir /skills \
      --mcp-config /mcp-config.json \
      --permission-mode bypassPermissions \
      --verbose \
      --output-format stream-json \
      --system-prompt "$prompt_content" \
      --model "$MODEL" \
      --max-budget-usd "$CONVERSION_BUDGET" \
      "Convert Express.js GitHub Actions to Buildkite pipelines. \
Cluster name: ${cluster_name}. Iteration version: ${version}. \
The bk CLI and buildkite-agent are pre-installed. Use BUILDKITE_API_TOKEN for API auth. \
${extra_flags}" \
    2>"$STATE_DIR/conversion-v${version}-stderr.log" > "$raw_log" &
  local docker_pid=$!

  # Show progress while Docker runs
  log "Conversion running (pid: $docker_pid). Raw log: $raw_log"
  touch "$raw_log"
  while kill -0 "$docker_pid" 2>/dev/null; do
    local lines=$(wc -l < "$raw_log" 2>/dev/null || echo 0)
    local elapsed=$(( SECONDS - phase_start ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))
    printf "\r${BLUE}[ralph]${NC} Conversion in progress... %d events, %dm%02ds elapsed" "$lines" "$mins" "$secs" >&2
    sleep 5
  done
  printf "\n" >&2
  local docker_exit=0
  wait "$docker_pid" || docker_exit=$?
  if [[ $docker_exit -ne 0 ]]; then
    log_warn "Conversion agent exited with code $docker_exit (check $STATE_DIR/conversion-v${version}-stderr.log)"
  fi
  local phase_elapsed=$(( SECONDS - phase_start ))
  log_ok "Conversion phase took $(( phase_elapsed / 60 ))m$(( phase_elapsed % 60 ))s"

  # Post-process the stream into a readable summary for the improvement agent
  python3 -c "
import json, sys

out = open('$log_file', 'w')
for line in open('$raw_log'):
    line = line.strip()
    if not line:
        continue
    try:
        evt = json.loads(line)
    except json.JSONDecodeError:
        continue
    t = evt.get('type', '')

    # Assistant text messages
    if t == 'assistant' and 'message' in evt:
        msg = evt['message']
        if isinstance(msg, str):
            out.write(f'## Assistant\n{msg}\n\n')
        elif isinstance(msg, dict):
            for block in msg.get('content', []):
                if block.get('type') == 'text':
                    out.write(f'## Assistant\n{block[\"text\"]}\n\n')
                elif block.get('type') == 'thinking':
                    text = block.get('thinking', '')
                    if len(text) > 500:
                        text = text[:500] + '... [truncated]'
                    out.write(f'## Thinking\n{text}\n\n')
                elif block.get('type') == 'tool_use':
                    name = block.get('name', '?')
                    inp = json.dumps(block.get('input', {}))
                    if len(inp) > 300:
                        inp = inp[:300] + '... [truncated]'
                    out.write(f'## Tool Call: {name}\n{inp}\n\n')

    # Tool results
    elif t == 'tool_result':
        name = evt.get('tool_name', evt.get('name', '?'))
        result = str(evt.get('content', evt.get('output', '')))
        if len(result) > 500:
            result = result[:500] + '... [truncated]'
        out.write(f'## Tool Result: {name}\n{result}\n\n')

    # System/error messages
    elif t == 'error':
        out.write(f'## ERROR\n{json.dumps(evt)}\n\n')

    # Result message (final)
    elif t == 'result':
        cost = evt.get('cost_usd', evt.get('costUsd', '?'))
        duration = evt.get('duration_ms', evt.get('durationMs', '?'))
        out.write(f'## Result\nCost: \${cost}, Duration: {duration}ms\n\n')

out.close()
" 2>/dev/null || {
    log_warn "Failed to post-process conversion log, falling back to raw"
    cp "$raw_log" "$log_file"
  }

  log_ok "Conversion complete. Log: $log_file (raw: $raw_log)"
}

# --- Phase 2: Evaluate ---
run_evaluation() {
  local version=$1
  local eval_file="$STATE_DIR/eval-v${version}.json"
  local cluster_name="ralph-express-${RUN_ID}-v${version}"

  log_section "PHASE 2: EVALUATION (v${version})"
  local phase_start=$SECONDS

  # Use bk CLI for live verification if available
  local -a cluster_args=()
  if command -v bk &>/dev/null && [[ "$SKIP_INFRA" == "false" ]]; then
    cluster_args+=(--cluster-name "$cluster_name")
    log "Live bk CLI verification enabled (cluster: $cluster_name)"
  else
    log_warn "bk CLI not found or --skip-infra set. Skipping live infrastructure & build checks."
  fi

  python3 "$RALPH_DIR/evaluate.py" \
    --express-dir "$EXPRESS_DIR" \
    "${cluster_args[@]}" \
    --version "$version" \
    --output "$eval_file" >&2

  local phase_elapsed=$(( SECONDS - phase_start ))
  log_ok "Evaluation phase took $(( phase_elapsed / 60 ))m$(( phase_elapsed % 60 ))s"

  # Extract score
  local score
  score=$(python3 -c "import json; print(json.load(open('$eval_file'))['total_score'])")
  echo "$score"
}

# --- Phase 3: Improvement Agent (worktree) ---
run_improvement() {
  local version=$1
  local eval_file="$STATE_DIR/eval-v${version}.json"
  local conversion_log="$STATE_DIR/conversion-v${version}.log"
  local improve_log="$STATE_DIR/improve-v${version}.log"
  local history
  history=$(cat "$STATE_DIR/iterations.json")

  log_section "PHASE 3: IMPROVEMENT (v${version})"

  if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN: Skipping improvement agent"
    echo "[dry run] No improvements made" > "$improve_log"
    return 0
  fi

  local improve_prompt
  improve_prompt=$(cat "$RALPH_DIR/IMPROVE.md")

  local phase_start=$SECONDS
  log "Running improvement agent (budget: \$${IMPROVEMENT_BUDGET})..."

  pushd "$SKILLS_REPO" > /dev/null

  # Point the improvement agent at the conversion session files
  local claude_home="$STATE_DIR/claude-home-v${version}"
  local session_dir=""
  if [[ -d "$claude_home/projects" ]]; then
    session_dir="$claude_home"
  fi

  # Also point at the CONVERSION_NOTES.md which has skill gaps
  local conversion_notes="$EXPRESS_DIR/CONVERSION_NOTES.md"

  claude \
    --print \
    --bare \
    --tools "Read,Write,Edit,Glob,Grep" \
    --allowed-tools "Bash(python:evals/*),Bash(git:*)" \
    --permission-mode bypassPermissions \
    --system-prompt "$improve_prompt" \
    --model "$MODEL" \
    --max-budget-usd "$IMPROVEMENT_BUDGET" \
    "Analyze the evaluation results and improve the Buildkite skills.

Eval results: $(cat "$eval_file")

Conversion log is at: $conversion_log

Conversion session files (full tool call trace) are at: $session_dir
Read the session JSON files there to see exactly what the conversion agent did, what tools it called, what errors it hit, and where it struggled.

The conversion agent's CONVERSION_NOTES.md (with documented skill gaps) is at: $conversion_notes

Iteration history: $history

Write your changes summary to: $STATE_DIR/changes-v${version}.md

Current iteration: $version" \
    > "$improve_log" 2>&1 &
  local improve_pid=$!

  # Show progress while improvement agent runs
  log "Improvement running (pid: $improve_pid). Log: $improve_log"
  touch "$improve_log"
  while kill -0 "$improve_pid" 2>/dev/null; do
    local lines=$(wc -l < "$improve_log" 2>/dev/null || echo 0)
    local elapsed=$(( SECONDS - phase_start ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))
    printf "\r${BLUE}[ralph]${NC} Improvement in progress... %d lines, %dm%02ds elapsed" "$lines" "$mins" "$secs" >&2
    sleep 5
  done
  printf "\n" >&2
  wait "$improve_pid" || true

  popd > /dev/null

  local phase_elapsed=$(( SECONDS - phase_start ))
  log_ok "Improvement phase took $(( phase_elapsed / 60 ))m$(( phase_elapsed % 60 ))s. Log: $improve_log"
}

# --- Record iteration result ---
record_iteration() {
  local version=$1
  local score=$2
  local duration_secs=${3:-0}
  local cluster_name="ralph-express-${RUN_ID}-v${version}"
  local timestamp
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  local skills_commit
  skills_commit=$(cd "$SKILLS_REPO" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")

  # Read per-category scores from eval file
  local eval_file="$STATE_DIR/eval-v${version}.json"
  local categories_json="{}"
  if [[ -f "$eval_file" ]]; then
    categories_json=$(python3 -c "
import json
data = json.load(open('$eval_file'))
scores = {k: v['score'] for k, v in data.get('categories', {}).items()}
print(json.dumps(scores))
")
  fi

  # Append to iterations.json
  python3 -c "
import json
history = json.load(open('$STATE_DIR/iterations.json'))
history.append({
    'version': $version,
    'score': $score,
    'timestamp': '$timestamp',
    'cluster': '$cluster_name',
    'skills_commit': '$skills_commit',
    'express_branch': 'ralph/iter-$version',
    'duration_seconds': $duration_secs,
    'scores_by_category': $categories_json
})
json.dump(history, open('$STATE_DIR/iterations.json', 'w'), indent=2)
"

  echo "$version" > "$STATE_DIR/current_version.txt"
}

# --- Print iteration summary ---
print_summary() {
  local version=$1
  local score=$2

  log_section "ITERATION ${version} SUMMARY"

  echo -e "Score: ${BOLD}${score}/100${NC}"

  if [[ -f "$STATE_DIR/eval-v${version}.json" ]]; then
    python3 -c "
import json
data = json.load(open('$STATE_DIR/eval-v${version}.json'))
print()
for cat, result in data.get('categories', {}).items():
    score = result.get('score', 0)
    weight = result.get('weight', 0)
    bar = '#' * int(score / 5) + '-' * (20 - int(score / 5))
    weighted = score * weight / 100
    print(f'  {cat:<25s} {bar} {score:5.1f}/100 (x{weight}% = {weighted:.1f})')
print()
print(f'  Total weighted score: {data[\"total_score\"]}/100')
"
  fi

  # Show history trend
  python3 -c "
import json
history = json.load(open('$STATE_DIR/iterations.json'))
if len(history) > 1:
    print()
    print('  Score history:')
    for h in history:
        v = h['version']
        s = h['score']
        bar = '#' * int(s / 5)
        print(f'    v{v}: {bar} {s}')
" 2>/dev/null || true
}

# --- Run quality eval and save results ---
# Usage: run_quality_eval <label> <output_path> [compare_path]
run_quality_eval() {
  local label=$1
  local output_path=$2
  local compare_path=${3:-}

  log "Running quality eval ($label)..."

  local -a eval_args=(--skill buildkite-pipelines --parallel 10)
  if [[ -n "$compare_path" && -f "$compare_path" ]]; then
    eval_args+=(--compare "$compare_path")
  fi

  local eval_output
  local eval_exit=0
  eval_output=$(cd "$SKILLS_REPO" && python3 evals/run_quality.py "${eval_args[@]}" 2>&1) || eval_exit=$?

  # Print the output (includes summary and comparison)
  echo "$eval_output" >&2

  # Extract the saved results path and copy to state dir
  local saved_path
  saved_path=$(echo "$eval_output" | grep -o 'Results saved to: .*' | head -1 | sed 's/Results saved to: //')
  if [[ -n "$saved_path" && -f "$saved_path" ]]; then
    cp "$saved_path" "$output_path"
    log_ok "Quality eval ($label) results saved to: $output_path"
  else
    log_warn "Could not find saved quality eval results"
  fi

  if [[ $eval_exit -eq 0 ]]; then
    log_ok "Quality eval ($label): all evals passed"
  else
    log_warn "Quality eval ($label): some evals failed"
  fi

  return $eval_exit
}

# --- Commit skill changes after improvement ---
commit_skill_changes() {
  local version=$1
  local score=$2

  (
    cd "$SKILLS_REPO"

    # Stage only skill and eval files (not ralph/ state)
    git add skills/ evals/ 2>/dev/null || true

    # Check if there are staged changes
    if git diff --cached --quiet 2>/dev/null; then
      log "No skill changes to commit for iteration $version"
      return 0
    fi

    # Build commit message
    local msg="ralph: iteration ${version} improvements (score: ${score}/100)"
    if [[ -f "$STATE_DIR/changes-v${version}.md" ]]; then
      local details
      details=$(head -c 500 "$STATE_DIR/changes-v${version}.md")
      msg="${msg}

${details}"
    fi

    git commit -m "$msg"
    log_ok "Committed skill changes for iteration $version"
  )
}

# ============================================================
# MAIN LOOP
# ============================================================

main() {
  log_section "RALPH WIGGUM LOOP"
  log "Skills repo: $SKILLS_REPO"
  log "Max iterations: $MAX_ITERATIONS"
  log "Pass threshold: $PASS_THRESHOLD%"
  log "Model: $MODEL"
  log "Dry run: $DRY_RUN"

  check_prerequisites
  setup_express
  init_state

  log "State dir: $STATE_DIR"
  log "Run ID: $RUN_ID (cluster prefix: ralph-express-${RUN_ID})"

  local plateau_count=0
  local best_score=0

  while true; do
    local version
    version=$(next_version)

    if [[ $version -gt $MAX_ITERATIONS ]]; then
      log_err "Maximum iterations reached ($MAX_ITERATIONS). Best score: $best_score"
      break
    fi

    log_section "ITERATION ${version} / ${MAX_ITERATIONS}"
    local iter_start=$SECONDS

    if [[ "$RESUME" == "true" ]]; then
      RESUME=false  # Only skip once, subsequent iterations run normally
      log "Resuming iteration $version — skipping conversion, picking up from evaluation..."
      # Verify Express repo exists and has conversion output
      if [[ ! -d "$EXPRESS_DIR/.git" ]]; then
        log_err "Express repo not found at $EXPRESS_DIR — cannot resume without prior conversion output."
        exit 1
      fi
      local express_branch
      express_branch=$(cd "$EXPRESS_DIR" && git branch --show-current 2>/dev/null || echo "unknown")
      log "Express repo on branch: $express_branch"
      if [[ "$express_branch" != "ralph/iter-"* ]]; then
        log_warn "Express repo is on '$express_branch', not a ralph iteration branch. Evaluation may use stale data."
      fi
    else
      # Reset Express.js to clean state
      reset_express "$version"

      # Phase 1: Conversion
      run_conversion "$version"
    fi

    # Phase 2: Evaluate
    local score
    score=$(run_evaluation "$version")

    local iter_elapsed=$(( SECONDS - iter_start ))

    # Record result
    record_iteration "$version" "$score" "$iter_elapsed"

    # Print summary
    print_summary "$version" "$score"

    # Track best score (require minimum delta to count as improvement)
    if (( $(echo "$score >= $best_score + $PLATEAU_MIN_DELTA" | bc -l) )); then
      best_score=$score
      plateau_count=0
    else
      plateau_count=$((plateau_count + 1))
    fi

    # Check termination: pass threshold
    if (( $(echo "$score >= $PASS_THRESHOLD" | bc -l) )); then
      log_ok "PASS! Score $score >= $PASS_THRESHOLD threshold. Done after $version iterations."
      break
    fi

    # Check termination: plateau
    if [[ $plateau_count -ge $PLATEAU_LIMIT ]]; then
      log_warn "Plateau: no improvement in $PLATEAU_LIMIT iterations. Best: $best_score"
      break
    fi

    # Quality eval baseline (before improvement)
    run_quality_eval "baseline" "$STATE_DIR/quality-baseline-v${version}.json" || true

    # Phase 3: Improvement
    run_improvement "$version"

    # Quality eval post-improvement (compare against baseline)
    run_quality_eval "post-improvement" "$STATE_DIR/quality-post-v${version}.json" \
        "$STATE_DIR/quality-baseline-v${version}.json" || true

    # Commit skill changes
    commit_skill_changes "$version" "$score"

    # Append timestamped entry to migration journal
    local journal_ts
    journal_ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local journal_file="$RALPH_DIR/MIGRATION_JOURNAL.md"
    if [[ -f "$STATE_DIR/changes-v${version}.md" ]]; then
      {
        echo ""
        echo "---"
        echo ""
        echo "## Run $(basename "$STATE_DIR") / Iteration $version -- $journal_ts"
        echo ""
        echo "**Score: ${score}/100**"
        echo ""
        cat "$STATE_DIR/changes-v${version}.md"
      } >> "$journal_file"
      log_ok "Appended iteration $version results to MIGRATION_JOURNAL.md"
    fi

    log_ok "Iteration $version complete (score: $score). Starting next iteration..."
  done

  # Final report
  log_section "FINAL REPORT"
  python3 -c "
import json
history = json.load(open('$STATE_DIR/iterations.json'))
print(f'Total iterations: {len(history)}')
if history:
    best = max(history, key=lambda h: h['score'])
    print(f'Best score: {best[\"score\"]}/100 (iteration v{best[\"version\"]})')
    print(f'Best cluster: {best[\"cluster\"]}')
    print()
    print('All iterations:')
    for h in history:
        print(f'  v{h[\"version\"]}: {h[\"score\"]}/100 ({h[\"timestamp\"]})')
"
}

main "$@"
