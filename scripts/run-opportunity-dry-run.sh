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
for required in sec-pilot-index.db sec-pilot-index.db.manifest.json market-data.sqlite; do
  if [[ ! -f "$pilot_dir/$required" ]]; then
    echo "Missing V2.5.1 pilot artifact: $pilot_dir/$required" >&2
    exit 2
  fi
done
mkdir -p -- "$output_dir"
chmod 700 -- "$output_dir"
pilot_dir=$(cd -- "$pilot_dir" && pwd)
output_dir=$(cd -- "$output_dir" && pwd)
if [[ "$pilot_dir" == "$output_dir" ]]; then
  echo "OUTPUT_DIR must differ from the read-only pilot directory." >&2
  exit 2
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docker build -t "$image" "$repo_root"
as_of=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$pilot_dir,dst=/input,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image" python -m scanner.opportunities.cli \
    --research-index /input/sec-pilot-index.db \
    --market-archive /input/market-data.sqlite \
    --as-of "$as_of" \
    --signal-date "$signal_date" \
    --output /output

(cd -- "$output_dir" && sha256sum -c opportunities.sha256)
echo "Read-only modeled research report: $output_dir/opportunities.json"
