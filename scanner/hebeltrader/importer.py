import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from scanner.hebeltrader.domain import EXTRACTOR_VERSION, Extraction
from scanner.hebeltrader.models import (
    Document,
    HistoricalRecommendation,
    ImportRun,
    Publication,
    SourceLocation,
)
from scanner.hebeltrader.parser import extract_pdf


def persist(session, data, extraction, root_id, relative_path, failed=False):
    sha = hashlib.sha256(data).hexdigest()
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    publication_id = None
    if extraction.issue_year and extraction.issue_number:
        identity = dict(issue_year=extraction.issue_year, issue_number=extraction.issue_number)
        session.execute(insert(Publication).values(**identity).on_conflict_do_nothing())
        issue = session.scalar(select(Publication).filter_by(**identity).with_for_update())
        publication_id = issue.id
    existing = session.get(Document, sha)
    new = existing is None
    if new:
        status = "failed" if failed else "extracted"
        inserted = session.execute(
            insert(Document)
            .values(
                sha256=sha,
                publication_id=publication_id,
                publication_date=extraction.publication_date,
                original_pdf=data,
                byte_size=len(data),
                extractor_version=EXTRACTOR_VERSION,
                imported_at=datetime.now(UTC),
                extraction_status=status,
                review_status="pending",
                revision_conflict=False,
                pages=extraction.pages,
                flags=extraction.flags,
                metadata_evidence=extraction.metadata_evidence,
            )
            .on_conflict_do_nothing(index_elements=["sha256"])
        )
        new = bool(inserted.rowcount)
        if new:
            for ordinal, rec in enumerate(extraction.recommendations, 1):
                session.add(
                    HistoricalRecommendation(
                        document_sha=sha,
                        ordinal=ordinal,
                        **rec.values,
                        evidence=rec.evidence,
                        flags=rec.flags,
                    )
                )
            if publication_id is not None:
                variants = session.scalars(
                    select(Document).where(Document.publication_id == publication_id)
                ).all()
                if len(variants) > 1:
                    issue.selected_sha = None
                    for variant in variants:
                        variant.review_status = "pending"
                        variant.revision_conflict = True
    session.execute(
        insert(SourceLocation)
        .values(
            document_sha=sha,
            root_id=root_id,
            relative_path=relative_path,
            categories=[p for p in Path(relative_path).parts[:-1] if p in ("all", "half", "fail")],
        )
        .on_conflict_do_nothing()
    )
    session.flush()
    return sha, new


def import_folder(sessions, root: Path, expected_count=None):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("PDF source must be a directory")
    root_id = hashlib.sha256(str(root).encode()).hexdigest()
    # pathlib.rglob suppresses permission errors, silently omitting documents.
    with os.scandir(root):
        pass
    directory_errors = []
    files = sorted(
        Path(folder) / filename
        for folder, _, filenames in os.walk(
            root, followlinks=False, onerror=directory_errors.append
        )
        for filename in filenames
        if Path(filename).suffix.lower() == ".pdf"
    )
    summary = dict(
        id=str(uuid.uuid4()),
        found=len(files),
        imported=0,
        skipped=0,
        failed=len(directory_errors),
        recommendations=0,
        needs_review=0,
        files=[
            dict(
                path=str(Path(e.filename).relative_to(root)),
                status="failed",
                code="source_directory_unreadable",
                error=type(e).__name__,
            )
            for e in directory_errors
        ],
        warnings=[],
    )
    if expected_count is not None and len(files) != expected_count:
        summary["warnings"].append(
            dict(code="file_count_mismatch", expected=expected_count, actual=len(files))
        )
    if not files:
        summary["warnings"].append(dict(code="no_pdf_files"))
    with sessions.begin() as session:
        session.add(ImportRun(id=summary["id"], started_at=datetime.now(UTC), summary={}))
    for path in files:
        relative = str(path.relative_to(root))
        event = dict(path=relative)
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Symlink/outside source rejected")
            with path.open("rb") as stream:
                data = stream.read(50 * 1024 * 1024 + 1)
            if len(data) > 50 * 1024 * 1024:
                raise ValueError("PDF exceeds size limit")
            sha = hashlib.sha256(data).hexdigest()
            with sessions() as session:
                existing = session.get(Document, sha)
                previous_failed = existing is not None and existing.extraction_status == "failed"
                seen = existing is not None
            extraction = Extraction()
            failed = previous_failed
            if not seen:
                try:
                    extraction = extract_pdf(data)
                except ValueError as exc:
                    failed = True
                    extraction.flags.append(dict(code="extraction_error", error=type(exc).__name__))
            with sessions.begin() as session:
                sha, new = persist(session, data, extraction, root_id, relative, failed=failed)
            event["sha256"] = sha
            if failed:
                summary["failed"] += 1
                event.update(status="failed", error="ValueError", flags=extraction.flags)
            elif new:
                summary["imported"] += 1
                summary["recommendations"] += len(extraction.recommendations)
                summary["needs_review"] += 1
                event.update(
                    status="imported",
                    recommendations=len(extraction.recommendations),
                    review_status="pending",
                    flags=extraction.flags,
                    recommendation_flags=[r.flags for r in extraction.recommendations],
                )
            else:
                summary["skipped"] += 1
                event["status"] = "skipped_duplicate"
        except Exception as exc:
            summary["failed"] += 1
            event.update(status="failed", error=type(exc).__name__)
        summary["files"].append(event)
    with sessions.begin() as session:
        run = session.get(ImportRun, summary["id"])
        run.finished_at = datetime.now(UTC)
        run.summary = summary
    return summary
