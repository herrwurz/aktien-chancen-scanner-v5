from contextlib import contextmanager

from sqlalchemy import create_engine, text
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


def create_sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def worker_lock(engine):
    """Use a dedicated physical connection; release before returning it to the pool."""
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
        connection.commit()
        try:
            yield bool(acquired)
        finally:
            if acquired:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                connection.commit()
