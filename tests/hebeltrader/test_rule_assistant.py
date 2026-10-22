from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

from scanner.hebeltrader.rule_assistant import suggest_rules


def suggest(text, **changes):
    doc = SimpleNamespace(
        sha256=sha256(b"pdf").hexdigest(), original_pdf=b"pdf", pages=[{"number": 1, "text": text}]
    )
    rec = SimpleNamespace(
        document_sha=doc.sha256, ordinal=1, evidence={}, source_commentary=None, product_type="Call"
    )
    for key, value in changes.items():
        setattr(rec, key, value)
    return suggest_rules(doc, rec, run_at=datetime(2026, 1, 1, tzinfo=UTC))


def test_explicit_rules_are_pending_and_literal():
    result = suggest(
        "Bei Ziel 1 verkaufen wir die Hälfte der Position. "
        "Nach Ziel 1 ziehen wir den Stopp auf Einstand. "
        "Nach 20 Handelstagen schließen wir die Position."
    )
    draft = result["rules_json_candidate"]
    assert draft["partial_fraction"] == 0.5
    assert draft["after_target1"] == "entry"
    assert draft["exit_after"] == {"days": 20, "unit": "trading_sessions"}
    assert draft["reviewer"] is None and draft["review_status"] == "pending"
    assert all(c["evidence"] for c in result["candidates"])


def test_ambiguous_and_conditional_days_never_become_expiry():
    for text in (
        "Nach 20 Tagen schließen wir die Position.",
        "Nach 20 Kalendertagen ohne Ziel 1 schließen wir die Position.",
    ):
        result = suggest(text)
        assert "exit_after" not in result["rules_json_candidate"]
        assert result["candidates"][0]["value"]["status"] == "unknown"


def test_conflicts_preserve_quotes_but_withhold_field():
    result = suggest("Nach Ziel 1 Stopp auf Einstand. Nach Ziel 1 Stopp unverändert.")
    assert "after_target1" not in result["rules_json_candidate"]
    assert len(result["candidates"]) == 2
    assert "contradictory_after_target1" in result["review_hints"]


def test_sha_mismatch_rejects_all_detection():
    result = suggest("Bei Ziel 1 verkaufen wir 50%.", document_sha="wrong")
    assert result["candidates"] == []
    assert "original_sha_mismatch" in result["review_hints"]


def test_unbound_generic_scope_is_never_verified():
    result = suggest("Bei Ziel 1 verkaufen wir 50%.")
    assert result["candidates"][0]["evidence"][0]["scope"] == "document_unverified"


def test_targets_require_typed_value_and_original_evidence():
    result = suggest(
        "Ziel 1: 12,50 EUR",
        derivative_target1=12.5,
        evidence={
            "derivative_target1": [{"page": 1, "text": "Ziel 1: 12,50 EUR", "bbox": [0, 0, 1, 1]}]
        },
    )
    target = next(c for c in result["candidates"] if c["kind"] == "derivative_target1")
    assert target["value"] == "12.5"
    assert target["evidence"][0]["bbox"] == [0, 0, 1, 1]


def test_hyphenated_duration_units():
    for word, unit in [("Handelstage", "trading_sessions"), ("Kalendertage", "calendar_days")]:
        result = suggest(f"Nach 20-{word} schließen wir die Position.")
        assert result["rules_json_candidate"]["exit_after"] == {"days": 20, "unit": unit}
        assert result["rules_json_candidate"]["review_status"] == "pending"


def test_partial_without_target1_trigger_remains_unknown():
    result = suggest("Wir verkaufen 50% der Position.")
    candidate = result["candidates"][0]
    assert candidate["value"]["status"] == "unknown"
    assert "partial_trigger_unverified" in candidate["review_hints"]
    assert "partial_fraction" not in result["rules_json_candidate"]


def test_target_evidence_can_match_authentic_region_lines():
    doc = SimpleNamespace(
        sha256=sha256(b"pdf").hexdigest(),
        original_pdf=b"pdf",
        pages=[
            {
                "number": 1,
                "text": "Ziel 1: Andere Spalte 12,50 EUR",
                "regions": [[{"text": "Ziel 1:"}, {"text": "12,50 EUR"}]],
            }
        ],
    )
    rec = SimpleNamespace(
        document_sha=doc.sha256,
        ordinal=1,
        derivative_target1=12.5,
        evidence={
            "derivative_target1": [{"page": 1, "text": "Ziel 1: 12,50 EUR", "bbox": [0, 0, 1, 1]}]
        },
    )
    result = suggest_rules(doc, rec, run_at=datetime(2026, 1, 1, tzinfo=UTC))
    target = result["candidates"][0]
    assert target["evidence"][0]["quote"] == "Ziel 1: 12,50 EUR"
    assert target["evidence"][0]["bbox"] == [0, 0, 1, 1]
    assert result["rules_json_candidate"]["review_status"] == "pending"
