from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

LOCK_ID = 684906061


def create_db(settings):
    return create_engine(
        settings.db_url(),
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 5,
        }
        if str(settings.db_url()).startswith("postgresql")
        else {},
    )


def create_sessions(engine, *, require_lock=False):
    sessions = sessionmaker(engine, expire_on_commit=False)
    if require_lock and engine.dialect.name == "postgresql":

        @event.listens_for(sessions, "after_begin")
        def verify_lock(session, transaction, connection):
            # Check on this same connection before writes, including after reconnect.
            held = connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                    "AND pid = pg_backend_pid() AND classid = 0 AND objid = :key "
                    "AND objsubid = 1 AND granted)"
                ),
                {"key": LOCK_ID},
            )
            if not held:
                raise RuntimeError("Worker advisory lock lost")

    return sessions


@contextmanager
def worker_lock(engine):
    """Yield the lock-owning connection, or None when another worker holds it."""
    if engine.dialect.name != "postgresql":
        yield engine
        return
    with engine.connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
        connection.commit()
        try:
            yield connection if acquired else None
        finally:
            if acquired and not connection.invalidated:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                connection.commit()
