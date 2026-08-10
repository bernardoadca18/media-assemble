"""
Configuração de engine/sessão assíncrona do SQLAlchemy, usada por todo o
projeto para acessar o Postgres.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
