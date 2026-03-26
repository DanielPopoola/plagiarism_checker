from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)


def _force_utc_session_timezone(dbapi_connection, _connection_record) -> None:
    """Keep DB session timezone pinned to UTC across host OS differences."""
    if "sqlite" in settings.database_url:
        return
    cursor = dbapi_connection.cursor()
    try:
        if settings.database_url.startswith("postgresql"):
            cursor.execute("SET TIME ZONE 'UTC'")
        elif settings.database_url.startswith("mysql"):
            cursor.execute("SET time_zone = '+00:00'")
    finally:
        cursor.close()


event.listen(engine, "connect", _force_utc_session_timezone)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
