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


def assess_document(document, cutoff):
    published = timestamp(document.get("published_at"))
    retrieved = timestamp(document.get("retrieved_at"))
    event = timestamp(document.get("event_at"))
    revision = timestamp(document.get("content_revision_at"))
    declared = timestamp(document.get("source_available_at"))
    proof = document.get("availability_evidence")
    bound_proof = bool(
        declared
        and isinstance(proof, dict)
        and proof.get("basis") == "archived_snapshot"
        and str(proof.get("source_url", "")).startswith("https://")
        and timestamp(proof.get("observed_at")) == declared
        and document.get("raw_sha256")
        and proof.get("content_sha256") == document.get("raw_sha256")
    )
    available = (
        declared if bound_proof else retrieved if retrieved and retrieved <= cutoff else None
    )
    basis = (
        "operator_archive_content_binding"
        if bound_proof
        else "observed_original"
        if available
        else "unknown"
    )
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
        "availability_evidence": proof if bound_proof else None,
        "eligibility": "after_cutoff" if after else "eligible" if eligible else "uncertain",
    }
