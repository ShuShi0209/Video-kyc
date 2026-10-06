import uuid
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from core.database import get_db
import models
import schemas
from api import get_attempt, validate_state_transition, raise_error, create_audit_event

router = APIRouter(prefix="/api/v1")

# 34. Document Presentation
@router.get("/video-sessions/{session_id}/attempts/{attempt_id}/documents/current", response_model=schemas.DocumentPresentationResponse)
def get_current_document(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    # validate_state_transition handles transition, here we just check if we are in valid state
    # Wait, getting current state doesn't change state. Just return current doc.
    docs = db.query(models.Document).filter(models.Document.case_id == attempt.video_session.case_id).order_by(models.Document.sequence_number.asc()).all()
    if not docs:
        raise_error(404, "NOT_FOUND", "No documents associated with this case.")
        
    captures = db.query(models.DocumentCapture).filter(
        models.DocumentCapture.attempt_id == attempt_id,
        models.DocumentCapture.status == "CAPTURED"
    ).all()
    captured_ids = [c.document_id for c in captures]
    
    current_doc = None
    for doc in docs:
        if doc.id not in captured_ids:
            current_doc = doc
            break
            
    if not current_doc:
        return schemas.DocumentPresentationResponse(document=None)
        
    return schemas.DocumentPresentationResponse(
        document=schemas.DocumentPresentationDocument(
            id=current_doc.id,
            document_type=current_doc.document_type,
            display_name=f"{current_doc.document_type} Document",
            sequence_number=current_doc.sequence_number,
            total_documents=len(docs)
        ),
        instruction="Please show the same document you uploaded."
    )

# 36. Document Capture
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/documents/{document_id}/capture", response_model=schemas.DocumentCaptureResponse)
def capture_document(session_id: uuid.UUID, attempt_id: uuid.UUID, document_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    validate_state_transition(attempt.current_step, "DOCUMENT_CAPTURE")
    
    count = db.query(func.count(models.DocumentCapture.id)).filter(
        models.DocumentCapture.attempt_id == attempt_id,
        models.DocumentCapture.document_id == document_id
    ).scalar()
    
    from core.config import settings
    max_retries = settings.MAX_RETRIES
    if count >= max_retries:
        raise_error(409, "RETRY_LIMIT_REACHED", "Maximum document capture retries reached.")
        
    # Assume success for V1
    capture = models.DocumentCapture(
        attempt_id=attempt_id,
        document_id=document_id,
        storage_key=f"captures/{attempt_id}/{document_id}.jpg",
        mime_type=file.content_type or "image/jpeg",
        file_size=1024,
        status="CAPTURED",
        retry_count=count + 1
    )
    db.add(capture)
    db.flush()
    
    docs = db.query(models.Document).filter(models.Document.case_id == attempt.video_session.case_id).order_by(models.Document.sequence_number.asc()).all()
    captures = db.query(models.DocumentCapture).filter(
        models.DocumentCapture.attempt_id == attempt_id,
        models.DocumentCapture.status == "CAPTURED"
    ).all()
    captured_ids = [c.document_id for c in captures]
    
    next_doc = None
    for doc in docs:
        if doc.id not in captured_ids:
            next_doc = doc
            break
            
    if next_doc:
        db.commit()
        return schemas.DocumentCaptureResponse(
            capture_id=capture.id,
            document_id=document_id,
            status="CAPTURED",
            next_document=schemas.NextDocumentInfo(
                id=next_doc.id,
                document_type=next_doc.document_type,
                sequence_number=next_doc.sequence_number
            )
        )
    else:
        attempt.current_step = "RECORDING_COMPLETE"
        db.query(models.VideoSession).filter(models.VideoSession.id == session_id).update({"current_step": "RECORDING_COMPLETE"})
        create_audit_event(db, attempt.video_session.case_id, "DOCUMENTS_CAPTURED", "SYSTEM", session_id, attempt_id)
        db.commit()
        return schemas.DocumentCaptureResponse(
            capture_id=capture.id,
            document_id=document_id,
            status="CAPTURED",
            completed=True,
            next_step="RECORDING_COMPLETE"
        )
