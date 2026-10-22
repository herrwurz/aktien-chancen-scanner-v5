import hashlib
import json

import httpx
import pytest

from scanner.hebeltrader.identity_assistant import collect_openfigi, suggest_identity

NOW = "2026-10-22T10:00:00Z"
WKN = {"wkn": "ABC123"}


def record(payload=None, **updates):
    payload = (
        payload
        if payload is not None
        else {"data": [{"figi": "BBG000000001", "ticker": "NEW", "exchCode": "US"}]}
    )
    result = {
        "query_wkn": "ABC123",
        "provider": "openfigi",
        "retrieved_at": NOW,
        "source_reference": "https://api.openfigi.com/v3/mapping",
        "license": "https://www.openfigi.com/docs/terms-of-service",
        "payload": payload,
        "payload_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    result.update(updates)
    return result


def suggest(records):
    return suggest_identity(WKN, records, run_at=NOW)


def test_current_lookup_is_not_historical_and_never_verified():
    result = suggest([record()])
    candidate = result["candidates"][0]
    assert result["selected"] is None
    assert result["identity_status"] == candidate["identity_status"] == "unverified"
    assert candidate["ticker"] == "NEW"
    assert candidate["temporal_scope"] == "current_lookup_not_historical"
    assert all(
        candidate[k] is None
        for k in (
            "isin",
            "historical_ticker",
            "venue",
            "timezone",
            "currency",
            "listing_valid_from",
            "delisted_at",
        )
    )
    assert candidate["evidence"]["ticker"] == "/data/0/ticker"
    assert candidate["payload_sha256"] == record()["payload_sha256"]


def test_conflicting_records_never_choose_current_over_dated():
    historical = record(
        {
            "wkn": "ABC123",
            "historical_ticker": "OLD",
            "venue": "XNYS",
            "as_of": "2020-01-01T00:00:00Z",
        },
        provider="historical_source",
    )
    result = suggest([record(), historical])
    assert "identity_ambiguous" in result["reason_codes"]
    assert result["selected"] is None
    assert result["candidates"][1]["historical_ticker"] == "OLD"
    assert result["candidates"][1]["temporal_scope"] == "dated_source"


@pytest.mark.parametrize(
    "source,reason",
    [
        (record(retrieved_at="2027-01-01T00:00:00Z"), "source_in_future"),
        (record(payload_sha256="0" * 64), "payload_integrity_error"),
        (record({"warning": "No identifier found."}), "source_no_information"),
        (record({"data": []}), "source_no_information"),
        (record({"data": [None]}), "malformed_source"),
        (record({"data": [{"figi": "x", "exchCode": {}}]}), "malformed_source"),
        (record(license=""), "malformed_source"),
        (
            record({"wkn": "XYZ123", "historical_ticker": "X"}, provider="historical_source"),
            "source_identifier_mismatch",
        ),
    ],
)
def test_bad_source_fails_closed(source, reason):
    result = suggest([source])
    assert not result["candidates"]
    assert reason in result["reason_codes"]


def test_no_record_unrelated_and_duplicate_evidence():
    assert "identity_unmapped" in suggest([])["reason_codes"]
    assert not suggest([record(query_wkn="XYZ123")])["candidates"]
    assert len(suggest([record(), record()])["candidates"]) == 1
    assert "identity_ambiguous" not in suggest([record(), record()])["reason_codes"]


def test_dated_source_future_and_no_data():
    future = record(
        {"wkn": "ABC123", "historical_ticker": "OLD", "as_of": "2030-01-01T00:00:00Z"},
        provider="historical_source",
    )
    assert "source_in_future" in suggest([future])["reason_codes"]
    empty = record({"wkn": "ABC123"}, provider="historical_source")
    assert "source_no_information" in suggest([empty])["reason_codes"]


def test_collector_no_key_repeated_wkn_and_immutable_raw_cache(tmp_path):
    requests = []

    def handle(request):
        requests.append(request)
        assert "X-OPENFIGI-APIKEY" not in request.headers
        assert json.loads(request.content) == [{"idType": "ID_WERTPAPIER", "idValue": "ABC123"}]
        return httpx.Response(200, json=[record()["payload"]])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = collect_openfigi(
            [WKN, WKN], cache_dir=tmp_path, allow_network=True, client=client, run_at=NOW
        )
        assert result["unique_wkn_count"] == 1
        assert len(requests) == 1
        source = result["records"][0]
        cached = tmp_path / source["raw_cache_file"]
        assert hashlib.sha256(cached.read_bytes()).hexdigest() == source["raw_response_sha256"]
        assert suggest(result["records"])["candidates"]
        cached.write_bytes(b"tampered")
        with pytest.raises(ValueError, match="cache integrity"):
            collect_openfigi(
                [WKN], cache_dir=tmp_path, allow_network=True, client=client, run_at=NOW
            )


def test_collector_requires_explicit_opt_in(tmp_path):
    with pytest.raises(ValueError, match="explicit"):
        collect_openfigi([WKN], cache_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_multiple_openfigi_listings_ambiguous():
    payload = {
        "data": [
            {"figi": "BBG000000001", "ticker": "X", "exchCode": "US"},
            {"figi": "BBG000000002", "ticker": "X", "exchCode": "GY"},
        ]
    }
    result = suggest([record(payload)])
    assert len(result["candidates"]) == 2
    assert "identity_ambiguous" in result["reason_codes"]
    assert result["selected"] is None


def test_retry_is_bounded_and_timeout_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr("scanner.hebeltrader.identity_assistant.time.sleep", lambda _: None)
    calls = []

    def handle(request):
        calls.append(request)
        assert request.extensions["timeout"]["read"] == 15
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.ReadTimeout):
            collect_openfigi([WKN], cache_dir=tmp_path, allow_network=True, client=client)
    assert len(calls) == 2
    assert not list(tmp_path.iterdir())


def test_readonly_cache_validation_binds_pointer_and_payload(tmp_path):
    from scanner.hebeltrader.identity_assistant import validate_source_cache

    def handle(request):
        return httpx.Response(200, json=[record()["payload"]])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        source = collect_openfigi(
            [WKN], cache_dir=tmp_path, allow_network=True, client=client, run_at=NOW
        )["records"][0]
    checked = validate_source_cache([source], tmp_path)
    assert checked == [source]
    assert "source_cache_integrity_error" not in suggest(checked)["reason_codes"]
    for patch in (
        {"raw_cache_file": "../escape"},
        {"raw_response_pointer": "/1"},
        {"payload_sha256": "a" * 64},
        {"payload": {"data": []}},
    ):
        invalid = validate_source_cache([{**source, **patch}], tmp_path)
        assert invalid[0]["integrity_error"] == "raw_cache_integrity_error"
        assert not suggest(invalid)["candidates"]
    assert "integrity_error" not in source
    unavailable = validate_source_cache([source], None)
    assert unavailable[0]["integrity_error"] == "raw_cache_unavailable"
    assert not suggest(unavailable)["candidates"]
    cached = tmp_path / source["raw_cache_file"]
    cached.write_bytes(b"tampered")
    assert validate_source_cache([source], tmp_path)[0]["integrity_error"]


def test_collection_cli_sanitizes_failure_and_returns_status(tmp_path, monkeypatch, capsys):
    from scanner.hebeltrader.identity_assistant import main

    manifest = tmp_path / "input.json"
    manifest.write_text(json.dumps([WKN]))
    arguments = [
        "collect",
        "--input",
        str(manifest),
        "--output",
        str(tmp_path / "new.json"),
        "--cache-dir",
        str(tmp_path / "cache"),
        "--provider",
        "openfigi",
        "--allow-network",
    ]

    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("https://secret:token@example.com/?apikey=private")

    monkeypatch.setattr("scanner.hebeltrader.identity_assistant.collect_openfigi", fail)
    assert main(arguments) == 2
    captured = capsys.readouterr()
    assert "private" not in captured.err and "secret" not in captured.err
    monkeypatch.setattr(
        "scanner.hebeltrader.identity_assistant.collect_openfigi",
        lambda *args, **kwargs: {"records": []},
    )
    assert main(arguments) == 0
    assert json.loads((tmp_path / "new.json").read_text()) == {"records": []}
