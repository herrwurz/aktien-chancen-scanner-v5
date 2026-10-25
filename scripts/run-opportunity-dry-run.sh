#!/usr/bin/env bash
set -Eeuo pipefail

pilot_dir=${PILOT_DIR:-/opt/scanner-v251-tiingo-pilot}
output_dir=${OUTPUT_DIR:-/opt/scanner-v252-opportunities}
image=${IMAGE:-scanner-v252-opportunities}
signal_date=${SIGNAL_DATE:-2025-12-31}

if [[ ! "$signal_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "SIGNAL_DATE must use YYYY-MM-DD." >&2
  exit 2
fi
for required in sec-pilot-index.db sec-pilot-index.db.manifest.json market-data.sqlite coverage.json coverage.sha256; do
  if [[ ! -f "$pilot_dir/$required" ]]; then
    echo "Missing V2.5.1 pilot artifact: $pilot_dir/$required" >&2
    exit 2
  fi
done
pilot_dir=$(cd -- "$pilot_dir" && pwd -P)
output_dir=$(realpath -m -- "$output_dir")
if [[ "$pilot_dir" == "$output_dir" || "$output_dir" == "$pilot_dir"/* || "$pilot_dir" == "$output_dir"/* ]]; then
  echo "PILOT_DIR and OUTPUT_DIR must not overlap." >&2
  exit 2
fi
(cd -- "$pilot_dir" && sha256sum -c coverage.sha256)
if [[ "${VALIDATE_ONLY:-0}" == "1" ]]; then
  echo "Runner paths and source coverage integrity validated."
  exit 0
fi
mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docker build -t "$image" "$repo_root"
scan_started=$SECONDS
review_args=()
if [[ -f "$pilot_dir/instrument-reviews.json" ]]; then
  review_args=(--instrument-reviews /input/instrument-reviews.json)
fi
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$pilot_dir,dst=/input,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.opportunities.cli \
    --research-index /input/sec-pilot-index.db \
    --market-archive /input/market-data.sqlite \
    --pilot-coverage /input/coverage.json \
    --as-of archive-latest \
    --signal-date "$signal_date" \
    --output /output \
    "${review_args[@]}"

(cd -- "$output_dir" && sha256sum -c opportunities.sha256)
scan_duration=$((SECONDS - scan_started))
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$output_dir,dst=/output,readonly" \
  "$image" python -c '
import json
report = json.load(open("/output/opportunities.json", encoding="utf-8"))
summary = {
    "mode": report["mode"],
    "signal_date": report["signal_date"],
    "coverage": report["coverage"],
    "source_pilot": report["source_pilot"],
    "top_candidates": [
        {
            "ticker": row["ticker"],
            "score": row["score"],
            "selection_reasons": row["selection_reasons"],
            "uncertainties": row["uncertainties"],
            "reference_date": (row.get("risk") or {}).get("reference_date"),
            "reference_price": (row.get("risk") or {}).get("reference_price"),
        }
        for row in report["top_candidates"]
    ],
    "top_watchlist": [
        {
            "ticker": row["ticker"],
            "score": row["score"],
            "selection_reasons": row["selection_reasons"],
            "uncertainties": row["uncertainties"],
            "reference_date": (row.get("risk") or {}).get("reference_date"),
            "reference_price": (row.get("risk") or {}).get("reference_price"),
        }
        for row in report["top_watchlist"]
    ],
}
print(json.dumps(summary, indent=2, sort_keys=True))'
echo "Scanner runtime (including container start): ${scan_duration}s"
echo "Read-only modeled research report: $output_dir/opportunities.json"
