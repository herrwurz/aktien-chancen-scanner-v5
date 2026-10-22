"""Only the explicitly configured disposable CI PostgreSQL may be written by setup."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import sessionmaker
from test_backtest_report import AS_OF, add_recommendation

from scanner.hebeltrader.historical_cli import main
from scanner.hebeltrader.models import Document, HistoricalRecommendation


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_v15_audit_postgres_118_only_select_and_read_only_transaction(tmp_path, monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    identifiers = []
    with sessions.begin() as session:
        for index in range(118):
            doc, _ = add_recommendation(session, index + 50000)
            identifiers.append(doc.sha256)
    with sessions() as session:
        count = session.scalar(select(func.count()).select_from(HistoricalRecommendation))
    statements = []

    def capture(c, u, statement, p, x, m):
        statements.append(statement.strip().upper())

    try:
        event.listen(engine, "before_cursor_execute", capture)
        monkeypatch.setattr("scanner.hebeltrader.historical_cli.create_db", lambda _: engine)
        assert (
            main(
                [
                    "audit",
                    "--as-of",
                    AS_OF.isoformat(),
                    "--run-at",
                    AS_OF.isoformat(),
                    "--expected-count",
                    str(count),
                    "--output-prefix",
                    str(tmp_path / "report"),
                ]
            )
            == 0
        )
        assert "SET TRANSACTION READ ONLY" in statements
        assert all(s.startswith(("SELECT", "SET TRANSACTION READ ONLY")) for s in statements)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        with sessions.begin() as session:
            assert (
                session.scalar(select(func.count()).select_from(HistoricalRecommendation)) == count
            )
            session.execute(delete(Document).where(Document.sha256.in_(identifiers)))
        engine.dispose()
