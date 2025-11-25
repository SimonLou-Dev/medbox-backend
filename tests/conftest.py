# tests/conftest.py

import asyncio
import pytest

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from medbox.core.config.settings import settings
from medbox.core.db.base import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


@pytest.fixture
async def test_session():
    """
    DB SQLite in-memory. Pour tester l'encryption, ça suffit.
    Pas de Postgres -> moins de friction.
    """

    engine = create_async_engine(settings.get_async_db_url(), future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
