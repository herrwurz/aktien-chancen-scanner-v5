#!/usr/bin/env bash
set -eu

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 INPUT_MANIFEST RESEARCH_INDEX OUTPUT_JSON IMAGE" >&2
  exit 2
fi

input_manifest=$1
research_index=$2
output_json=$3
image_name=$4
research_manifest="${research_index}.manifest.json"
output_dir=$(dirname "$output_json")

mkdir -p "$output_dir"
docker run --rm --network none --read-only --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$input_manifest,dst=/blind/inputs.json,readonly" \
  --mount "type=bind,src=$research_index,dst=/research/index.db,readonly" \
  --mount "type=bind,src=$research_manifest,dst=/research/index.db.manifest.json,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image_name" python -m scanner.hebeltrader.detective.benchmark_scan \
  --inputs /blind/inputs.json --research-index /research/index.db \
  --output "/output/$(basename "$output_json")"
