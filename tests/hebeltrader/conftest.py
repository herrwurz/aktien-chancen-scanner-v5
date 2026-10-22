import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scanner.models import Base


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()
