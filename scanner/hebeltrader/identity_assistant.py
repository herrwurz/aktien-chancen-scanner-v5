"""Unverified identity proposals. Importing and suggesting never access the network."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ENDPOINT = "https://api.openfigi.com/v3/mapping"
LICENSE = "https://www.openfigi.com/docs/terms-of-service"
FIELDS = (
    "isin",
    "historical_ticker",
    "venue",
    "timezone",
    "currency",
    "listing_valid_from",
    "listing_valid_until",
    "delisted_at",
)


def _at(value):
    result = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if result.utcoffset() is None:
        raise ValueError("timezone required")
    return result


def _raw(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(payload):
    return hashlib.sha256(_raw(payload)).hexdigest()


def validate_source_cache(records: list[dict], cache_dir: Path | None) -> list[dict]:
    """Read each raw cache file once and bind its indexed payload to the record.

    Hashes establish integrity, not authenticity: OpenFIGI does not echo WKN.
    Query association is the collector's request-order provenance.
    """
    checked = []
    for original in records:
        if not isinstance(original, dict):
            checked.append({"integrity_error": "malformed_source"})
            continue
        record = dict(original)
        if "raw_cache_file" not in record:
            checked.append(record)
            continue
        try:
            if cache_dir is None:
                raise FileNotFoundError
            name, digest = record["raw_cache_file"], record.get("raw_response_sha256")
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[0-9a-f]{64}\.json", name)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or name != digest + ".json"
            ):
                raise ValueError("invalid cache reference")
            root = Path(cache_dir).resolve()
            path = root / name
            if path.is_symlink() or path.resolve().parent != root:
                raise ValueError("cache escape")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("raw hash mismatch")
            payload = json.loads(raw)
            pointer = record.get("raw_response_pointer")
            if not isinstance(pointer, str) or not re.fullmatch(r"/(0|[1-9][0-9]*)", pointer):
                raise ValueError("invalid response pointer")
            if not isinstance(payload, list):
                raise ValueError("invalid raw response")
            item = payload[int(pointer[1:])]
            if _sha(item) != record.get("payload_sha256") or _sha(
                record.get("payload")
            ) != record.get("payload_sha256"):
                raise ValueError("payload mismatch")
            if not isinstance(record.get("query_wkn"), str) or not re.fullmatch(
                r"[A-Z0-9]{6}", record["query_wkn"]
            ):
                raise ValueError("invalid query association")
        except FileNotFoundError:
            record["integrity_error"] = "raw_cache_unavailable"
        except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError):
            record["integrity_error"] = "raw_cache_integrity_error"
        checked.append(record)
    return checked


def suggest_identity(instrument: dict, source_records: list[dict], *, run_at) -> dict:
    """Return evidence-bearing proposals; never authorize a historical identity.

    Records: query_wkn, provider (openfigi or historical_source), retrieved_at,
    source_reference, license, payload, payload_sha256. historical_source payload
    requires wkn and supplies explicit FIELDS, optionally ticker and as_of.
    """
    now = _at(run_at)
    wkn = instrument.get("wkn")
    result = {
        "wkn": wkn,
        "identity_status": "unverified",
        "selected": None,
        "candidates": [],
        "reason_codes": [],
        "needed_manual_proof": [
            "dated WKN/ISIN identity evidence",
            "historical ticker and venue",
            "timezone and currency",
            "listing validity and delisting evidence",
            "manual review with reviewer, reference and timestamp",
        ],
    }
    reasons = result["reason_codes"]
    if not isinstance(wkn, str) or not re.fullmatch(r"[A-Z0-9]{6}", wkn):
        reasons.append("invalid_wkn")
        return result
    for record in source_records:
        if not isinstance(record, dict):
            reasons.append("malformed_source")
            continue
        if record.get("query_wkn") != wkn:
            continue
        if record.get("integrity_error"):
            reasons.append("source_cache_integrity_error")
            continue
        try:
            if _at(record["retrieved_at"]) > now:
                reasons.append("source_in_future")
                continue
            if any(
                not isinstance(record.get(k), str) or not record[k].strip()
                for k in ("source_reference", "license", "provider")
            ):
                raise ValueError("missing provenance")
            payload = record["payload"]
            digest = _sha(payload)
            if record.get("payload_sha256") != digest:
                reasons.append("payload_integrity_error")
                continue
            provider = record["provider"]
            if provider == "openfigi":
                if not isinstance(payload, dict):
                    raise ValueError("invalid response")
                if payload.get("error") or payload.get("warning"):
                    reasons.append("source_no_information")
                    continue
                rows = payload.get("data")
                if not isinstance(rows, list):
                    raise ValueError("invalid data")
            elif provider == "historical_source":
                if not isinstance(payload, dict) or payload.get("wkn") != wkn:
                    reasons.append("source_identifier_mismatch")
                    continue
                rows = [payload]
            else:
                reasons.append("unsupported_provider")
                continue
            if not rows:
                reasons.append("source_no_information")
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ValueError("invalid candidate")
                candidate = dict.fromkeys(FIELDS)
                evidence = {}
                if provider == "openfigi":
                    # exchCode is a provider code, not a sourced MIC/timezone/currency table.
                    if any(
                        row.get(k) is not None and not isinstance(row[k], str)
                        for k in ("ticker", "exchCode")
                    ):
                        raise ValueError("invalid metadata")
                    if not isinstance(row.get("figi"), str) or not row["figi"]:
                        raise ValueError("missing FIGI")
                    candidate.update(
                        ticker=row.get("ticker") if isinstance(row.get("ticker"), str) else None,
                        figi=row["figi"],
                        provider_exchange_code=row.get("exchCode"),
                        temporal_scope="current_lookup_not_historical",
                        as_of=record["retrieved_at"],
                    )
                    for field, raw_field in (
                        ("ticker", "ticker"),
                        ("figi", "figi"),
                        ("provider_exchange_code", "exchCode"),
                    ):
                        if candidate.get(field) is not None:
                            evidence[field] = f"/data/{index}/{raw_field}"
                else:
                    for field in FIELDS:
                        if row.get(field) is not None:
                            if not isinstance(row[field], str) or not row[field].strip():
                                raise ValueError("invalid field")
                            candidate[field] = row[field]
                            evidence[field] = "/" + field
                    if not evidence:
                        reasons.append("source_no_information")
                        continue
                    if row.get("ticker") is not None and not isinstance(row["ticker"], str):
                        raise ValueError("invalid ticker")
                    as_of = row.get("as_of")
                    if as_of is not None and _at(as_of) > now:
                        reasons.append("source_in_future")
                        continue
                    candidate.update(
                        ticker=row.get("ticker"),
                        temporal_scope="dated_source" if as_of else "undated_source",
                        as_of=as_of,
                    )
                candidate.update(
                    identity_status="unverified",
                    query_wkn=wkn,
                    provider=provider,
                    source_reference=record["source_reference"],
                    retrieved_at=record["retrieved_at"],
                    license=record["license"],
                    payload_sha256=digest,
                    raw_response_sha256=record.get("raw_response_sha256"),
                    raw_response_pointer=record.get("raw_response_pointer"),
                    evidence=evidence,
                )
                if candidate not in result["candidates"]:
                    result["candidates"].append(candidate)
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            reasons.append("malformed_source")
    identities = {
        tuple(c.get(k) for k in (*FIELDS, "ticker", "figi", "provider_exchange_code"))
        for c in result["candidates"]
    }
    if len(identities) > 1:
        reasons.append("identity_ambiguous")
    if not result["candidates"]:
        reasons.append("identity_unmapped")
    reasons.append("manual_review_required")
    result["reason_codes"] = list(dict.fromkeys(reasons))
    return result


def collect_openfigi(
    instruments: list[dict],
    *,
    cache_dir,
    allow_network=False,
    client: httpx.Client | None = None,
    run_at=None,
) -> dict:
    """Explicit, unauthenticated, serial public lookup; ten jobs/request, bounded retries.

    No credentials or paid features. Raw response bytes are cached with exclusive
    creation; records hash their individual parsed response for offline checks.
    """
    if not allow_network:
        raise ValueError("network requires explicit --allow-network")
    wkns = sorted(
        {
            i["wkn"]
            for i in instruments
            if isinstance(i, dict)
            and isinstance(i.get("wkn"), str)
            and re.fullmatch(r"[A-Z0-9]{6}", i["wkn"])
        }
    )
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = []
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
    try:
        for start in range(0, len(wkns), 10):
            batch = wkns[start : start + 10]
            response = None
            # At most two attempts; do not wait on untrusted Retry-After values.
            for attempt in range(2):
                try:
                    response = client.post(
                        ENDPOINT,
                        json=[{"idType": "ID_WERTPAPIER", "idValue": w} for w in batch],
                        timeout=15,
                    )
                except httpx.TransportError:
                    if attempt:
                        raise
                    time.sleep(6)
                    continue
                if response.status_code not in (429, 500, 502, 503, 504):
                    break
                if attempt == 0:
                    time.sleep(6)
            response.raise_for_status()
            raw = response.content
            digest = hashlib.sha256(raw).hexdigest()
            path = directory / (digest + ".json")
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise ValueError("cache integrity error") from None
            else:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != len(batch):
                raise ValueError("unexpected OpenFIGI response shape")
            retrieved = _at(run_at or datetime.now(UTC)).isoformat()
            for index, (wkn, item) in enumerate(zip(batch, payload, strict=True)):
                records.append(
                    {
                        "query_wkn": wkn,
                        "provider": "openfigi",
                        "retrieved_at": retrieved,
                        "source_reference": ENDPOINT,
                        "license": LICENSE,
                        "payload": item,
                        "payload_sha256": _sha(item),
                        "raw_response_sha256": digest,
                        "raw_response_pointer": f"/{index}",
                        "raw_cache_file": path.name,
                    }
                )
            if start + 10 < len(wkns):
                time.sleep(6)
    finally:
        if own_client:
            client.close()
    return {"provider": "openfigi", "records": records, "unique_wkn_count": len(wkns)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--input", required=True)
    collect.add_argument("--output", required=True)
    collect.add_argument("--cache-dir", required=True)
    collect.add_argument("--allow-network", action="store_true")
    collect.add_argument("--provider", choices=["openfigi"], required=True)
    args = parser.parse_args(argv)
    if Path(args.output).exists():
        parser.error("output must be a new file")
    if not args.allow_network:
        parser.error("collection requires --allow-network")
    try:
        manifest = json.loads(Path(args.input).read_text())
        instruments = manifest if isinstance(manifest, list) else manifest["instruments"]
        if not isinstance(instruments, list):
            raise ValueError("invalid instruments")
        result = collect_openfigi(instruments, cache_dir=args.cache_dir, allow_network=True)
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError):
        print(
            "identity collection failed; check input, cache, or public service availability",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
