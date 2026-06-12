# tests/conftest.py

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from medbox.api.main import app
from medbox.core.db.base import Base
from medbox.core.db.session import get_session

# Tous les modules qui font `from medbox.core.db.session import async_session_local`
# doivent être patchés individuellement (la référence est copiée à l'import-time).
_SESSION_MODULES = [
    "medbox.core.db.session",
    "medbox.core.db.repositories.base",
    "medbox.core.db.repositories.global_medication",
    "medbox.core.db.repositories.patient",
    "medbox.core.db.repositories.user",
    "medbox.core.db.repositories.tenant",
    "medbox.core.db.repositories.invitation",
    "medbox.core.db.repositories.prescription",
    "medbox.core.db.repositories.box",
    "medbox.core.db.repositories.wheel",
    "medbox.core.db.repositories.prescription_schedule_item",
    "medbox.core.db.repositories.wheel_load_plan",
    "medbox.core.services.wheel_load_plan",
]


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Session SQLite in-memory partagée entre tous les repositories.

    StaticPool force une seule connexion → tous les AsyncSession créés par
    async_session_local (patché) voient les mêmes données.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patcher async_session_local dans chaque module qui l'a importé
    patches = []
    for module_path in _SESSION_MODULES:
        p = patch(f"{module_path}.async_session_local", test_session_maker)
        try:
            p.start()
            patches.append(p)
        except AttributeError:
            pass  # module ne l'importe pas

    try:
        async with test_session_maker() as session:
            yield session
    finally:
        for p in patches:
            p.stop()
        await engine.dispose()


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Fixture pour AsyncClient avec DB session override."""

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
