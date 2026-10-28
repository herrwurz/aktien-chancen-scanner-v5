"""Safety boundaries of the forward-only SEC pilot."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from scanner.live_pilot import Journal, assess_event, select_universe
from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def test_journal_is_append_only_and_chain_detects_changes(tmp_path):
    journal = Journal(tmp_path / "audit.db")
    first = journal.append("scan_started", {"at": NOW.isoformat()})
    journal.append("decision", {"event_id": "sec:one", "status": "BEOBACHTEN"})
    assert journal.verify() == 2
    assert journal.records()[0]["sha256"] == first
    with sqlite3.connect(journal.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE audit SET payload='{}'")
        db.execute("DROP TRIGGER audit_no_update")
        db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
    with pytest.raises(ValueError, match="integrity"):
        journal.verify()


def test_newness_and_reassessment_are_separate(tmp_path):
    journal = Journal(tmp_path / "audit.db")
    journal.append("event_discovered", {"event_id": "sec:one"})
    assert journal.discovered("sec:one")
    assert not journal.discovered("sec:two")
    journal.append("decision", {"event_id": "sec:one", "status": "NICHT VERFÜGBAR"})
    journal.append("decision", {"event_id": "sec:one", "status": "BEOBACHTEN"})
    assert len(journal.records()) == 3


def identity(cik, ticker, exchange="Nasdaq"):
    return AssetIdentity(
        asset_type="stock",
        name=ticker,
        cik=cik,
        ticker=ticker,
        exchange=exchange,
        country="US",
        source_id="test",
        retrieved_at=NOW,
    )


def test_universe_excludes_ambiguous_cik_and_is_independent_of_archive():
    assets = [identity(str(i), f"T{i}") for i in range(110)]
    assets.append(identity("1", "DUP"))
    selected, excluded = select_universe(assets, 100)
    assert len(selected) == 100
    assert "1" not in {a.cik for a in selected}
    assert any(row["reason"] == "ambiguous_listing" for row in excluded)
    assert [a.cik for a in selected] == [a.cik for a in select_universe(reversed(assets), 100)[0]]


def event():
    return {
        "event_id": "sec:one",
        "published_at": (NOW - timedelta(days=2)).isoformat(),
        "retrieved_at": NOW.isoformat(),
        "form": "8-K",
        "items": "2.02",
        "document_status": "archived",
        "text_hints": ["earnings"],
        "identity": {},
    }


def test_no_prices_never_emits_buy():
    result = assess_event(event(), [], now=NOW)
    assert result["status"] == "NICHT VERFÜGBAR"
    assert result["entry_limit"] is None
    assert result["market_reaction"]["status"] == "unavailable"


def bars():
    return [
        {
            "date": f"2026-10-{day:02}T00:00:00Z",
            "adjClose": 100 + day,
            "close": 100 + day,
            "volume": 10000,
        }
        for day in range(1, 28)
    ]


def test_eod_reaction_is_real_but_never_executable():
    result = assess_event(event(), bars(), now=NOW)
    assert result["market_reaction"]["status"] == "observed_eod"
    assert result["status"] == "BEOBACHTEN"
    assert result["current_price"] is None
    assert result["flatex_status"] == "unverified"
    assert result["net_crv"] is None


def test_pre_publication_prices_are_not_a_reaction():
    result = assess_event(event(), bars()[:5], now=NOW)
    assert result["market_reaction"]["status"] == "unavailable"
    assert "post_publication_price_missing" in result["reasons"]


def test_future_publication_is_rejected():
    value = event() | {"published_at": (NOW + timedelta(hours=1)).isoformat()}
    with pytest.raises(ValueError, match="future"):
        assess_event(value, bars(), now=NOW)


def test_dilution_is_a_risk_not_positive_catalyst():
    result = assess_event(event() | {"items": "3.02"}, bars(), now=NOW)
    assert result["status"] == "ABLEHNEN"
    assert "dilution_risk" in result["reasons"]


def test_missing_timezone_fails_closed():
    with pytest.raises(ValueError, match="timezone"):
        assess_event(event() | {"published_at": "2026-10-26T10:00:00"}, bars(), now=NOW)


def test_export_is_valid_json(tmp_path):
    journal = Journal(tmp_path / "audit.db")
    journal.append("scan_started", {"at": NOW.isoformat()})
    assert json.loads(json.dumps(journal.records()))[0]["kind"] == "scan_started"


def mock_sources(monkeypatch, repeat=False):
    import httpx

    import scanner.live_pilot as pilot

    monkeypatch.setenv("SEC_USER_AGENT", "test test@example.invalid")
    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)
    monkeypatch.setattr(pilot, "clock", lambda: NOW)
    monkeypatch.setattr(pilot.time, "sleep", lambda _: None)
    attempts = []

    def handle(request):
        attempts.append(str(request.url))
        if "company_tickers" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "fields": ["cik", "name", "ticker", "exchange"],
                    "data": [[i, f"Company {i}", f"T{i}", "Nasdaq"] for i in range(1, 101)],
                },
            )
        if "/submissions/" in request.url.path:
            cik = int(request.url.path.split("CIK")[1].split(".")[0])
            return httpx.Response(
                200,
                json={
                    "filings": {
                        "recent": {
                            "accessionNumber": [f"{cik:010d}-26-000001"],
                            "filingDate": ["2026-10-26"],
                            "acceptanceDateTime": ["2026-10-26T13:00:00Z"],
                            "form": ["8-K"],
                            "items": ["2.02"],
                            "primaryDocument": ["release.htm"],
                        }
                    }
                },
            )
        return httpx.Response(200, text="<html>Quarterly results</html>")

    base_handle = handle

    def handle(request):
        response = base_handle(request)
        if repeat and "/submissions/" in request.url.path:
            payload = response.json()
            recent = payload["filings"]["recent"]
            for key, values in recent.items():
                values.append(
                    values[0] if key != "accessionNumber" else values[0].replace("000001", "000002")
                )
            return httpx.Response(200, json=payload)
        return response

    original = pilot.BoundedHTTP

    def factory(*args, **kwargs):
        instance = original(*args, **kwargs)
        instance.client.close()
        instance.client = httpx.Client(transport=httpx.MockTransport(handle))
        return instance

    monkeypatch.setattr(pilot, "BoundedHTTP", factory)
    return attempts


def test_bounded_end_to_end_discovers_all_before_evaluation_budget(tmp_path, monkeypatch):
    import scanner.live_pilot as pilot

    attempts = mock_sources(monkeypatch)
    summary = pilot.run_scan(tmp_path, max_events=2)
    assert summary["checked_issuers"] == 100
    assert summary["new_events"] == 100
    assert summary["evaluated_events"] == 2
    journal = Journal(tmp_path / "audit.db")
    decisions = [row["payload"] for row in journal.records() if row["kind"] == "decision"]
    assert len(decisions) == 2
    assert all(row["status"] == "NICHT VERFÜGBAR" for row in decisions)
    again = pilot.run_scan(tmp_path, max_events=2)
    assert again["new_events"] == 0
    # A fresh run must poll all submissions instead of replaying an eternal cache.
    assert sum("/submissions/" in url for url in attempts) == 200


def test_blocked_run_persists_exact_missing_configuration(tmp_path, monkeypatch):
    from scanner.live_pilot import run_scan

    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    result = run_scan(tmp_path)
    assert result["status"] == "blocked"
    assert result["errors"] == ["SEC_USER_AGENT_with_contact_email_required"]
    assert Journal(tmp_path / "audit.db").records()[-1]["kind"] == "scan_finished"


def test_interrupted_run_is_preserved_on_restart(tmp_path, monkeypatch):
    from scanner.live_pilot import run_scan

    journal = Journal(tmp_path / "audit.db")
    journal.append("scan_started", {"run_id": "interrupted"})
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    run_scan(tmp_path)
    assert any(
        row["kind"] == "scan_interrupted" and row["payload"]["run_id"] == "interrupted"
        for row in journal.records()
    )


def test_source_429_stops_shared_budget_and_records_timestamp(tmp_path):
    import httpx

    from scanner.live_pilot import BoundedHTTP

    journal = Journal(tmp_path / "audit.db")
    http = BoundedHTTP(journal, "test", limit=10, seconds=5)
    http.client.close()
    http.client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429)))
    try:
        with pytest.raises(ValueError, match="rate_limited"):
            http.get("https://data.sec.gov/test")
        assert http.remaining == 0
        row = journal.records()[-1]["payload"]
        assert row["http_status"] == 429 and row["retrieved_at"]
    finally:
        http.client.close()


def test_read_only_api_exports_decisions_and_integrity(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from scanner.live_pilot import create_app

    monkeypatch.setenv("LIVE_PILOT_ROOT", str(tmp_path))
    journal = Journal(tmp_path / "audit.db")
    journal.append("decision", {"event_id": "sec:one", "status": "BEOBACHTEN"})
    with TestClient(create_app()) as client:
        response = client.get("/decisions")
        assert response.status_code == 200
        assert response.json()["records"][0]["payload"]["status"] == "BEOBACHTEN"
        assert client.get("/health").json()["verified_rows"] == 1
        assert client.post("/decisions").status_code == 405
    assert journal.verify() == 1


def test_read_only_journal_never_creates_a_missing_database(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        Journal(tmp_path / "missing.db", read_only=True)
    assert not (tmp_path / "missing.db").exists()


def test_infeasible_universe_budget_is_rejected_before_network(tmp_path):
    from scanner.live_pilot import run_scan

    with pytest.raises(ValueError, match="budget"):
        run_scan(tmp_path, count=200, max_requests=150)


def test_deadline_expiring_during_throttle_never_sends_request(tmp_path, monkeypatch):
    import httpx

    import scanner.live_pilot as pilot

    journal = Journal(tmp_path / "audit.db")
    http = pilot.BoundedHTTP(journal, "test", limit=10, seconds=5)
    http.client.close()
    sent = []
    http.client = httpx.Client(
        transport=httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200))
    )
    monkeypatch.setattr(pilot.time, "sleep", lambda _: setattr(http, "deadline", 0))
    try:
        with pytest.raises(ValueError, match="duration"):
            http.get("https://data.sec.gov/test")
        assert sent == []
    finally:
        http.client.close()


def test_repeated_issuer_events_reuse_successful_prices_without_quota_reservation(
    tmp_path, monkeypatch
):
    import scanner.live_pilot as pilot

    mock_sources(monkeypatch, repeat=True)
    monkeypatch.setenv("TIINGO_API_TOKEN", "test-only-token")
    reservations = []
    monkeypatch.setattr(
        pilot.TiingoQuotaLedger, "reserve", lambda self, **kw: reservations.append(kw["symbols"])
    )
    monkeypatch.setattr(
        pilot.TiingoClient,
        "fetch",
        lambda self, symbol, **kw: {
            "payload": [],
            "retrieved_at": NOW.isoformat(),
            "raw_sha256": "a" * 64,
            "source_reference": "https://api.tiingo.com/",
        },
    )
    result = pilot.run_scan(tmp_path, max_events=2, authorize_tiingo=True)
    assert result["evaluated_events"] == 2
    assert len(reservations) == 2  # SPY and one issuer, not one reservation per event.


def test_malformed_market_response_still_gets_a_durable_decision(tmp_path, monkeypatch):
    import scanner.live_pilot as pilot

    mock_sources(monkeypatch)
    monkeypatch.setenv("TIINGO_API_TOKEN", "test-only-token")
    monkeypatch.setattr(pilot.TiingoQuotaLedger, "reserve", lambda self, **kw: None)
    monkeypatch.setattr(
        pilot.TiingoClient,
        "fetch",
        lambda self, symbol, **kw: {
            "payload": [{"unexpected": True}],
            "retrieved_at": NOW.isoformat(),
            "raw_sha256": "b" * 64,
            "source_reference": "https://api.tiingo.com/",
        },
    )
    result = pilot.run_scan(tmp_path, max_events=1, authorize_tiingo=True)
    decisions = [r for r in Journal(tmp_path / "audit.db").records() if r["kind"] == "decision"]
    assert result["evaluated_events"] == 1
    assert decisions[0]["payload"]["status"] == "NICHT VERFÜGBAR"
    assert "invalid_market_data" in decisions[0]["payload"]["reasons"]
