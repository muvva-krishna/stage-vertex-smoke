#!/usr/bin/env bash
# Launch one fresh, no-tools trace-detector session per rendered cluster.
# Results are written to stage4_context_grid/results/raw/<size>/<cluster>.jsonl
# Nothing here reads evaluator maps or labels.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAP="${SNAP:-$ROOT/stage4_context_grid/agent_snapshots_v2}"
OUT="${OUT:-$ROOT/stage4_context_grid/results/raw_v2}"
SANDBOX="${SANDBOX:-/tmp/opencode/tw_sandbox}"
MODEL="${MODEL:-opencode-go/muse-spark-1.3-contributor#high}"
CONCURRENCY="${CONCURRENCY:-20}"
# ID prefix selects the batch: C = batch 1, D = batch 2, * = all.
PREFIX="${PREFIX:-C}"
# Sizes to run: default N1 N4 (N8 only when explicitly requested).
SIZES="${SIZES:-N1 N4}"

mkdir -p "$OUT/N1" "$OUT/N4" "$OUT/N8" "$SANDBOX/inbox"

run_one() {
  local size="$1" dir="$2"
  local id; id="$(basename "$dir")"
  local jsonl="$OUT/$size/$id.jsonl"
  local err="$OUT/$size/$id.err"
  if [ -s "$jsonl" ] && grep -q '"type":"text"' "$jsonl" 2>/dev/null; then
    return 0
  fi
  (
    cd "$SANDBOX" || exit 1
    for attempt in 1 2 3; do
      # Give the provider only a random-named temporary attachment from the
      # clean sandbox, never a repository path or C/D/N-bearing filename.
      local attachment
      attachment="$(mktemp "$SANDBOX/inbox/prompt.XXXXXXXX.txt")" || exit 1
      cp "$dir/prompt.txt" "$attachment" || { rm -f "$attachment"; exit 1; }
      # --file for ALL clusters: identical delivery at every size, and it
      # avoids Linux's 128KB single-argv limit that broke inline prompts.
      timeout 1200 opencode run --agent trace-detector --model "$MODEL" \
        --format json -f "$attachment" \
        "The attached file IS the complete prompt. Follow it exactly and return the JSON verdict." > "$jsonl" 2> "$err"
      rc=$?
      rm -f "$attachment"
      if [ "$rc" -eq 0 ] && grep -q '"type":"text"' "$jsonl" 2>/dev/null; then
        exit 0
      fi
      sleep $((attempt * 15))
    done
    echo "FAILED $size/$id (rc=$rc)" >> "$OUT/failures.txt"
    exit 1
  )
}
export -f run_one
export OUT SANDBOX MODEL

for size in $SIZES; do
  # shellcheck disable=SC2086: PREFIX intentionally unquoted for '*' matching.
  for dir in "$SNAP"/$PREFIX${size#N}-*; do
    [ -d "$dir" ] || continue
    printf '%s\0%s\0' "$size" "$dir"
  done
done | xargs -0 -n 2 -P "$CONCURRENCY" bash -c 'run_one "$@"' _

echo "done: $(find "$OUT/N1" "$OUT/N4" "$OUT/N8" -name '*.jsonl' 2>/dev/null | wc -l) raw files"
[ -f "$OUT/failures.txt" ] && cat "$OUT/failures.txt"
