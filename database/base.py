import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DB_URL,
    echo=False,
    connect_args={"timeout": 30.0} if "sqlite" in settings.DB_URL else {}
)

# Enable WAL mode for SQLite to eliminate locking issues
if "sqlite" in settings.DB_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add transaction_type column if missing (existing databases)
        if "sqlite" in settings.DB_URL:
            try:
                await conn.execute(
                    __import__("sqlalchemy", fromlist=["text"]).text(
                        "ALTER TABLE expenses ADD COLUMN transaction_type TEXT NOT NULL DEFAULT 'expense'"
                    )
                )
            except Exception:
                pass  # Column already exists
    logger.info("Database tables initialized successfully with WAL mode.")

