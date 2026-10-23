"""Synthetic JNJ-shaped inputs. No fixture price or identity is a real observation."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from test_backtest_report import add_recommendation
from test_historical_identity import source
from test_rules_v16 import spec_for

from scanner.hebeltrader.eodhd import EodhdClient, canonical, sha
from scanner.hebeltrader.eodhd_adapter import prepare_snapshot
from scanner.hebeltrader.historical_identity import PROOF_FIELDS

CLOCK = datetime(2026, 10, 22, 12, tzinfo=UTC)
END = date(2026, 1, 16)


def fixture(
    sessions,
    tmp_path,
    monkeypatch,
    *,
    dividend=False,
    missing=False,
    scenario="targets",
    split=False,
):
    zone = ZoneInfo("America/New_York")
    sessions_csv = ["timestamp,end_timestamp"]
    prices = []
    day = date(2025, 8, 4)
    holidays = {date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25), date(2026, 1, 1)}
    while day <= END:
        if day.weekday() < 5 and day not in holidays:
            close = time(13) if day in {date(2025, 11, 28), date(2025, 12, 24)} else time(16)
            opened = datetime.combine(day, time(9, 30), zone)
            closed = datetime.combine(day, close, zone)
            sessions_csv.append(f"{opened.isoformat()},{closed.isoformat()}")
            high, low, closing = (
                (191, 173, 190)
                if day == date(2025, 8, 11) and scenario == "targets"
                else (180, 170, 175)
            )
            opening = 180 if day == date(2025, 8, 11) and scenario == "targets" else 172
            if day == date(2025, 8, 12) and scenario == "targets":
                opening, high, low, closing = 195, 217, 191, 216
            if scenario == "collision" and day == date(2025, 8, 6):
                high, low = 195, 155
            if scenario == "gap" and day == date(2025, 8, 7):
                opening, high, low, closing = 150, 155, 145, 151
            if scenario == "loss20":
                closing = 171
            if not missing or day != date(2025, 8, 7):
                prices.append(
                    dict(
                        date=str(day),
                        open=opening,
                        high=high,
                        low=low,
                        close=closing,
                        volume=100,
                        adjusted_close=1,
                    )
                )
        day += timedelta(days=1)
    calendar = tmp_path / "sessions.csv"
    calendar.write_text("\n".join(sessions_csv) + "\n")
    payloads = {
        "eod": prices,
        "splits": [dict(date="2025-08-15", split="2/1")] if split else [],
        "div": [dict(date="2025-08-15", value=1.23, currency="USD")] if dividend else [],
    }
    monkeypatch.setenv("EODHD_API_TOKEN", "synthetic-test-value")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=payloads[r.url.path.split("/")[2]])
        )
    )
    collector = EodhdClient(
        tmp_path / "raw",
        client=client,
        allow_network=True,
        authorize_usage=True,
        max_requests=3,
        now=lambda: CLOCK,
        sleeper=lambda _: None,
    )
    raw_manifests = {
        e: collector.fetch(e, "JNJ.US", start="2025-08-04", end=str(END))["manifest_sha256"]
        for e in payloads
    }
    spec = dict(
        wkn="853260",
        isin="US4781601046",
        symbol="JNJ.US",
        venue="XNYS",
        currency="USD",
        timezone="America/New_York",
        identity_status="verified",
        identity_reference="https://issuer.example/synthetic-2025-proof",
        identity_evidence="SYNTHETIC identity proof",
        identity_reviewed_by="Synthetic reviewer",
        identity_reviewed_at=CLOCK.isoformat(),
        identity_valid_from="2025-08-04T00:00:00-04:00",
        identity_valid_until="2026-01-16T23:59:59-05:00",
        coverage_start="2025-08-04T00:00:00-04:00",
        coverage_end="2026-01-16T23:59:59-05:00",
        calendar_reference="https://exchange.example/synthetic-sessions",
    )
    record = source(
        {k: spec[k] for k in PROOF_FIELDS if k != "asset_class"} | {"asset_class": "stock"}
    )
    record["query_wkn"] = "853260"
    bundle = prepare_snapshot(
        tmp_path / "raw",
        tmp_path / "data",
        records=raw_manifests,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    approved = dict(
        bundle["spec"],
        asset_class="stock",
        review_evidence={
            k: dict(payload_sha256=record["payload_sha256"], pointer="/" + k) for k in PROOF_FIELDS
        },
    )
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        doc.publication_date = date(2025, 8, 5)
        rec.stock_name = "Johnson & Johnson"
        rec.stock_wkn = "853260"
        rec.stock_currency = "USD"
        rec.stock_price = rec.stock_stop2 = Decimal("171.04")
        rec.stock_target1, rec.stock_target2, rec.stock_stop1 = 190, 216, 160
        rec.derivative_wkn, rec.derivative_currency = "HS5RMP", "EUR"
        rec.entry_price, rec.derivative_target1, rec.derivative_target2 = (
            Decimal("0.17"),
            Decimal("0.70"),
            Decimal("2.30"),
        )
        rec.maturity_date = END
        rules = spec_for(doc, rec)
        rules["reviewed_at"] = CLOCK.isoformat()
        header = "05.08.2025 #130/2025"
        doc.pages[0]["text"] += "\n" + header
        doc.metadata_evidence = [dict(page=3, raw=header)]
        # Deliberately synthetic, source-bound price evidence for gate testing.
        rec.evidence = {
            k: [dict(page=3, raw=f"SYNTHETIC {k} {getattr(rec, k)}")]
            for k in (
                "stock_price",
                "stock_target1",
                "stock_target2",
                "stock_stop1",
                "stock_stop2",
                "stock_currency",
            )
        }
        key = f"{doc.sha256}:1"
        document_sha = doc.sha256
    source_bytes = b"SYNTHETIC complete session source; not a real exchange calendar"
    (tmp_path / "raw" / "calendar-source.txt").write_bytes(source_bytes)
    calendar_review = dict(
        status="approved",
        reviewer="Synthetic reviewer",
        reviewed_at=CLOCK.isoformat(),
        source_reference="https://exchange.example/synthetic-calendar",
        license="synthetic fixture",
        source_file="calendar-source.txt",
        source_sha256=sha(source_bytes),
        source_retrieved_at=CLOCK.isoformat(),
        calendar_sha256=sha(calendar.read_bytes()),
        venue="XNYS",
        timezone="America/New_York",
        completeness_reviewed=True,
        coverage_start=spec["coverage_start"],
        coverage_end=spec["coverage_end"],
    )
    projection = dict(
        status="approved",
        reviewer="Synthetic reviewer",
        reviewed_at=CLOCK.isoformat(),
        document_sha=document_sha,
        ordinal=1,
        rule_spec_sha256=sha(canonical(rules)),
        original_rule_scope="derivative",
        model_scope="hypothetical_stock",
        additional_document_rules_reviewed=True,
        scope_decision="Synthetic limited four-rule model, excludes any other original policy",
    )
    actions = dict(
        status="approved",
        reviewer="Synthetic reviewer",
        reviewed_at=CLOCK.isoformat(),
        policy="raw_price_only_exclude_cash_dividends",
        splits_policy="block",
        dividend_cashflows_included=False,
        raw_manifests={k: raw_manifests[k] for k in ("splits", "div")},
    )
    return dict(
        run_at=CLOCK,
        end_date=END,
        records=[record],
        mapping={"853260": approved},
        rules={key: rules},
        bundles=[bundle],
        market_root=tmp_path / "data",
        raw_cache=tmp_path / "raw",
        calendar_review=calendar_review,
        projection_review=projection,
        action_review=actions,
        synthetic=True,
        document_sha=document_sha,
    )
