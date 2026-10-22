import hashlib
import json
from datetime import UTC, datetime

from scanner.hebeltrader.historical_identity import ReviewedIdentityProvider, audit_identities

CLOCK = datetime(2026, 10, 22, tzinfo=UTC)


def source(payload, provider="historical_source"):
    return dict(
        query_wkn="AB1234",
        provider=provider,
        retrieved_at=CLOCK.isoformat(),
        source_reference="https://issuer.example/dated-2025-report",
        license="private research permitted",
        payload=payload,
        payload_sha256=hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )


def test_multiple_figi_venues_preserved_and_current_data_never_verified():
    payload = dict(
        data=[
            dict(figi="FIGI1", ticker="ABC", exchCode="US", securityType="Common Stock"),
            dict(figi="FIGI2", ticker="ABC", exchCode="GR", securityType="Common Stock"),
        ]
    )
    report = audit_identities([dict(wkn="AB1234")], [source(payload, "openfigi")], run_at=CLOCK)
    row = report["identities"][0]
    assert len(row["candidates"]) == 2
    assert row["identity_status"] == "unverified"
    assert row["selected"] is None
    assert row["venue_candidate_count"] == 2
    assert all(c["venue"] is None for c in row["candidates"])


def test_duplicate_stock_and_derivative_id_is_quarantined():
    report = audit_identities([dict(wkn="SJ6B4A", derivative_wkn="SJ6B4A")], [], run_at=CLOCK)
    assert (
        report["identities"][0]["classification_status"] == "quarantined_stock_derivative_collision"
    )


def test_verified_label_without_field_bound_historical_proofs_is_rejected():
    spec = dict(
        wkn="AB1234",
        isin="US0378331005",
        symbol="ABC.US",
        venue="XNYS",
        timezone="America/New_York",
        currency="USD",
        adjustment="raw",
        identity_status="verified",
        identity_reviewed_by="Person",
        identity_reviewed_at=CLOCK.isoformat(),
        identity_reference="issuer report",
        identity_evidence="reviewed",
        identity_valid_from="2025-01-01T00:00:00+00:00",
        identity_valid_until="2025-12-31T23:59:00+00:00",
    )
    resolver = ReviewedIdentityProvider({"AB1234": spec}, [], run_at=CLOCK)
    result = resolver.resolve(
        instrument={"wkn": "AB1234", "currency": "USD"},
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 2, 1, tzinfo=UTC),
        reviewed_as_of=CLOCK,
    )
    assert result.selected is None


def test_dated_manual_sources_allow_reviewed_interval_but_not_later_identifier_reuse():
    payload = dict(
        wkn="AB1234",
        isin="US0378331005",
        symbol="ABC.US",
        venue="XNYS",
        timezone="America/New_York",
        currency="USD",
        asset_class="stock",
        identity_valid_from="2025-01-01T00:00:00+00:00",
        identity_valid_until="2025-12-31T23:59:00+00:00",
    )
    record = source(payload)
    spec = dict(
        payload,
        adjustment="raw",
        identity_status="verified",
        identity_reviewed_by="Person",
        identity_reviewed_at=CLOCK.isoformat(),
        identity_reference=record["source_reference"],
        identity_evidence="dated issuer and exchange evidence",
        review_evidence={
            k: dict(payload_sha256=record["payload_sha256"], pointer="/" + k) for k in payload
        },
    )
    resolver = ReviewedIdentityProvider({"AB1234": spec}, [record], run_at=CLOCK)
    for year, selected in [(2025, True), (2026, False)]:
        result = resolver.resolve(
            instrument={"wkn": "AB1234", "currency": "USD"},
            start=datetime(year, 1, 1, tzinfo=UTC),
            end=datetime(year, 2, 1, tzinfo=UTC),
            reviewed_as_of=CLOCK,
        )
        assert (result.selected is not None) == selected


def test_real_fresenius_and_daimler_pdf_identifiers_remain_proposals_only():
    from pathlib import Path

    fixture = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/hebeltrader/v15-targeted-identifiers.json"
        ).read_text()
    )
    report = audit_identities(fixture["instruments"], [], run_at=CLOCK)
    assert report["unique_wkn"] == 2
    fresenius = next(r for r in report["identities"] if r["wkn"] == "578560")
    assert len(fresenius["contexts"]) == 2
    assert fresenius["identity_status"] == "unverified"
    daimler = next(r for r in report["identities"] if r["wkn"] == "SJ6B4A")
    assert daimler["classification_status"] == "quarantined_stock_derivative_collision"
    context = daimler["contexts"][0]
    assert context["stock_wkn_evidence"][0]["page"] == 3
    assert context["derivative_wkn_evidence"][0]["page"] == 1
    assert (
        context["stock_wkn_evidence"][0]["raw"]
        == context["derivative_wkn_evidence"][0]["raw"]
        == "SJ6B4A"
    )


def test_bad_payload_hash_cannot_count_as_a_completed_lookup():
    record = source({"data": []}, "openfigi")
    record["payload_sha256"] = "0" * 64
    report = audit_identities([dict(wkn="AB1234")], [record], run_at=CLOCK)
    assert report["queried_openfigi_wkn"] == 0
    assert report["source_records_integrity_failed"] == 1
