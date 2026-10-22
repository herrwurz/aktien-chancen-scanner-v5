from decimal import Decimal

from sqlalchemy import func, select
from test_import import copy_pdf

from scanner.hebeltrader.analysis import review_document
from scanner.hebeltrader.importer import import_folder
from scanner.hebeltrader.models import Document, HistoricalRecommendation, ReviewEvent
from scanner.hebeltrader.quality import preview_database


def test_reimport_preserves_reviewed_old_extraction(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        doc = s.scalar(select(Document))
        doc.extractor_version = "hebeltrader-rules-v1"
        review_document(s, doc.sha256, "approve", "tester", "Original checked")
        rec = s.scalar(select(HistoricalRecommendation))
        rec.entry_price = Decimal("1.25")
        original_id = rec.id
        sha = doc.sha256
    for _ in range(2):
        assert import_folder(sessions, tmp_path)["skipped"] == 1
    with sessions() as s:
        doc = s.get(Document, sha)
        rec = s.scalar(select(HistoricalRecommendation))
        assert doc.review_status == "approved"
        assert doc.extractor_version == "hebeltrader-rules-v1"
        assert rec.entry_price == Decimal("1.25") and rec.id == original_id
        assert s.scalar(select(func.count()).select_from(ReviewEvent)) == 1


def test_quality_replay_does_not_change_stored_data(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        doc = s.scalar(select(Document))
        doc.extractor_version = "hebeltrader-rules-v1"
        doc.review_status = "rejected"
        rec = s.scalar(select(HistoricalRecommendation))
        rec.crv = None
        rec.evidence = {k: v for k, v in rec.evidence.items() if k != "_calculated_crv"}
    with sessions() as s:
        report = preview_database(s)
        assert report["before"]["fields"]["crv"]["missing"] == 1
        assert report["after"]["fields"]["crv"]["missing"] == 0
        assert report["after"]["computed_crv"]["derivative_target1"] == 1
    with sessions() as s:
        assert s.scalar(select(HistoricalRecommendation)).crv is None
        assert s.scalar(select(Document)).review_status == "rejected"
        assert s.scalar(select(Document)).extractor_version == "hebeltrader-rules-v1"
