import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from scanner.db import worker_lock
from scanner.models import Base


def migrate(url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    command.check(cfg)
    command.downgrade(cfg, "base")
    assert "market_candles" not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    engine.dispose()


def test_migration_roundtrip_sqlite(tmp_path, monkeypatch):
    migrate(f"sqlite:///{tmp_path}/migration.db", monkeypatch)


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_postgres_migrations_persistence_and_lock(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    migrate(url, monkeypatch)
    engine = create_engine(url)
    # Each connection uses the same database; lock must exclude concurrent workers.
    with worker_lock(engine) as first:
        assert first
        with worker_lock(engine) as second:
            assert not second
    with worker_lock(engine) as third:
        assert third
    from datetime import timedelta

    from test_domain import START, candle

    from scanner.detector import VolumeDetector
    from scanner.service import ingest

    sessions = sessionmaker(engine)
    for _ in range(2):
        with sessions.begin() as session:
            ingest(
                session,
                [candle(0), candle(1, "40")],
                VolumeDetector(lookback=1),
                START + timedelta(hours=1),
            )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM market_candles")) == 2
        assert connection.scalar(text("SELECT count(*) FROM signals")) == 1
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE scan_runs, market_candles CASCADE"))
    engine.dispose()


@pytest.mark.postgres
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Disposable PostgreSQL not configured"
)
def test_lock_connection_loss_prevents_old_worker_writes(monkeypatch):
    import asyncio

    from sqlalchemy.exc import SQLAlchemyError
    from test_domain import candle

    from scanner.db import create_sessions
    from scanner.detector import VolumeDetector
    from scanner.service import scan_once

    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    with worker_lock(engine) as locked_connection:
        # The active worker must use this exact lock-owning connection.
        sessions = create_sessions(locked_connection, require_lock=True)
        pid = locked_connection.scalar(text("SELECT pg_backend_pid()"))
        locked_connection.commit()

        class Provider:
            name = "fixture"
            asset_class = "crypto"

            async def fetch_candles(self, symbol, interval, **kwargs):
                with engine.begin() as other:
                    assert other.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
                # Another worker can now acquire the released lock.
                with worker_lock(engine) as another:
                    assert another
                return [candle(0), candle(1, "40")]

        with pytest.raises((SQLAlchemyError, RuntimeError)):
            asyncio.run(
                scan_once(sessions, Provider(), ["BTCUSDT"], ["5m"], VolumeDetector(lookback=1))
            )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM market_candles")) == 0
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE scan_runs, market_candles CASCADE"))
    engine.dispose()
