from alembic import context

from scanner.config import Settings
from scanner.db import create_db
from scanner.models import Base

target_metadata = Base.metadata


def run_migrations_online():
    engine = create_db(Settings())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    context.configure(url=Settings().db_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
