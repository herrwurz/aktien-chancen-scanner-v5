#!/usr/bin/env bash
set -eu

if [ "$#" -ne 5 ]; then
  echo "Usage: $0 TEASER PUBLICATION_AT RIGHTS_STATUS RESEARCH_INDEX OUTPUT_DIR" >&2
  exit 2
fi

teaser_path=$1
publication_at=$2
rights_status=$3
research_index=$4
output_dir=$5
image_name=${DETECTIVE_IMAGE:-scanner-detective-v3}

mkdir -p "$output_dir"

docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$teaser_path,dst=/input/teaser,readonly" \
  --mount "type=bind,src=$research_index,dst=/research/index.db,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image_name" python -m scanner.hebeltrader.detective.real_acceptance \
  --teaser /input/teaser --publication-at "$publication_at" --rights-status "$rights_status" \
  --research-index /research/index.db --output /output

case "$teaser_path" in
  *.pdf|*.PDF) input_args=(--pdf /input/teaser) ;;
  *) input_args=(--text-file /input/teaser) ;;
esac

docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$teaser_path,dst=/input/teaser,readonly" \
  --mount "type=bind,src=$research_index,dst=/research/index.db,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  "$image_name" python -m scanner.hebeltrader.detective.cli "${input_args[@]}" \
  --publication-at "$publication_at" --research-mode indexed_research \
  --research-index /research/index.db --output /output/analysis.json

sha256sum "$output_dir/analysis.json" > "$output_dir/analysis.sha256"
echo "Read-only V3 report: $output_dir/analysis.json"
