#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Run the isolated Scanner V6 V2.5.1 Tiingo pilot with a renewed Tiingo token.

Usage: scripts/run-tiingo-pilot.sh

Optional environment variables:
  SOURCE_REPORTS  Existing archived research reports (read-only mount).
                  Default: /opt/aktien-chancen-scanner-v5/reports
  OUTPUT_DIR      Isolated pilot artifacts. Default: /opt/scanner-v251-tiingo-pilot
  IMAGE           Local image name. Default: scanner-v251-pr21

The runner prompts for the token when TIINGO_API_TOKEN is unset. It does not use Docker Compose or PostgreSQL.
It does not modify Immich or the source reports.
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi
if [[ $- == *x* ]]; then
  echo "Refusing to run with shell tracing because it could expose secrets." >&2
  exit 2
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_reports=${SOURCE_REPORTS:-/opt/aktien-chancen-scanner-v5/reports}
output_dir=${OUTPUT_DIR:-/opt/scanner-v251-tiingo-pilot}
image=${IMAGE:-scanner-v251-pr21}

if [[ ! -d "$source_reports" ]]; then
  echo "SEC reports directory not found: $source_reports" >&2
  exit 2
fi
mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"
source_reports=$(cd -- "$source_reports" && pwd)
output_dir=$(cd -- "$output_dir" && pwd)
if [[ "$output_dir" == "$source_reports" || "$output_dir" == "$source_reports"/* ]]; then
  echo "OUTPUT_DIR must be independent from SOURCE_REPORTS." >&2
  exit 2
fi

docker info >/dev/null
docker build -t "$image" "$repo_root"

docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$source_reports,dst=/source-reports,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.market_data.cli build-sec-pilot-index \
  --sec-cache-root /source-reports \
  --index /output/sec-pilot-index.db \
  --audit-output /output/sec-pilot-index.audit.json

if [[ -z "${TIINGO_API_TOKEN:-}" ]]; then
  read -rsp 'Renewed TIINGO_API_TOKEN: ' TIINGO_API_TOKEN
  printf '\n'
  export TIINGO_API_TOKEN
fi
if [[ -z "$TIINGO_API_TOKEN" ]]; then
  echo "A renewed Tiingo token is required." >&2
  exit 2
fi
trap 'unset TIINGO_API_TOKEN' EXIT

as_of=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
docker run --rm --network bridge --user "$(id -u):$(id -g)" \
  -e TIINGO_API_TOKEN \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.market_data.cli pilot \
  --index /output/sec-pilot-index.db \
  --sec-index-audit /output/sec-pilot-index.audit.json \
  --market-db /output/market-data.sqlite \
  --raw-cache /output/tiingo-raw \
  --output /output/coverage \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --as-of "$as_of" \
  --count 10 \
  --max-requests 30 \
  --max-duration-seconds 120 \
  --monthly-cost-eur 0 \
  --allow-network \
  --authorize-provider-usage

unset TIINGO_API_TOKEN
trap - EXIT
(cd -- "$output_dir" && sha256sum -c coverage.sha256)

docker run --rm --network none \
  --mount "type=bind,src=$output_dir,dst=/output,readonly" \
  "$image" python -c \
  'import json; r=json.load(open("/output/coverage.json")); print(json.dumps({k:r.get(k) for k in ("status","blocker_code","selected_count","successful_instruments","requests_attempted","cost_eur")}, sort_keys=True))'

echo "Reports: $output_dir/coverage.json and $output_dir/coverage.csv"
