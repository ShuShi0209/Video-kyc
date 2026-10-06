import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config import settings
from core.database import engine, get_db
from main import app


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Tests must not depend on the developer's .env or write into the real storage directory."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "MAX_RETRIES", 3)
    monkeypatch.setattr(settings, "FACE_MAX_RETRIES", None)
    monkeypatch.setattr(settings, "LIVENESS_MAX_RETRIES", None)
    monkeypatch.setattr(settings, "FACE_MIN_QUALITY", 0.5)
    monkeypatch.setattr(settings, "LIVENESS_MIN_SCORE", 0.5)
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 5 * 1024 * 1024)


@pytest.fixture()
def db():
    """A session inside a transaction that is rolled back afterwards: tests never leave rows behind."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()  # like a real request: whatever was not committed is discarded

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
