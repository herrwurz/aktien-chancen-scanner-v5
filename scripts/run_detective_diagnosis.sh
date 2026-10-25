#!/usr/bin/env bash
# Offline teaser diagnosis helper. Does not claim a real hit rate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUTS="${1:-$ROOT/tests/fixtures/detective-hypothesis/mini_benchmark/manifest.json}"
LABELS="${2:-$ROOT/tests/fixtures/detective-hypothesis/mini_benchmark/labels.json}"
OUT="${3:-/tmp/detective-diagnosis/run}"
cd "$ROOT"
ARGS=(--inputs "$INPUTS" --output-prefix "$OUT" --service hypothesis_fixture)
if [[ -f "$LABELS" ]]; then
  ARGS+=(--labels "$LABELS")
fi
exec python3 -m scanner.hebeltrader.detective.diagnose "${ARGS[@]}"
