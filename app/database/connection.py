from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.discovery import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            for table, column in (
                ("discovery_jobs", "raw_candidates"),
                ("discovery_jobs", "candidates_checked"),
                ("discovery_jobs", "accepted_leads"),
                ("discovery_jobs", "rejected_candidates"),
                ("discovery_jobs", "duplicates"),
                ("discovery_jobs", "error_count"),
            ):
                columns = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
                existing = {row[1] for row in columns.fetchall()}
                if column not in existing:
                    await conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} INTEGER DEFAULT 0"
                    )


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
