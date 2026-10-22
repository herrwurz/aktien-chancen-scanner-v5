import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from scanner.hebeltrader.analysis import export_features, review_document
from scanner.hebeltrader.importer import import_folder
from scanner.hebeltrader.models import (
    Document,
    HistoricalRecommendation,
    ImportRun,
    Publication,
    SourceLocation,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "hebeltrader"


def copy_pdf(root, filename="complete.pdf", destination="all/sample.pdf"):
    target = root / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / filename, target)
    return target


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_repeated_import_and_copied_sources_are_idempotent(sessions, tmp_path):
    copy_pdf(tmp_path)
    first = import_folder(sessions, tmp_path)
    assert first["imported"] == 1 and first["recommendations"] == 1
    second = import_folder(sessions, tmp_path)
    assert second["skipped"] == 1 and second["imported"] == 0
    copy_pdf(tmp_path, destination="fail/renamed.PDF")
    third = import_folder(sessions, tmp_path)
    assert third["skipped"] == 2
    with sessions() as s:
        assert (
            count(s, Document) == count(s, Publication) == count(s, HistoricalRecommendation) == 1
        )
        assert count(s, SourceLocation) == 2
        assert {tuple(x.categories) for x in s.scalars(select(SourceLocation))} == {
            ("all",),
            ("fail",),
        }
        r = s.scalar(select(HistoricalRecommendation))
        document = s.get(Document, r.document_sha)
        assert document.original_pdf == (FIXTURES / "complete.pdf").read_bytes()
        assert r.evidence["entry_price"][0]["page"] == 1
        assert document.review_status == "pending"
        assert count(s, ImportRun) == 3


def test_changed_pdf_same_issue_is_explicit_revision_conflict(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        original = s.scalar(select(Document))
        review_document(s, original.sha256, "approve", "tester", "Checked original against source")
    # Different bytes/contents, same publication identity.
    copy_pdf(tmp_path, "incomplete.pdf", "half/revision.pdf")
    result = import_folder(sessions, tmp_path)
    assert result["imported"] == 1
    with sessions() as s:
        assert count(s, Publication) == 1
        assert count(s, Document) == 2
        assert s.scalar(select(Publication)).selected_sha is None
        assert all(d.review_status == "pending" for d in s.scalars(select(Document)))
        assert all(d.revision_conflict for d in s.scalars(select(Document)))
        assert export_features(s, datetime(2026, 1, 1, tzinfo=UTC)) == []


def test_broken_and_scan_files_do_not_block_valid_file(sessions, tmp_path):
    copy_pdf(tmp_path)
    copy_pdf(tmp_path, "broken.pdf", "bad.pdf")
    copy_pdf(tmp_path, "scan.pdf", "scan.pdf")
    result = import_folder(sessions, tmp_path)
    assert result["found"] == 3 and result["failed"] == 1 and result["imported"] == 2
    assert result["recommendations"] == 1
    assert any(e.get("error") == "ValueError" for e in result["files"])
    with sessions() as s:
        assert count(s, Document) == 3
        assert s.scalar(select(Document).where(Document.extraction_status == "failed")).original_pdf


def test_features_require_manual_review_and_conservative_time(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        doc = s.scalar(select(Document))
        assert export_features(s, datetime(2026, 1, 1, tzinfo=UTC)) == []
        review_document(
            s, doc.sha256, "approve", "tester", "Source checked; optional gaps accepted"
        )
        # 2025-02-15 00:00 Berlin equals 2025-02-14 23:00 UTC.
        assert export_features(s, datetime(2025, 2, 14, 22, 59, tzinfo=UTC)) == []
        rows = export_features(s, datetime(2025, 2, 14, 23, 0, tzinfo=UTC))
        assert len(rows) == 1
        assert rows[0]["features"]["entry_price"] == "1.250000000000000000"
        assert (
            not {"categories", "review_status", "outcomes", "imported_at"}
            & rows[0]["features"].keys()
        )
        assert rows[0]["source_sha256"] == doc.sha256
        assert rows[0]["availability_assumption"] == "end_of_publication_day_Europe_Berlin"


def test_missing_publication_date_never_exported(sessions, tmp_path):
    copy_pdf(tmp_path, "no_date.pdf")
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        doc = s.scalar(select(Document))
        with pytest.raises(ValueError):
            review_document(s, doc.sha256, "approve", "tester", "Cannot invent date")
        assert export_features(s, datetime(2026, 1, 1, tzinfo=UTC)) == []


def test_unresolved_document_can_be_rejected(sessions, tmp_path):
    copy_pdf(tmp_path, "no_date.pdf")
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        doc = s.scalar(select(Document))
        review_document(s, doc.sha256, "reject", "tester", "Publication date cannot be established")
        assert doc.review_status == "rejected"


def test_conflicting_header_dates_still_invalidate_same_issue(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        review_document(s, s.scalar(select(Document)).sha256, "approve", "tester", "Checked")
    copy_pdf(tmp_path, "metadata_conflict.pdf", "conflict.pdf")
    import_folder(sessions, tmp_path)
    with sessions() as s:
        assert count(s, Publication) == 1
        assert s.scalar(select(Publication)).selected_sha is None


def test_symlink_cannot_import_outside_source_folder(sessions, tmp_path):
    outside = tmp_path / "private.pdf"
    shutil.copyfile(FIXTURES / "complete.pdf", outside)
    root = tmp_path / "source"
    root.mkdir()
    (root / "link.pdf").symlink_to(outside)
    result = import_folder(sessions, root)
    assert result["failed"] == 1
    with sessions() as s:
        assert count(s, Document) == 0


@pytest.mark.skipif(os.geteuid() == 0, reason="Root bypasses Unix mode bits")
def test_unreadable_source_is_not_reported_as_empty(sessions, tmp_path):
    root = tmp_path / "unreadable"
    root.mkdir()
    root.chmod(0)
    try:
        with pytest.raises(PermissionError):
            import_folder(sessions, root)
    finally:
        root.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="Root bypasses Unix mode bits")
def test_unreadable_subdirectory_is_reported(sessions, tmp_path):
    copy_pdf(tmp_path)
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    hidden.chmod(0)
    try:
        result = import_folder(sessions, tmp_path)
        assert result["imported"] == 1
        assert result["failed"] == 1
        assert any(f.get("code") == "source_directory_unreadable" for f in result["files"])
    finally:
        hidden.chmod(0o700)
