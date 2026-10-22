from copy import deepcopy

from test_backtest_report import AS_OF, add_recommendation

from scanner.hebeltrader.backtest_report import document_rules


def spec_for(doc, rec):
    quote = (
        "Bei Ziel 1 die Hälfte verkaufen. Stopp auf Einstieg. "
        "Bei Ziel 2 die zweite Hälfte verkaufen. "
        "Nach 20 Kalendertagen im Minus schließen."
    )
    doc.pages = [
        dict(number=3, text=quote, regions=[[dict(page=3, text=quote, bbox=[390, 100, 550, 300])]])
    ]
    return dict(
        rule_version="1.6",
        document_sha=doc.sha256,
        ordinal=rec.ordinal,
        instrument_scope="stock",
        review_status="approved",
        requires_manual_review=False,
        reviewer="Synthetic reviewer",
        reviewed_at=AS_OF.isoformat(),
        partial_fraction=0.5,
        after_target1="entry",
        target2_sale=dict(fraction=0.5, trigger="target2"),
        conditional_loss_exit=dict(
            days=20,
            unit="calendar_days",
            condition="position_in_loss",
            threshold="at_least",
            loss_basis="total_position",
            evaluation="completed_close",
            execution="next_session_open",
        ),
        evidence=[
            dict(
                page=3,
                region=0,
                quote=quote,
                fields=[
                    "partial_fraction",
                    "after_target1",
                    "target2_sale",
                    "conditional_loss_exit",
                ],
            )
        ],
    )


def test_complete_reviewed_v16_rules_and_region_quote_are_accepted(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        spec = spec_for(doc, rec)
        doc.pages[0]["text"] = "interleaved unrelated column"
        rule, audit, issue = document_rules(doc, rec, spec, AS_OF)
        assert issue is None
        assert rule.version == "1.6" and rule.loss_after_days == 20
        assert audit["research_assumption"] is False


def test_unknown_unit_pending_or_missing_rule_cannot_pass(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        spec = spec_for(doc, rec)
        for field, value in [
            ("requires_manual_review", True),
            ("target2_sale", None),
            ("instrument_scope", "derivative"),
        ]:
            changed = deepcopy(spec)
            changed[field] = value
            assert document_rules(doc, rec, changed, AS_OF)[0] is None
        spec["conditional_loss_exit"]["unit"] = None
        assert document_rules(doc, rec, spec, AS_OF)[0] is None


def test_ambiguous_days_require_documented_research_interpretation(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        spec = spec_for(doc, rec)
        doc.pages[0]["text"] = doc.pages[0]["text"].replace("Kalendertagen", "Tagen")
        doc.pages[0]["regions"][0][0]["text"] = doc.pages[0]["text"]
        spec["evidence"][0]["quote"] = doc.pages[0]["text"]
        assert document_rules(doc, rec, spec, AS_OF)[0] is None
        spec["time_unit_interpretation"] = (
            "Synthetic manual research assumption: elapsed calendar days; "
            "not asserted as original meaning"
        )
        rule, audit, issue = document_rules(doc, rec, spec, AS_OF)
        assert issue is None and audit["research_assumption"] is True
