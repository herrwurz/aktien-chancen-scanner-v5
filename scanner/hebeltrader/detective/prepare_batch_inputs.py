"""Write original + named input manifests for a SEC packet batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _named_teaser(
    original: str,
    *,
    issuer: str,
    products: list[str],
    acquisitions: list[str] | None = None,
) -> str:
    bits = [f"Konzern {issuer}"]
    acquisitions = acquisitions or []
    for target in acquisitions[:2]:
        bits.append(f"Mit der Übernahme von {target}")
    if len(products) >= 2:
        bits.append(f"Wachstumstreiber {products[0]} und {products[1]} heben den Umsatz")
    elif products:
        bits.append(f"Wachstumstreiber {products[0]} heben den Umsatz")
    extra = " — ".join(bits) + "."
    return (
        original.rstrip()
        + "\n\nZusätzlicher entwicklungsdiagnostischer Hinweis (nicht Original-Teaser): "
        + extra
    )


def prepare(manifest: Path, *, refs: Path, out_dir: Path) -> dict:
    batch = json.loads(manifest.read_text(encoding="utf-8"))
    ref_payload = json.loads(refs.read_text(encoding="utf-8"))
    ref_cases = {
        c["case_id"]: c
        for c in (
            ref_payload
            if isinstance(ref_payload, list)
            else ref_payload.get("cases", ref_payload.get("inputs", []))
        )
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for entry in batch["cases"]:
        case_id = entry["case_id"]
        ref = ref_cases[case_id]
        headline = ref.get("headline") or ""
        teaser = ref.get("teaser_text") or headline
        if not teaser:
            raise ValueError(f"{case_id}: missing teaser_text and headline")
        pub = ref["publication_at"]
        headline = headline or teaser.split("\n", 1)[0]
        date = pub[:10]
        original = {
            "schema_version": 1,
            "corpus_kind": "development_regression",
            "evaluation_class": "development_regression",
            "independent_benchmark": False,
            "note": f"{case_id} original teaser; batch-10.",
            "cases": [
                {
                    "case_id": case_id,
                    "headline": headline,
                    "teaser_text": teaser,
                    "publication_date": date,
                    "publication_at": pub,
                }
            ],
        }
        named = {
            "schema_version": 1,
            "corpus_kind": "development_regression",
            "evaluation_class": "development_regression",
            "independent_benchmark": False,
            "note": (
                f"{case_id} DEVELOPMENTAL enrichment with Konzern/products; "
                "not a freeze input. Call-PDF remains resolution-only."
            ),
            "cases": [
                {
                    "case_id": case_id,
                    "headline": headline,
                    "teaser_text": _named_teaser(
                        teaser,
                        issuer=entry["issuer_display"],
                        products=entry.get("named_products") or [],
                        acquisitions=entry.get("named_acquisitions") or [],
                    ),
                    "publication_date": date,
                    "publication_at": pub,
                }
            ],
        }
        op = out_dir / f"{case_id}.inputs.original.json"
        np = out_dir / f"{case_id}.inputs.named.json"
        op.write_text(json.dumps(original, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        np.write_text(json.dumps(named, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append({"case_id": case_id, "original": str(op), "named": str(np)})
    return {"cases": len(written), "written": written}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--refs",
        type=Path,
        default=Path("docs/examples/reference-27-inputs-with-publication-at.json"),
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = prepare(args.manifest, refs=args.refs, out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
