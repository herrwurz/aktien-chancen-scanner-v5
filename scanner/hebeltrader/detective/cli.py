"""Offline CLI for the HEBELTRADER detective MVP."""

import argparse
import base64
import json
from pathlib import Path

from scanner.config import Settings
from scanner.hebeltrader.detective.factory import build_detective
from scanner.hebeltrader.detective.schemas import DetectiveRequest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--image-media-type", choices=("image/png", "image/jpeg", "image/webp"))
    parser.add_argument("--publication-at")
    parser.add_argument(
        "--research-mode",
        choices=("fixture", "cached_research", "live_research"),
        default="fixture",
    )
    parser.add_argument("--research-snapshot", type=Path)
    parser.add_argument("--research-cache-dir", type=Path)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--request-timeout-seconds", type=float, default=10)
    parser.add_argument("--max-duration-seconds", type=float, default=120)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.image and not args.image_media_type:
        parser.error("--image-media-type is required with --image")
    payload = DetectiveRequest(
        teaser_text=args.text_file.read_text(encoding="utf-8") if args.text_file else "",
        screenshot_base64=(
            base64.b64encode(args.image.read_bytes()).decode() if args.image else None
        ),
        screenshot_media_type=args.image_media_type,
        publication_at=args.publication_at,
    )
    values = {
        "detective_research_mode": args.research_mode,
        "detective_live_allow_network": args.allow_network,
        "detective_live_max_requests": args.max_requests,
        "detective_live_max_candidates": args.max_candidates,
        "detective_live_request_timeout_seconds": args.request_timeout_seconds,
        "detective_live_max_duration_seconds": args.max_duration_seconds,
    }
    if args.research_snapshot:
        values["detective_research_snapshot"] = args.research_snapshot
    if args.research_cache_dir:
        values["detective_research_cache_dir"] = args.research_cache_dir
    report = build_detective(Settings(_env_file=None, **values)).analyze(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "candidates": len(report["candidates"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
