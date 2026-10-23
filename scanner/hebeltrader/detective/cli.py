"""Offline CLI for the HEBELTRADER detective MVP."""

import argparse
import base64
import json
from pathlib import Path

from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--image-media-type", choices=("image/png", "image/jpeg", "image/webp"))
    parser.add_argument("--publication-at")
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
    report = DetectiveService().analyze(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "candidates": len(report["candidates"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
