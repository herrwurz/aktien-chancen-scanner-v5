#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 0 || $- == *x* ]]; then
  echo "Usage: scripts/run-tiingo-benchmark.sh (without shell tracing)" >&2
  exit 2
fi
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output_dir=${OUTPUT_DIR:-/opt/scanner-v26-market-data}
image=${IMAGE:-scanner-v26-market-data}
start=${START_DATE:-2025-01-01}
end=${END_DATE:-2026-10-24}
mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
docker info >/dev/null
docker build -t "$image" "$repo_root"
if [[ -z "${TIINGO_API_TOKEN:-}" ]]; then
  read -rsp 'Renewed TIINGO_API_TOKEN: ' TIINGO_API_TOKEN
  printf '\n'
  export TIINGO_API_TOKEN
fi
[[ -n "$TIINGO_API_TOKEN" ]] || { echo "A renewed token is required." >&2; exit 2; }
trap 'unset TIINGO_API_TOKEN' EXIT
as_of=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
docker run --rm --network bridge --user "$(id -u):$(id -g)" \
  -e TIINGO_API_TOKEN \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.market_data.cli benchmark \
    --market-db /output/market-data.sqlite --raw-cache /output/tiingo-raw \
    --quota-ledger /output/tiingo-quota.jsonl --output /output/benchmark-spy \
    --start "$start" --end "$end" --as-of "$as_of" --max-requests 3 \
    --correction-lookback-days 10 --monthly-cost-eur 0 \
    --allow-network --authorize-provider-usage
unset TIINGO_API_TOKEN
trap - EXIT
(cd -- "$output_dir" && sha256sum -c benchmark-spy.sha256)
echo "Benchmark report: $output_dir/benchmark-spy.json"
