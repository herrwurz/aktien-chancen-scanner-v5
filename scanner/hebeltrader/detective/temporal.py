"""Source time contract: publication is not proof of historical availability."""

from datetime import datetime


def timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def _bound_availability(document, proof, declared):
    """Return availability-basis label when proof binds declared time to this content."""
    if not declared or not isinstance(proof, dict):
        return None
    if not (
        document.get("raw_sha256")
        and proof.get("content_sha256") == document.get("raw_sha256")
        and str(proof.get("source_url", "")).startswith("https://")
    ):
        return None
    basis = proof.get("basis")
    if basis == "archived_snapshot":
        # WayBack/operator archive: observation time must equal declared availability.
        if timestamp(proof.get("observed_at")) == declared:
            return "operator_archive_content_binding"
        return None
    if basis == "sec_edgar_filing_date":
        # EDGAR accession URLs are immutable; filing/published date is public availability.
        # observed_at is when the content was hashed (may be after cutoff).
        published = timestamp(document.get("published_at"))
        url = str(proof.get("source_url", ""))
        if (
            url.startswith("https://www.sec.gov/Archives/edgar/")
            and published is not None
            and published == declared
            and timestamp(proof.get("observed_at")) is not None
        ):
            return "sec_edgar_filing_date_binding"
        return None
    return None


def assess_document(document, cutoff):
    published = timestamp(document.get("published_at"))
    retrieved = timestamp(document.get("retrieved_at"))
    event = timestamp(document.get("event_at"))
    revision = timestamp(document.get("content_revision_at"))
    declared = timestamp(document.get("source_available_at"))
    proof = document.get("availability_evidence")
    binding = _bound_availability(document, proof, declared)
    available = declared if binding else retrieved if retrieved and retrieved <= cutoff else None
    basis = binding if binding else ("observed_original" if available else "unknown")
    after = any(t and t > cutoff for t in (published, event, revision, available, declared))
    eligible = bool(published and retrieved and available and not after)
    return {
        "url": document.get("url"),
        "event_at": event.isoformat() if event else None,
        "published_at": published.isoformat() if published else None,
        "source_available_at": available.isoformat() if available else None,
        "retrieved_at": retrieved.isoformat() if retrieved else None,
        "content_revision_at": revision.isoformat() if revision else None,
        "availability_status": "documented" if available else "uncertain",
        "availability_basis": basis,
        "availability_evidence": proof if binding else None,
        "eligibility": "after_cutoff" if after else "eligible" if eligible else "uncertain",
    }
