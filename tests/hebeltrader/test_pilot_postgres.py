"""A disposable CI database is seeded by tests; the pilot transaction itself is read-only."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from test_backtest_report import add_recommendation

from scanner.hebeltrader.models import Document, HistoricalRecommendation
from scanner.hebeltrader.pilot import build_pilot_report
from scanner.hebeltrader.pilot_cli import main


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_pilot_postgres_originals_unchanged_and_server_transaction_is_readonly(
    tmp_path, monkeypatch
):
    url = os.environ["TEST_DATABASE_URL"]
    if not (make_url(url).database or "").endswith("_test"):
        pytest.skip("Pilot regression requires an explicitly disposable _test database")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        doc, _ = add_recommendation(session, 170001)
        identifier = doc.sha256
    with sessions() as session:
        before = session.scalar(select(func.count()).select_from(HistoricalRecommendation))
    statements = []

    def capture(c, u, statement, p, x, m):
        statements.append(statement.strip().upper())

    def checked(session, **kwargs):
        assert session.scalar(text("SELECT current_setting('transaction_read_only')")) == "on"
        return build_pilot_report(session, **kwargs)

    try:
        event.listen(engine, "before_cursor_execute", capture)
        monkeypatch.setattr("scanner.hebeltrader.pilot_cli.create_db", lambda _: engine)
        monkeypatch.setattr("scanner.hebeltrader.pilot_cli.build_pilot_report", checked)
        assert (
            main(
                [
                    "run",
                    "--synthetic",
                    "--document-sha",
                    identifier,
                    "--run-at",
                    "2026-10-22T12:00:00+00:00",
                    "--output-prefix",
                    str(tmp_path / "pilot"),
                ]
            )
            == 2
        )
        assert "SET TRANSACTION READ ONLY" in statements
        assert all(s.startswith(("SELECT", "SET TRANSACTION READ ONLY")) for s in statements)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        with sessions.begin() as session:
            assert (
                session.scalar(select(func.count()).select_from(HistoricalRecommendation)) == before
            )
            assert session.get(Document, identifier) is not None
            session.execute(delete(Document).where(Document.sha256 == identifier))
        engine.dispose()
