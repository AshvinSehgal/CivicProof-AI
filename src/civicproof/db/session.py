from civicproof.core.config import get_settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()
engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_database_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

async def close_database() -> None:
    await engine.dispose()