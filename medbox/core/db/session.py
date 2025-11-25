from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from medbox.core.config.settings import settings

engine = create_async_engine(settings.database_url, future=True)

async_session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

async def get_session() -> AsyncGenerator[AsyncSession | Any, Any]:
    async with async_session_local() as session:
        yield session