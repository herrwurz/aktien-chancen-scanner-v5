import json
from datetime import UTC, datetime

from scanner.hebeltrader.eodhd import sha
from scanner.hebeltrader.identity_assistant import _sha
from scanner.hebeltrader.openfigi_archive import audit_archive

CLOCK = datetime(2026, 10, 22, tzinfo=UTC)


def test_original_raw_and_linked_exports_are_read_only_and_mismatches_detected(tmp_path):
    payload = {"data": [dict(figi="FIGI1", ticker="SYN", exchCode="US")]}
    raw = json.dumps([payload]).encode()
    digest = sha(raw)
    cache = tmp_path / "raw"
    cache.mkdir()
    (cache / (digest + ".json")).write_bytes(raw)
    record = dict(
        query_wkn="AB1234",
        provider="openfigi",
        retrieved_at=CLOCK.isoformat(),
        source_reference="https://api.openfigi.com/v3/mapping",
        license="MIT",
        payload=payload,
        payload_sha256=_sha(payload),
        raw_response_sha256=digest,
        raw_response_pointer="/0",
        raw_cache_file=digest + ".json",
    )
    export = tmp_path / "openfigi.json"
    export.write_text(json.dumps({"records": [record]}))
    linked = tmp_path / "identities.json"
    linked.write_text(
        json.dumps(
            [
                dict(
                    wkn="AB1234",
                    identity_status="unverified",
                    selected=None,
                    candidates=[
                        dict(
                            figi="FIGI1",
                            ticker="SYN",
                            provider_exchange_code="US",
                            payload_sha256=_sha(payload),
                        )
                    ],
                )
            ]
        )
    )
    before = [p.read_bytes() for p in (export, linked, cache / (digest + ".json"))]
    audit = audit_archive(export, cache, linked, run_at=CLOCK)
    assert audit["errors"] == [] and audit["wkn_with_candidates"] == 1
    assert before == [p.read_bytes() for p in (export, linked, cache / (digest + ".json"))]
    linked.write_text(linked.read_text().replace("FIGI1", "FORGED"))
    assert (
        "linked_candidates_mismatch" in audit_archive(export, cache, linked, run_at=CLOCK)["errors"]
    )


def test_synthetic_96_wkn_94_hits_archive_without_new_api_requests(tmp_path):
    from scanner.hebeltrader.historical_identity import audit_identities

    identifiers = ["578560", "SJ6B4A"] + [f"A{i:05d}" for i in range(94)]
    cache = tmp_path / "raw"
    cache.mkdir()
    records = []
    for offset in range(0, 96, 25):
        keys = identifiers[offset : offset + 25]
        payloads = [
            {"warning": "synthetic no hit"}
            if wkn in {"578560", "SJ6B4A"}
            else {"data": [dict(figi="SYNTHETIC" + wkn, ticker="SYN" + wkn, exchCode="US")]}
            for wkn in keys
        ]
        raw = json.dumps(payloads).encode()
        digest = sha(raw)
        (cache / (digest + ".json")).write_bytes(raw)
        for index, (wkn, payload) in enumerate(zip(keys, payloads, strict=True)):
            records.append(
                dict(
                    query_wkn=wkn,
                    provider="openfigi",
                    retrieved_at=CLOCK.isoformat(),
                    source_reference="https://api.openfigi.com/v3/mapping",
                    license="MIT",
                    payload=payload,
                    payload_sha256=_sha(payload),
                    raw_response_sha256=digest,
                    raw_response_pointer=f"/{index}",
                    raw_cache_file=digest + ".json",
                )
            )
    export, linked = tmp_path / "openfigi.json", tmp_path / "linked.json"
    export.write_text(json.dumps(dict(records=records, fixture="synthetic, not Hetzner")))
    identities = audit_identities(
        [dict(wkn=w) for w in identifiers],
        records,
        run_at=CLOCK,
        cache_dir=cache,
    )["identities"]
    linked.write_text(json.dumps(identities))
    report = audit_archive(export, cache, linked, run_at=CLOCK)
    assert report["errors"] == []
    assert report["unique_wkn"] == 96 and report["wkn_with_candidates"] == 94
    assert report["database_writes"] == report["network_requests"] == 0
