import pytest
from sqlalchemy.orm import Session
from models import KycCase, Document, VideoSession, Attempt
from core.database import SessionLocal, engine, Base

@pytest.fixture(scope="module")
def db():
    # Setup test DB tables (they should already exist from Alembic, but good practice)
    # We will just use the existing test DB from the session
    session = SessionLocal()
    yield session
    # We rollback after the test to leave DB clean
    session.rollback()
    session.close()

def test_create_kyc_case_and_relationships(db: Session):
    # Create KycCase
    case = KycCase(status="IN_PROGRESS")
    db.add(case)
    db.commit()
    db.refresh(case)
    assert case.id is not None
    assert case.status == "IN_PROGRESS"

    # Create Document
    doc = Document(
        case_id=case.id,
        document_type="ID",
        filename="test.jpg",
        mime_type="image/jpeg",
        storage_key="test/test.jpg",
        sequence_number=1
    )
    db.add(doc)

    # Create VideoSession
    session = VideoSession(
        case_id=case.id,
        status="STARTED",
        current_step="STARTED"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Create Attempt
    attempt = Attempt(
        session_id=session.id,
        attempt_number=1,
        status="IN_PROGRESS",
        current_step="FACE"
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Verify relationships
    assert len(case.documents) == 1
    assert case.documents[0].filename == "test.jpg"
    assert len(case.video_sessions) == 1
    assert case.video_sessions[0].status == "STARTED"
    assert len(session.attempts) == 1
    assert session.attempts[0].current_step == "FACE"
    assert attempt.video_session.id == session.id

    # Clean up (Optional, but good practice)
    db.delete(case)
    db.commit()
