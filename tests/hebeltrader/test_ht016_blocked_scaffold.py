"""HT-016 Williams scaffold stays blocked and out of the corpus freeze."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("docs/examples/source-packets/ht-016-blocked")
MANIFEST = ROOT / "manifest.json"
PACKET = ROOT / "packets" / "HT-016.json"
META = ROOT / "packets" / "HT-016.meta.json"
INPUTS = ROOT / "HT-016.inputs.original.json"
CORPUS_MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")

CUTOFF = "2026-10-15T08:15:00+01:00"


def test_ht016_scaffold_issue_bound_awaiting_pdf():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    case = manifest["case"]
    assert case["case_id"] == "HT-016"
    assert case["status"] == "blocked_awaiting_pdf_stand"
    assert case["identification_freeze"] is False
    assert case["publication_issue"] == "191/26"
    assert case["publication_date"] == "2026-10-15"
    assert case["publication_at"] == CUTOFF
    assert case["publication_at_basis"] == "featured_date_plus_corpus_stand_0815_pdf_pending"
    assert case["research_cutoff"] == CUTOFF
    assert case["suspected_ticker"] == "WMB"
    assert len(case["issuers"]) >= 6
    assert case["issuers"][0]["ticker"] == "WMB"
    assert "Transco" in case["lead_needles"]
    assert "Northwest Pipeline" in case["lead_needles"]


def test_ht016_inputs_bind_191_26():
    inputs = json.loads(INPUTS.read_text(encoding="utf-8"))
    assert inputs["publication_issue"] == "191/26"
    assert inputs["publication_date"] == "2026-10-15"
    assert inputs["publication_at"] == CUTOFF
    assert "Stromhunger" in inputs["teaser_text"]
    assert inputs["advertised_return"] == "1453"


def test_ht016_packet_pit_safe_for_stand_2026_10_15():
    docs = json.loads(PACKET.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert docs[0]["ticker"] == "WMB"
    assert docs[0]["availability_evidence"]["basis"] == "sec_edgar_filing_date"
    text = docs[0]["text"]
    assert "Transco" in text or "transco" in text.casefold()
    assert "Northwest Pipeline" in text or "northwest pipeline" in text.casefold()
    tickers = [d["ticker"] for d in docs]
    assert tickers[0] == "WMB"
    assert set(tickers) <= {"WMB", "KMI", "OKE", "EPD", "ET", "LNG"}
    assert meta["documents"] == len(docs)
    cutoff_date = "2026-10-15"
    for row in meta["meta"]:
        assert row["filing_date"] <= cutoff_date, row
    for doc in docs:
        available = (doc.get("source_available_at") or doc.get("published_at") or "")[:10]
        assert available <= cutoff_date, doc.get("ticker")


def test_ht016_excluded_from_corpus_v1():
    corpus = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    assert "HT-016" not in {c["case_id"] for c in corpus["cases"]}
