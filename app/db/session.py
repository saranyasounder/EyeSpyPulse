from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# The engine manages the actual connection pool to Postgres.
# Created once per process — not per request.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # checks connection is alive before using it
    echo=(settings.environment == "development"),  # logs SQL in dev only
)

# SessionLocal is a factory for creating new DB sessions.
# We call SessionLocal() once per request, not once globally.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base is what all your SQLAlchemy models will inherit from.
# It's how SQLAlchemy knows what tables to create/migrate.
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes. Yields a session, then always
    closes it — even if the request raised an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()