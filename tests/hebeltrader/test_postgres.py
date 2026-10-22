import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from scanner.hebeltrader.importer import import_folder
from scanner.hebeltrader.models import Document, HistoricalRecommendation


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_postgres_pdf_import_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE hebel_publications, hebel_import_runs CASCADE"))
    fixture = Path(__file__).parents[1] / "fixtures/hebeltrader/complete.pdf"
    shutil.copyfile(fixture, tmp_path / "test.pdf")
    sessions = sessionmaker(engine)
    assert import_folder(sessions, tmp_path)["imported"] == 1
    assert import_folder(sessions, tmp_path)["skipped"] == 1
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Document)) == 1
        assert s.scalar(select(HistoricalRecommendation)).entry_price == Decimal("1.25")
    engine.dispose()


def test_upgrade_preserves_existing_market_history(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/upgrade.db"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO scan_runs (provider,started_at,status,error_count,errors) "
                "VALUES ('fixture','2025-01-01 00:00:00','ok',0,'[]')"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM scan_runs")) == 1
        assert conn.scalar(text("SELECT count(*) FROM hebel_documents")) == 0
    engine.dispose()
