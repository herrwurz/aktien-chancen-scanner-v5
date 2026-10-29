#!/usr/bin/env bash
set -eu

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 REFERENCE_JSON NEW_OUTPUT_DIRECTORY IMAGE" >&2
  exit 2
fi
reference_file=$1
output_root=$2
image_name=$3

mkdir -p "$(dirname "$output_root")"
# A fresh directory prevents accidentally mounting a source tree or old solutions.
mkdir "$output_root"
mkdir "$output_root/scans"
python -m scanner.hebeltrader.detective.reference_cases export \
  --references "$reference_file" --output "$output_root/inputs.json"
input_file=$(realpath "$output_root/inputs.json")
scan_directory=$(realpath "$output_root/scans")

docker run --rm --network none --read-only --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$input_file,dst=/blind/inputs.json,readonly" \
  --mount "type=bind,src=$scan_directory,dst=/output" \
  "$image_name" python -m scanner.hebeltrader.detective.reference_scan \
  --inputs /blind/inputs.json --root /output
