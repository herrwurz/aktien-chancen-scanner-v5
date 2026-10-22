"""These tests require the explicitly configured, disposable test database."""

import json
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import sessionmaker
from test_backtest_report import AS_OF, add_recommendation

from scanner.hebeltrader.coverage_cli import main
from scanner.hebeltrader.models import Document, HistoricalOutcome, HistoricalRecommendation


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_coverage_118_read_only_postgres(tmp_path, monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    identifiers = []
    with sessions.begin() as session:
        for index in range(118):
            doc, rec = add_recommendation(session, index + 10000)
            identifiers.append(doc.sha256)
    try:
        with sessions() as session:
            before = session.scalar(select(func.count()).select_from(HistoricalOutcome))
        with sessions() as session:
            expected = session.scalar(select(func.count()).select_from(HistoricalRecommendation))
        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.strip().upper())

        event.listen(engine, "before_cursor_execute", capture)
        monkeypatch.setattr("scanner.hebeltrader.coverage_cli.create_db", lambda settings: engine)
        mapping = tmp_path / "mapping.json"
        mapping.write_text("{}")
        output = tmp_path / "inventory"
        assert (
            main(
                [
                    "--map",
                    str(mapping),
                    "--as-of",
                    AS_OF.isoformat(),
                    "--run-at",
                    AS_OF.isoformat(),
                    "--expected-count",
                    str(expected),
                    "--output-prefix",
                    str(output),
                ]
            )
            == 0
        )
        assert "SET TRANSACTION READ ONLY" in statements
        assert all(s.startswith(("SELECT", "SET TRANSACTION READ ONLY")) for s in statements)
        event.remove(engine, "before_cursor_execute", capture)
        report = json.loads(output.with_suffix(".json").read_text())
        own = [r for r in report["results"] if r["document_sha"] in identifiers]
        assert len(own) == 118
        assert all(not r["training_eligible"] for r in own)
        assert all(len(r["blockers"]) >= 4 for r in own)
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(HistoricalOutcome)) == before
            assert (
                len(
                    list(
                        session.scalars(
                            select(HistoricalRecommendation).where(
                                HistoricalRecommendation.document_sha.in_(identifiers)
                            )
                        )
                    )
                )
                == 118
            )
            assert set(
                session.scalars(
                    select(Document.review_status).where(Document.sha256.in_(identifiers))
                )
            ) == {"pending"}
    finally:
        with sessions.begin() as session:
            session.execute(delete(Document).where(Document.sha256.in_(identifiers)))
        engine.dispose()
