"""HT-016 Williams scaffold stays blocked and out of the corpus freeze."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("docs/examples/source-packets/ht-016-blocked")
MANIFEST = ROOT / "manifest.json"
PACKET = ROOT / "packets" / "HT-016.json"
META = ROOT / "packets" / "HT-016.meta.json"
CORPUS_MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")


def test_ht016_scaffold_present_and_blocked():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    case = manifest["case"]
    assert case["case_id"] == "HT-016"
    assert case["status"] == "blocked_no_publication_at"
    assert case["identification_freeze"] is False
    assert case["publication_at"] is None
    assert case["publication_issue"] is None
    assert case["suspected_ticker"] == "WMB"
    assert len(case["issuers"]) >= 6
    assert case["issuers"][0]["ticker"] == "WMB"
    assert "Transco" in case["lead_needles"]
    assert "Northwest Pipeline" in case["lead_needles"]


def test_ht016_packet_has_lead_and_peers_with_sec_binding():
    docs = json.loads(PACKET.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert len(docs) == 6
    assert docs[0]["ticker"] == "WMB"
    assert docs[0]["availability_evidence"]["basis"] == "sec_edgar_filing_date"
    text = docs[0]["text"]
    assert "Transco" in text or "transco" in text.casefold()
    assert "Northwest Pipeline" in text or "northwest pipeline" in text.casefold()
    tickers = [d["ticker"] for d in docs]
    assert tickers == ["WMB", "KMI", "OKE", "EPD", "ET", "LNG"]
    assert meta["documents"] == 6
    assert meta["meta"][0]["form"] == "10-Q"


def test_ht016_excluded_from_corpus_v1():
    corpus = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    assert "HT-016" not in {c["case_id"] for c in corpus["cases"]}
