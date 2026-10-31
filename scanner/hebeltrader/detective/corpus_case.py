"""Load a corpus-v1 case (inputs + packet) for offline investigate / readiness."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

DEFAULT_CORPUS_DIR = Path("docs/examples/source-packets/corpus-v1")
BLOCKED_CASES = frozenset({"HT-016"})


def corpus_paths(
    case_id: str,
    *,
    variant: str = "named",
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
) -> dict[str, Path]:
    if variant not in {"named", "original"}:
        raise ValueError("variant must be named or original")
    case_id = case_id.upper()
    if case_id in BLOCKED_CASES:
        raise ValueError(
            f"{case_id} is blocked (no publication_at); see ht-016-blocked/, not corpus-v1"
        )
    inputs = corpus_dir / f"{case_id}.inputs.{variant}.json"
    packet = corpus_dir / "packets" / f"{case_id}.json"
    if not inputs.exists():
        raise FileNotFoundError(f"missing corpus inputs: {inputs}")
    if not packet.exists():
        raise FileNotFoundError(f"missing corpus packet: {packet}")
    return {"inputs": inputs, "packet": packet, "manifest": corpus_dir / "manifest.json"}


def load_corpus_case(
    case_id: str,
    *,
    variant: str = "named",
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
) -> dict:
    """Return request fields + documents for Investigator / investigate_cli."""
    paths = corpus_paths(case_id, variant=variant, corpus_dir=corpus_dir)
    payload = json.loads(paths["inputs"].read_text(encoding="utf-8"))
    case = payload["cases"][0]
    documents = json.loads(paths["packet"].read_text(encoding="utf-8"))
    expected = None
    if paths["manifest"].exists():
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        expected = next(
            (
                row.get("expected_ticker")
                for row in manifest.get("cases") or []
                if row.get("case_id") == case["case_id"]
            ),
            None,
        )
    publication_at = None
    if case.get("publication_at"):
        publication_at = datetime.fromisoformat(case["publication_at"])
    publication_date = None
    if case.get("publication_date"):
        publication_date = date.fromisoformat(str(case["publication_date"])[:10])
    return {
        "case_id": case["case_id"],
        "variant": variant,
        "expected_ticker": expected,
        "headline": case.get("headline") or "",
        "teaser_text": case.get("teaser_text") or case.get("headline") or "",
        "publication_at": publication_at,
        "publication_date": publication_date,
        "evaluation_class": payload.get("evaluation_class") or "development_regression",
        "documents": documents,
        "paths": {key: str(value) for key, value in paths.items()},
        "historical_blind": True,
    }
