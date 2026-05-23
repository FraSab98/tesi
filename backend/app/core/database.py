"""
Setup database con SQLAlchemy 2.0 async.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base per tutti i modelli ORM."""
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # Testa la connessione prima di usarla: evita "connection is closed"
    # quando il DB ha chiuso una connessione idle (tipico dopo test lunghi).
    pool_pre_ping=True,
    # Ricicla le connessioni dopo 5 minuti di vita (valore conservativo).
    pool_recycle=300,
    # Dimensioni pool moderate per dev locale
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency injection FastAPI per sessioni DB."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Inizializza lo schema del database (usa solo in dev)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
