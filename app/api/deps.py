from app.db.session import SessionLocal


def get_db():
    """
    FastAPI dependency that yields a DB session and always closes it,
    even if the request handler raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()