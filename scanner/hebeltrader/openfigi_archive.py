"""Read-only audit of original V1.4 export, raw responses and linked identity export."""

import json
from pathlib import Path

from .eodhd import canonical, sha
from .historical_identity import audit_identities
from .market_snapshot import _credentials


def audit_archive(export_path, raw_dir, linked_path, *, run_at):
    raw = Path(export_path).read_bytes()
    export = json.loads(raw)
    records = export["records"]
    if not isinstance(records, list):
        raise ValueError("records list required")
    instruments = [dict(wkn=r["query_wkn"]) for r in records]
    audited = audit_identities(instruments, records, run_at=run_at, cache_dir=Path(raw_dir))
    errors = []
    if audited["source_records_integrity_failed"]:
        errors.append("raw_or_payload_integrity_error")
    result = dict(
        export_sha256=sha(raw),
        source_records=len(records),
        unique_wkn=audited["unique_wkn"],
        wkn_with_candidates=audited["openfigi_wkn_with_candidates"],
        multiple_venue_wkn=audited["multiple_venue_wkn"],
        linked_sha256=None,
        errors=errors,
        database_writes=0,
        network_requests=0,
    )
    if linked_path:
        linked_raw = Path(linked_path).read_bytes()
        linked = json.loads(linked_raw)
        _credentials(linked)
        if not isinstance(linked, list):
            raise ValueError("linked identities list required")
        result["linked_sha256"] = sha(linked_raw)
        authoritative = {row["wkn"]: row for row in audited["identities"]}
        seen = set()

        def signatures(candidates):
            return {
                tuple(
                    c.get(k) for k in ("figi", "ticker", "provider_exchange_code", "payload_sha256")
                )
                for c in candidates
            }

        for row in linked:
            wkn = row["wkn"]
            if wkn in seen or wkn not in authoritative:
                errors.append("duplicate_or_unknown_linked_wkn")
            elif signatures(row["candidates"]) != signatures(authoritative[wkn]["candidates"]):
                errors.append("linked_candidates_mismatch")
            if row.get("identity_status") == "verified" or row.get("selected") is not None:
                errors.append("linked_approval_not_a_historical_source")
            seen.add(wkn)
        if seen != set(authoritative):
            errors.append("linked_inventory_mismatch")
    result["errors"] = sorted(set(errors))
    result["audit_sha256"] = sha(canonical(result))
    return result
