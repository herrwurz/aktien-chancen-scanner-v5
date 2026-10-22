"""Evidence-bound historical identities. Public lookups remain unverified proposals."""

import re
from collections import defaultdict

from .identity import IdentityResolution, LocalIdentityProvider
from .identity_assistant import _at, _sha, suggest_identity, validate_source_cache
from .market_snapshot import _credentials
from .parser import isin

PROOF_FIELDS = (
    "wkn",
    "isin",
    "symbol",
    "venue",
    "timezone",
    "currency",
    "identity_valid_from",
    "identity_valid_until",
    "asset_class",
)


def _checked_records(records, cache_dir):
    checked = validate_source_cache(records, cache_dir)
    for record in checked:
        try:
            _credentials(record)
            if _sha(record["payload"]) != record["payload_sha256"]:
                record["integrity_error"] = "payload_integrity_error"
        except (ValueError, KeyError, TypeError):
            record["integrity_error"] = "malformed_source"
    return checked


def audit_identities(instruments, records, *, run_at, cache_dir=None):
    checked = _checked_records(records, cache_dir)
    grouped = defaultdict(list)
    for item in instruments:
        if item.get("wkn"):
            grouped[item["wkn"]].append(item)
    identities = []
    for wkn, contexts in sorted(grouped.items()):
        row = suggest_identity(dict(wkn=wkn), checked, run_at=run_at)
        for candidate in row["candidates"]:
            record = next(
                r for r in checked if r.get("payload_sha256") == candidate["payload_sha256"]
            )
            raw = record["payload"]
            if candidate["provider"] == "openfigi":
                matching = [
                    d for d in raw.get("data", []) if d.get("figi") == candidate.get("figi")
                ]
                if len(matching) == 1:
                    candidate["security_type"] = matching[0].get("securityType")
                    candidate["market_sector"] = matching[0].get("marketSector")
        if any(
            re.search(r"warrant|option|future|bond|certificate", c.get("security_type") or "", re.I)
            for c in row["candidates"]
        ):
            row["reason_codes"].append("non_stock_figi_candidate_requires_review")
        collision = any(c.get("derivative_wkn") == wkn for c in contexts)
        row["classification_status"] = (
            "quarantined_stock_derivative_collision"
            if collision
            else "stock_classification_requires_review"
        )
        row["venue_candidate_count"] = len(
            {
                c.get("provider_exchange_code") or c.get("venue")
                for c in row["candidates"]
                if c.get("provider_exchange_code") or c.get("venue")
            }
        )
        row["historical_continuity"] = "unverified"
        row["contexts"] = contexts
        row["requires_manual_review"] = True
        if collision:
            row["reason_codes"].append("stock_derivative_identifier_collision")
        identities.append(row)
    return dict(
        version="1.5",
        identities=identities,
        unique_wkn=len(identities),
        queried_openfigi_wkn=len(
            {
                r.get("query_wkn")
                for r in checked
                if r.get("provider") == "openfigi"
                and not r.get("integrity_error")
                and r.get("query_wkn") in grouped
            }
        ),
        wkn_with_candidates=sum(bool(r["candidates"]) for r in identities),
        openfigi_wkn_with_candidates=sum(
            any(c["provider"] == "openfigi" for c in r["candidates"]) for r in identities
        ),
        multiple_venue_wkn=sum(r["venue_candidate_count"] > 1 for r in identities),
        classification_conflicts=sum(
            r["classification_status"].startswith("quarantined") for r in identities
        ),
        source_records_supplied=len(records),
        source_records_integrity_failed=sum(bool(r.get("integrity_error")) for r in checked),
    )


def _pointer(payload, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer required")
    value = payload
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def review_supported(spec, records, run_at):
    try:
        _credentials(spec)
        if (
            spec.get("identity_status") != "verified"
            or not spec.get("identity_reviewed_by", "").strip()
        ):
            return False
        if _at(spec["identity_reviewed_at"]) > run_at or spec.get("asset_class") != "stock":
            return False
        isin(spec["isin"])
        if not re.fullmatch(r"[A-Z0-9]{4}", spec["venue"]):
            return False
        fields = (*PROOF_FIELDS, *(["delisted_at"] if spec.get("delisted_at") else []))
        for field in fields:
            proof = spec["review_evidence"][field]
            matched = [
                r
                for r in records
                if r.get("payload_sha256") == proof["payload_sha256"]
                and r.get("provider") == "historical_source"
                and not r.get("integrity_error")
            ]
            if not matched:
                return False
            record = matched[0]
            if (
                record.get("query_wkn") != spec["wkn"]
                or _sha(record["payload"]) != record["payload_sha256"]
                or _at(record["retrieved_at"]) > min(run_at, _at(spec["identity_reviewed_at"]))
                or not record.get("source_reference")
                or not record.get("license")
            ):
                return False
            _credentials(record)
            if _pointer(record["payload"], proof["pointer"]) != spec[field]:
                return False
        return True
    except (KeyError, ValueError, TypeError, IndexError, AttributeError):
        return False


class ReviewedIdentityProvider:
    """V1.3-compatible resolver, with additional field-by-field historical proofs."""

    def __init__(self, mapping, records, *, run_at, cache_dir=None, blocked_wkn=()):
        self.blocked = set(blocked_wkn)
        checked = _checked_records(records, cache_dir)
        self.mapping = {}
        for key, entries in mapping.items():
            entries = entries if isinstance(entries, list) else [entries]
            self.mapping[key] = [
                dict(
                    e,
                    identity_status="verified"
                    if review_supported(e, checked, run_at)
                    else "unverified",
                )
                for e in entries
                if isinstance(e, dict)
            ]
        self.provider = LocalIdentityProvider(self.mapping)

    def resolve(self, *, instrument, **kwargs):
        if instrument.get("wkn") in self.blocked:
            return IdentityResolution([], None, ["stock_derivative_identifier_collision"])
        return self.provider.resolve(instrument=instrument, **kwargs)
