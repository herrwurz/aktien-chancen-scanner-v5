import csv
import hashlib
import json

import pytest
from test_backtest_report import AS_OF, add_recommendation

from scanner.hebeltrader.backtest_report import document_rules
from scanner.hebeltrader.preparation import build_preparation
from scanner.hebeltrader.preparation_cli import write_bundle


def test_118_readonly_reproducible_bundle(sessions, tmp_path):
    with sessions.begin() as session:
        for index in range(118):
            add_recommendation(session, index)
    with sessions() as session:
        first = build_preparation(session, run_at=AS_OF)
        second = build_preparation(session, run_at=AS_OF)
        assert not session.dirty and not session.new and not session.deleted
    assert first == second
    assert first["summary"]["recommendations"] == 118
    assert first["summary"]["original_sha_valid"] == 118
    assert first["summary"]["stock_wkn_occurrences"] == 118
    assert first["summary"]["unique_stock_wkn"] == 1
    assert first["summary"]["verified_identities"] == 0
    assert all(not r["training_eligible"] for r in first["results"])
    paths = write_bundle(tmp_path / "a", first)
    replay = write_bundle(tmp_path / "b", second)
    assert [p.read_bytes() for p in paths] == [p.read_bytes() for p in replay]
    with paths[5].open() as stream:
        assert [json.loads(r["record_json"]) for r in csv.DictReader(stream)] == first["results"]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    with pytest.raises(FileExistsError):
        write_bundle(tmp_path / "a", first)
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]


def test_pending_rule_cannot_be_used_even_with_reviewer(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        spec = dict(
            document_sha=doc.sha256,
            ordinal=rec.ordinal,
            reviewer="manual",
            reviewed_at=AS_OF.isoformat(),
            partial_fraction="0.5",
            after_target1="entry",
            evidence=[
                dict(
                    page=1, quote=doc.pages[0]["text"], fields=["partial_fraction", "after_target1"]
                )
            ],
        )
        assert document_rules(doc, rec, spec, AS_OF)[2] is None
        for flag in ({"requires_manual_review": True}, {"review_status": "pending"}):
            assert (
                document_rules(doc, rec, dict(spec, **flag), AS_OF)[2] == "unverified_rule_evidence"
            )


@pytest.mark.parametrize("kind", ["conditional_loss_exit", "target2_sale"])
def test_new_rule_types_cannot_be_silently_ignored_by_backtest(sessions, kind):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        spec = dict(
            document_sha=doc.sha256,
            ordinal=rec.ordinal,
            reviewer="manual",
            reviewed_at=AS_OF.isoformat(),
            partial_fraction="0.5",
            after_target1="entry",
            evidence=[
                dict(
                    page=1, quote=doc.pages[0]["text"], fields=["partial_fraction", "after_target1"]
                )
            ],
            **{kind: dict(days=20, unit=None, condition="position_in_loss")},
        )
        assert document_rules(doc, rec, spec, AS_OF)[2] == "unverified_rule_evidence"
