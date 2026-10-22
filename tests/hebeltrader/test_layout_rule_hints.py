from hashlib import sha256
from types import SimpleNamespace

from scanner.hebeltrader.rule_assistant import suggest_layout_rule_hints

TEXT = (
    "Sobald das erste Kursziel erreicht wurde, sollten Anleger die Hälfte ihres Derivats ver- "
    "kaufen, um erste Gewinne zu realisieren. Der neue Stoppkurs sollte dann auf den Wert des "
    "Einstiegskurses angehoben werden. Eine Position, die nach einer Haltedauer von "
    "20 Tagen oder länger im Minus notiert, wird geschlossen."
)


def test_original_partial_stop_and_20_day_loss_rule_are_cited_but_pending():
    doc = SimpleNamespace(
        sha256=sha256(b"fixture").hexdigest(),
        original_pdf=b"fixture",
        pages=[dict(number=3, regions=[[dict(page=3, text=TEXT, bbox=[392, 332, 552, 473])]])],
    )
    rec = SimpleNamespace(document_sha=doc.sha256, ordinal=1)
    hints = suggest_layout_rule_hints(doc, rec)
    assert {c["kind"] for c in hints} == {
        "partial_fraction",
        "after_target1",
        "conditional_loss_exit",
    }
    for hint in hints:
        assert hint["evidence"][0]["quote"] in TEXT
        assert hint["evidence"][0]["page"] == 3
        if hint["kind"] != "conditional_loss_exit":
            assert hint["instrument_scope"] == "derivative_mentioned"
        assert hint["requires_manual_review"] is True
    loss = next(c for c in hints if c["kind"] == "conditional_loss_exit")
    assert loss["value"] == dict(
        days=20, unit=None, condition="position_in_loss", threshold="at_least"
    )
    assert "time_unit_unverified" in loss["review_hints"]
    doc.original_pdf = b"changed"
    assert suggest_layout_rule_hints(doc, rec) == []


def test_representative_six_original_column_excerpts():
    import json
    from pathlib import Path

    cases = json.loads(
        (Path(__file__).parents[1] / "fixtures/hebeltrader/v14-rules-sample.json").read_text()
    )["cases"]
    for case in cases:
        data = json.dumps(case, sort_keys=True).encode()
        digest = sha256(data).hexdigest()
        doc = SimpleNamespace(sha256=digest, original_pdf=data, pages=case["pages"])
        rec = SimpleNamespace(document_sha=digest, ordinal=1)
        hints = suggest_layout_rule_hints(doc, rec)
        assert {"partial_fraction", "after_target1"} <= {h["kind"] for h in hints}, case[
            "source_sha"
        ]
        for hint in hints:
            assert hint["evidence"][0]["document_sha"] == digest
            assert hint["requires_manual_review"] is True


def test_target2_sale_is_separate_from_conditional_time_exit():
    text = (
        "Mit Erreichen von Kursziel 2 kann die zweite Hälfte des Derivats verkauft werden. "
        "Eine Position, die nach einer Haltedauer von 20 Tagen oder länger im Minus "
        "notiert, wird geschlossen."
    )
    doc = SimpleNamespace(
        sha256=sha256(b"fixture").hexdigest(),
        original_pdf=b"fixture",
        pages=[dict(number=3, regions=[[dict(page=3, text=text, bbox=[392, 332, 552, 473])]])],
    )
    rec = SimpleNamespace(document_sha=doc.sha256, ordinal=1)
    hints = suggest_layout_rule_hints(doc, rec)
    assert {h["kind"] for h in hints} == {"target2_sale", "conditional_loss_exit"}
    assert all(h["kind"] != "exit_after" for h in hints)


def test_neighbor_column_cannot_supply_missing_sale_or_loss_condition():
    doc = SimpleNamespace(
        sha256=sha256(b"fixture").hexdigest(),
        original_pdf=b"fixture",
        pages=[
            dict(
                number=3,
                regions=[
                    [
                        dict(
                            page=3,
                            text="Sobald das erste Kursziel erreicht wurde.",
                            bbox=[40, 100, 300, 110],
                        )
                    ],
                    [
                        dict(
                            page=3,
                            text="Die Hälfte verkaufen. Nach 20 Tagen schließen.",
                            bbox=[390, 100, 550, 110],
                        )
                    ],
                ],
            )
        ],
    )
    rec = SimpleNamespace(document_sha=doc.sha256, ordinal=1)
    assert suggest_layout_rule_hints(doc, rec) == []


def test_negated_loss_exit_does_not_become_a_rule():
    doc = SimpleNamespace(
        sha256=sha256(b"fixture").hexdigest(),
        original_pdf=b"fixture",
        pages=[
            dict(
                number=3,
                regions=[
                    [
                        dict(
                            page=3,
                            text=(
                                "Eine Position, die nach 20 Tagen nicht im Minus notiert, "
                                "wird geschlossen."
                            ),
                            bbox=[392, 332, 552, 473],
                        )
                    ]
                ],
            )
        ],
    )
    rec = SimpleNamespace(document_sha=doc.sha256, ordinal=1)
    assert suggest_layout_rule_hints(doc, rec) == []


def test_representative_sample_adds_six_distinct_documents_beyond_problem_cases():
    import json
    from pathlib import Path

    folder = Path(__file__).parents[1] / "fixtures/hebeltrader"
    problems = json.loads((folder / "v14-audit-five.json").read_text())["cases"]
    sample = json.loads((folder / "v14-rules-sample.json").read_text())["cases"]
    assert len({c["source_sha"] for c in sample}) == 6
    assert not {c["source_sha"] for c in problems} & {c["source_sha"] for c in sample}


def test_conflicting_stock_and_derivative_stops_remain_separate_candidates():
    from datetime import UTC, datetime

    from scanner.hebeltrader.rule_assistant import suggest_rules

    texts = [
        "Sobald das erste Kursziel erreicht wurde, die Hälfte des Derivats verkaufen. "
        "Der Stopp sollte dann auf den Einstiegskurs angehoben werden.",
        "Sobald das erste Kursziel erreicht wurde, die Hälfte der Aktien verkaufen. "
        "Der Stopp sollte dann auf den Wert des ersten Kursziels angehoben werden.",
    ]
    doc = SimpleNamespace(
        sha256=sha256(b"fixture").hexdigest(),
        original_pdf=b"fixture",
        pages=[
            dict(
                number=3,
                text=" ".join(texts),
                regions=[
                    [dict(text=t, page=3, bbox=[40 + i * 350, 100, 300 + i * 350, 200])]
                    for i, t in enumerate(texts)
                ],
            )
        ],
    )
    rec = SimpleNamespace(document_sha=doc.sha256, ordinal=1, evidence={})
    result = suggest_rules(doc, rec, run_at=datetime(2026, 10, 22, tzinfo=UTC))
    assert "after_target1" not in result["rules_json_candidate"]
    assert "contradictory_layout_after_target1" in result["review_hints"]
    assert {
        c["value"] for c in result["layout_rule_candidates"] if c["kind"] == "after_target1"
    } == {"entry", "target1"}
