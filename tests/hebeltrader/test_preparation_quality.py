from test_backtest_report import add_recommendation

from scanner.hebeltrader.preparation_quality import assess_quality, group_quality


def test_overlapping_missing_and_invalid_target_is_one_finding(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        rec.stock_wkn = None
        rec.stock_currency = None
        rec.stock_stop1 = None
        rec.stock_target1 = None
        rec.stock_target2 = None
        rec.flags = [dict(code="invalid_value", field="stock_target2", page=1)]
        doc.pages = [dict(number=1, text="AKTIE: Kursziel 2 unklar")]
        rec.evidence = dict(stock_target2=[dict(page=1, raw="unklar", text="Kursziel 2 unklar")])
        findings = assess_quality(doc, rec)
    target = [f for f in findings if f["field"] == "stock_target2"]
    assert len(target) == 1
    assert target[0]["statuses"] == ["missing", "unverified"]
    assert target[0]["source_hints"][0]["page"] == 1
    assert target[0]["source_hints"][0]["quote"] == "Kursziel 2 unklar"
    grouped = group_quality(findings)
    assert len(grouped["documents"]) == 1
    assert grouped["summary"]["stock_target2"]["missing"] == 1
    assert grouped["summary"]["stock_target2"]["unverified"] == 1
    assert len(grouped["documents"][0]["findings"]) == 5


def test_wkn_is_sufficient_and_missing_field_uses_page_context(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        rec.stock_currency = "EUR"
        rec.evidence = dict(rec.evidence, stock_currency=[dict(page=1, raw="EUR")])
        rec.stock_target2 = None
        rec.evidence = {k: v for k, v in rec.evidence.items() if k != "stock_target2"}
        findings = assess_quality(doc, rec)
    assert [f["field"] for f in findings] == ["stock_target2"]
    assert findings[0]["source_hints"][0]["page"] == 1
    assert findings[0]["source_hints"][0]["source"] == "stock_section_context"
    assert findings[0]["current_value"] is None
