"""Distinct source availability and hypothetical publication-date entry policies."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from scanner.hebeltrader.parser import HEADER, parse_date

PUBLICATION_ZONE = ZoneInfo("Europe/Berlin")


def publication_evidence(doc):
    """Accept a matching original header, never a filename-derived date."""
    if any(f.get("code") in {"metadata_conflict", "invalid_publication_date"} for f in doc.flags):
        return None
    for item in doc.metadata_evidence:
        raw = item.get("raw", "")
        if not isinstance(raw, str):
            continue
        match = HEADER.fullmatch(raw)
        if not match:
            continue
        try:
            if parse_date(match[1]) != doc.publication_date:
                continue
        except ValueError:
            continue
        page = next((p for p in doc.pages if p.get("number") == item.get("page")), None)
        if page and " ".join(raw.split()) in " ".join(page.get("text", "").split()):
            return item
    return None


def entry_policy(doc, as_of, analysis_mode, strict_reason, calendar_timezone=None):
    """Research never asserts source availability, and never ignores known later release."""
    audit = dict(
        availability_status="verified" if strict_reason is None else "unverified",
        publication_evidence=None,
        publication_timezone=PUBLICATION_ZONE.key,
        calendar_timezone=calendar_timezone,
        entry_cutoff_exclusive=None,
        cutoff_basis="verified_source_availability",
    )
    if analysis_mode == "verified":
        cutoff = doc.verified_available_at if strict_reason is None else None
        audit["entry_cutoff_exclusive"] = cutoff.isoformat() if cutoff else None
        return cutoff, strict_reason, audit
    # Only the lack of availability may be replaced, not contradictory or excluded data.
    if strict_reason not in (None, "unverified_availability"):
        return None, strict_reason, audit
    evidence = publication_evidence(doc)
    if not evidence:
        return None, "unverified_publication_date", audit
    cutoff = datetime.combine(doc.publication_date, time.max, PUBLICATION_ZONE)
    if calendar_timezone is not None:
        try:
            calendar_end = datetime.combine(
                doc.publication_date, time.max, ZoneInfo(calendar_timezone)
            )
        except (KeyError, TypeError, ValueError):
            return None, "invalid_calendar_timezone", audit
        cutoff = max(cutoff, calendar_end)
    audit.update(
        availability_status="assumed_from_publication_date",
        publication_evidence=evidence,
        cutoff_basis="end_of_publication_day_assumption",
    )
    if strict_reason is None and doc.verified_available_at > cutoff:
        cutoff = doc.verified_available_at
        audit["cutoff_basis"] = "publication_day_and_verified_later_availability"
    audit["entry_cutoff_exclusive"] = cutoff.isoformat()
    if cutoff >= as_of:
        return None, "no_post_publication_window", audit
    return cutoff, None, audit
