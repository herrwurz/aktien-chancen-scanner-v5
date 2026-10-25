#!/usr/bin/env bash
set -Eeuo pipefail

input_dir=${INPUT_DIR:-/opt/scanner-v26-market-data}
output_dir=${OUTPUT_DIR:-/opt/scanner-v26-opportunities}
image=${IMAGE:-scanner-v26-opportunities}
signal_date=${SIGNAL_DATE:-2026-10-23}

if [[ ! "$signal_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "SIGNAL_DATE must use YYYY-MM-DD." >&2
  exit 2
fi
for required in sec-index.db sec-index.db.manifest.json market-data.sqlite \
  coverage-100.json coverage-100.sha256 benchmark-spy.json benchmark-spy.sha256; do
  [[ -f "$input_dir/$required" ]] || { echo "Missing input artifact: $required" >&2; exit 2; }
done
input_dir=$(cd -- "$input_dir" && pwd -P)
output_dir=$(realpath -m -- "$output_dir")
if [[ "$input_dir" == "$output_dir" || "$output_dir" == "$input_dir"/* \
  || "$input_dir" == "$output_dir"/* ]]; then
  echo "INPUT_DIR and OUTPUT_DIR must not overlap." >&2
  exit 2
fi
(cd -- "$input_dir" && sha256sum -c coverage-100.sha256 && sha256sum -c benchmark-spy.sha256)
if [[ "${VALIDATE_ONLY:-0}" == "1" ]]; then
  echo "Expanded input integrity and paths validated."
  exit 0
fi

mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docker build -t "$image" "$repo_root"
scan_started=$SECONDS
review_args=()
if [[ -f "$input_dir/instrument-reviews.json" ]]; then
  review_args=(--instrument-reviews /input/instrument-reviews.json)
fi
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$input_dir,dst=/input,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.opportunities.cli \
    --research-index /input/sec-index.db \
    --market-archive /input/market-data.sqlite \
    --pilot-coverage /input/coverage-100.json \
    --benchmark-asset-id benchmark:SPY \
    --as-of archive-latest \
    --signal-date "$signal_date" \
    --output /output \
    "${review_args[@]}"

(cd -- "$output_dir" && sha256sum -c opportunities.sha256)
scan_duration=$((SECONDS - scan_started))
python3 - "$output_dir/opportunities.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({
    "mode": report["mode"],
    "signal_date": report["signal_date"],
    "archive_sha256": report["archive_sha256"],
    "benchmark_status": report["benchmark_status"],
    "coverage": report["coverage"],
    "source_pilot": report["source_pilot"],
    "top_candidates": report["top_candidates"],
    "top_watchlist": report["top_watchlist"],
}, indent=2, sort_keys=True))
PY
echo "Scanner runtime (including container start): ${scan_duration}s"
echo "Read-only modeled research report: $output_dir/opportunities.json"
