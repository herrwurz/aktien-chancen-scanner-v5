"""Conservative, offline resolution of reviewed historical security identities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass
class IdentityResolution:
    candidates: list[dict]
    selected: dict | None
    issues: list[str]


class HistoricalIdentityProvider(Protocol):
    def resolve(
        self, *, instrument: dict, start: datetime | None, end: datetime, reviewed_as_of: datetime
    ) -> IdentityResolution: ...


_FIELDS = frozenset(
    """wkn isin instrument_wkn instrument_isin symbol venue timezone currency
adjustment file source_reference license retrieved_at calendar_file calendar_reference
corporate_actions_file corporate_actions_reference coverage_start coverage_end delisted_at
identity_status identity_reference identity_evidence identity_reviewed_by identity_reviewed_at
identity_valid_from identity_valid_until""".split()
)


def _at(value):
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamp required")
    stamp = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if stamp.utcoffset() is None:
        raise ValueError("timezone required")
    return stamp


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _snapshot(value):
    """Copy the sole supported nested manifest field without retaining caller objects."""
    fields = {"version", "manifest_file", "expected_hashes", "source_sha256"}
    hash_fields = {"file", "calendar_file", "corporate_actions_file"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid snapshot")
    version, manifest = value["version"], value["manifest_file"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
        raise ValueError("invalid snapshot version")
    if (
        not _text(manifest)
        or ":" in manifest
        or "\\" in manifest
        or PurePosixPath(manifest).is_absolute()
        or ".." in PurePosixPath(manifest).parts
    ):
        raise ValueError("invalid snapshot manifest path")
    result = {"version": version, "manifest_file": manifest}
    for key in ("expected_hashes", "source_sha256"):
        hashes = value[key]
        if not isinstance(hashes, dict) or set(hashes) != hash_fields:
            raise ValueError("invalid snapshot hashes")
        if any(
            not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in hashes.values()
        ):
            raise ValueError("invalid snapshot hash")
        result[key] = dict(hashes)
    if result["expected_hashes"] != result["source_sha256"]:
        raise ValueError("inconsistent snapshot hashes")
    return result


class LocalIdentityProvider:
    def __init__(self, mapping: dict):
        self.mapping = mapping if isinstance(mapping, dict) else {}

    def resolve(
        self, *, instrument: dict, start: datetime | None, end: datetime, reviewed_as_of: datetime
    ) -> IdentityResolution:
        candidates, seen, failures, valid = [], set(), [], []
        invalid_candidates = set()
        malformed = False
        for key in ("wkn", "isin"):
            identifier = instrument.get(key)
            if not _text(identifier):
                continue
            entries = self.mapping.get(identifier, [])
            entries = entries if isinstance(entries, list) else [entries]
            for entry in entries:
                if not isinstance(entry, dict):
                    malformed = True
                    continue
                # Only scalar, explicitly supported manifest fields leave this boundary.
                candidate = {
                    k: (v.isoformat() if isinstance(v, datetime) else v)
                    for k, v in entry.items()
                    if k in _FIELDS and isinstance(v, (str, int, float, bool, type(None), datetime))
                }
                invalid_snapshot = False
                if "snapshot" in entry:
                    try:
                        candidate["snapshot"] = _snapshot(entry["snapshot"])
                    except (ValueError, TypeError):
                        candidate["snapshot"] = None
                        invalid_snapshot = True
                fingerprint = (
                    json.dumps(candidate, sort_keys=True, allow_nan=False)
                    if all(
                        not isinstance(v, float) or v == v and abs(v) != float("inf")
                        for v in candidate.values()
                    )
                    else None
                )
                if fingerprint is None:
                    malformed = True
                    continue
                if invalid_snapshot or any(
                    k in _FIELDS and not isinstance(v, (str, datetime)) for k, v in entry.items()
                ):
                    invalid_candidates.add(fingerprint)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                candidates.append(candidate)
        try:
            end, reviewed_as_of = _at(end), _at(reviewed_as_of)
            start = _at(start) if start is not None else None
            if start is not None and start > end:
                raise ValueError("reversed window")
        except (ValueError, TypeError, OverflowError):
            return IdentityResolution(candidates, None, ["identity_window_unknown"])
        for candidate in candidates:
            problems = []
            if json.dumps(candidate, sort_keys=True, allow_nan=False) in invalid_candidates:
                problems.append("identity_invalid_candidate")
            matched = False
            for key in ("wkn", "isin"):
                direct, alias = candidate.get(key), candidate.get("instrument_" + key)
                if direct and alias and direct != alias:
                    problems.append("instrument_mismatch")
                supplied = direct or alias
                if supplied and instrument.get(key):
                    if supplied != instrument[key]:
                        problems.append("instrument_mismatch")
                    else:
                        matched = True
            if not matched:
                problems.append("instrument_mismatch")
            if any(
                not _text(candidate.get(k)) for k in ("symbol", "venue", "timezone", "currency")
            ):
                problems.append("identity_missing_metadata")
            try:
                ZoneInfo(candidate.get("timezone", ""))
            except (ValueError, TypeError, ZoneInfoNotFoundError):
                problems.append("identity_missing_metadata")
            if candidate.get("adjustment") != "raw":
                problems.append("identity_missing_metadata")
            if candidate.get("identity_status") != "verified" or any(
                not _text(candidate.get(k))
                for k in ("identity_reference", "identity_evidence", "identity_reviewed_by")
            ):
                problems.append("identity_unverified")
            try:
                if _at(candidate.get("identity_reviewed_at")) > reviewed_as_of:
                    problems.append("identity_review_in_future")
            except (ValueError, TypeError, OverflowError):
                problems.append("identity_unverified")
            try:
                first, last = (
                    _at(candidate.get("identity_valid_from")),
                    _at(candidate.get("identity_valid_until")),
                )
                if first > last or first > (start or end) or last < end:
                    problems.append("identity_outside_window")
            except (ValueError, TypeError, OverflowError):
                problems.append("identity_window_unknown")
            if not problems:
                valid.append(candidate)
            failures.extend(problems)
        if start is None:
            return IdentityResolution(
                candidates, None, ["missing_publication_date", "identity_window_unknown"]
            )
        # Venue and currency differences remain distinct identities, even if one currency matches.
        if len(valid) > 1:
            return IdentityResolution(candidates, None, ["identity_ambiguous"])
        if valid:
            candidate = valid[0]
            if instrument.get("currency") and candidate["currency"] != instrument["currency"]:
                return IdentityResolution(candidates, None, ["currency_mismatch"])
            return IdentityResolution(candidates, candidate, [])
        issues = list(dict.fromkeys(failures))
        if malformed:
            issues.append("identity_invalid_candidate")
        return IdentityResolution(candidates, None, issues or ["identity_unmapped"])
