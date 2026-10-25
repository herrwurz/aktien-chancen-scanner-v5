#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Run one isolated, resumable Tiingo universe-expansion batch.

  BATCH_OFFSET=0 BATCH_COUNT=40 scripts/run-tiingo-expansion.sh

Run further pages in later UTC hours with offsets 40 and 80. The persistent quota ledger applies
the documented free-tier hard stops. BATCH_COUNT may not exceed 40. Existing raw responses and
archive revisions are reused. The token is prompted without echo and never written to an image,
report or command line.

Optional variables:
  SOURCE_REPORTS=/opt/scanner-v251-sec-source  (read-only SEC archives)
  OUTPUT_DIR=/opt/scanner-v26-market-data      (isolated output)
  IMAGE=scanner-v26-market-data
  START_DATE=2025-01-01 END_DATE=2026-10-24
EOF
}

if [[ "${1:-}" == "--help" ]]; then usage; exit 0; fi
if [[ $# -ne 0 ]]; then usage >&2; exit 2; fi
if [[ $- == *x* ]]; then echo "Shell tracing could expose secrets; refusing." >&2; exit 2; fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_reports=${SOURCE_REPORTS:-/opt/scanner-v251-sec-source}
output_dir=${OUTPUT_DIR:-/opt/scanner-v26-market-data}
image=${IMAGE:-scanner-v26-market-data}
offset=${BATCH_OFFSET:-0}
count=${BATCH_COUNT:-40}
start=${START_DATE:-2025-01-01}
end=${END_DATE:-2026-10-24}

[[ "$offset" =~ ^[0-9]+$ ]] || { echo "BATCH_OFFSET must be non-negative." >&2; exit 2; }
[[ "$count" =~ ^[0-9]+$ ]] && (( count >= 1 && count <= 40 )) || {
  echo "BATCH_COUNT must be between 1 and 40." >&2; exit 2;
}
[[ -d "$source_reports" ]] || { echo "SEC source missing: $source_reports" >&2; exit 2; }
mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"
source_reports=$(cd -- "$source_reports" && pwd)
output_dir=$(cd -- "$output_dir" && pwd)
[[ "$output_dir" != "$source_reports" && "$output_dir" != "$source_reports"/* ]] || {
  echo "OUTPUT_DIR must be separate from SOURCE_REPORTS." >&2; exit 2;
}

docker info >/dev/null
docker build -t "$image" "$repo_root"
if [[ ! -s "$output_dir/sec-index.db" ]]; then
  docker run --rm --network none --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$source_reports,dst=/source,readonly" \
    --mount "type=bind,src=$output_dir,dst=/output" \
    "$image" python -m scanner.market_data.cli build-sec-pilot-index \
      --sec-cache-root /source --index /output/sec-index.db \
      --audit-output /output/sec-index.audit.json
fi

if [[ -z "${TIINGO_API_TOKEN:-}" ]]; then
  read -rsp 'Renewed TIINGO_API_TOKEN: ' TIINGO_API_TOKEN
  printf '\n'
  export TIINGO_API_TOKEN
fi
[[ -n "$TIINGO_API_TOKEN" ]] || { echo "A renewed token is required." >&2; exit 2; }
trap 'unset TIINGO_API_TOKEN' EXIT

as_of=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
name=$(printf 'batch-%04d' "$offset")
docker run --rm --network bridge --user "$(id -u):$(id -g)" \
  -e TIINGO_API_TOKEN \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.market_data.cli pilot \
    --index /output/sec-index.db --sec-index-audit /output/sec-index.audit.json \
    --market-db /output/market-data.sqlite --raw-cache /output/tiingo-raw \
    --quota-ledger /output/tiingo-quota.jsonl --output "/output/$name" \
    --start "$start" --end "$end" --as-of "$as_of" \
    --count "$count" --selection-offset "$offset" --max-requests 50 \
    --max-duration-seconds 300 --correction-lookback-days 10 --monthly-cost-eur 0 \
    --allow-network --authorize-provider-usage

unset TIINGO_API_TOKEN
trap - EXIT
(cd -- "$output_dir" && sha256sum -c "$name.sha256")
echo "Batch report: $output_dir/$name.json"
