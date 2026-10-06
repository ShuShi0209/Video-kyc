import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from core.database import get_db
import models
import schemas
from api import get_attempt, validate_state_transition, raise_error, create_audit_event, utc_now

router = APIRouter(prefix="/api/v1")

# 40. Evidence Package
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/evidence", response_model=schemas.EvidenceCreateResponse)
def create_evidence(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    validate_state_transition(attempt.current_step, "HUMAN_REVIEW") # EVIDENCE_PACKAGE_CREATED -> HUMAN_REVIEW
    
    evidence = db.query(models.EvidencePackage).filter(models.EvidencePackage.attempt_id == attempt_id).first()
    if not evidence:
        evidence = models.EvidencePackage(
            attempt_id=attempt_id,
            status="CREATED"
        )
        db.add(evidence)
        db.flush()
        
    attempt.current_step = "HUMAN_REVIEW"
    db.query(models.VideoSession).filter(models.VideoSession.id == session_id).update({"current_step": "HUMAN_REVIEW"})
    create_audit_event(db, attempt.video_session.case_id, "EVIDENCE_CREATED", "SYSTEM", session_id, attempt_id)
    db.commit()
    db.refresh(evidence)
    
    return schemas.EvidenceCreateResponse(
        evidence_id=evidence.id,
        attempt_id=attempt_id,
        status=evidence.status,
        created_at=evidence.created_at,
        next_step="HUMAN_REVIEW"
    )

# 41. Get Evidence
@router.get("/video-sessions/{session_id}/attempts/{attempt_id}/evidence", response_model=schemas.EvidenceGetResponse)
def get_evidence(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    evidence = db.query(models.EvidencePackage).filter(models.EvidencePackage.attempt_id == attempt_id).first()
    if not evidence:
        raise_error(404, "NOT_FOUND", "Evidence package not found.")
        
    recording = db.query(models.Recording).filter(models.Recording.attempt_id == attempt_id).first()
    face = db.query(models.FaceResult).filter(models.FaceResult.attempt_id == attempt_id).first()
    liveness = db.query(models.LivenessResult).filter(models.LivenessResult.attempt_id == attempt_id).first()
    q_count = db.query(func.count(models.AttemptQuestion.id)).filter(models.AttemptQuestion.attempt_id == attempt_id).scalar()
    d_count = db.query(func.count(models.DocumentCapture.id)).filter(models.DocumentCapture.attempt_id == attempt_id).scalar()
    
    return schemas.EvidenceGetResponse(
        evidence_id=evidence.id,
        attempt_id=attempt_id,
        status=evidence.status,
        recording=schemas.AvailableFlag(available=bool(recording)),
        face=schemas.AvailableFlag(available=bool(face)),
        liveness=schemas.AvailableFlag(available=bool(liveness)),
        questions=schemas.CountFlag(count=q_count),
        documents=schemas.CountFlag(count=d_count)
    )

# 42. Human Review Queue
@router.get("/reviews", response_model=schemas.ReviewListResponse)
def list_reviews(db: Session = Depends(get_db)):
    # Any attempt in HUMAN_REVIEW
    attempts = db.query(models.Attempt).filter(models.Attempt.current_step == "HUMAN_REVIEW").all()
    reviews = []
    for att in attempts:
        evidence = db.query(models.EvidencePackage).filter(models.EvidencePackage.attempt_id == att.id).first()
        if evidence:
            review = db.query(models.Review).filter(models.Review.attempt_id == att.id).first()
            if not review:
                review = models.Review(
                    attempt_id=att.id,
                    evidence_id=evidence.id,
                    status="PENDING"
                )
                db.add(review)
                db.flush()
            reviews.append(schemas.ReviewListItem(
                review_id=review.id,
                case_id=att.video_session.case_id,
                session_id=att.session_id,
                attempt_id=att.id,
                status=review.status,
                created_at=review.created_at
            ))
    db.commit()
    return schemas.ReviewListResponse(reviews=reviews)

# 43. Get Review
@router.get("/reviews/{review_id}", response_model=schemas.ReviewGetResponse)
def get_review(review_id: uuid.UUID, db: Session = Depends(get_db)):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise_error(404, "NOT_FOUND", "Review not found.")
        
    return schemas.ReviewGetResponse(
        review_id=review.id,
        case_id=review.attempt.video_session.case_id,
        attempt_id=review.attempt_id,
        status=review.status,
        evidence_id=review.evidence_id
    )

# 44. Approve Review
@router.post("/reviews/{review_id}/approve", response_model=schemas.ReviewApproveResponse)
def approve_review(review_id: uuid.UUID, payload: schemas.ReviewApproveRequest, db: Session = Depends(get_db)):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise_error(404, "NOT_FOUND", "Review not found.")
        
    attempt = review.attempt
    validate_state_transition(attempt.current_step, "VERIFIED")
    
    review.decision = "APPROVED"
    review.status = "COMPLETED"
    review.notes = payload.notes
    review.completed_at = utc_now()
    
    attempt.current_step = "VERIFIED"
    attempt.status = "COMPLETED"
    attempt.completed_at = utc_now()
    
    session = attempt.video_session
    session.current_step = "VERIFIED"
    session.status = "COMPLETED"
    session.completed_at = utc_now()
    
    case = session.kyc_case
    case.status = "VERIFIED"
    case.completed_at = utc_now()
    
    create_audit_event(db, case.id, "REVIEW_APPROVED", "USER", session.id, attempt.id)
    db.commit()
    
    return schemas.ReviewApproveResponse(
        review_id=review.id,
        decision="APPROVED",
        attempt_id=attempt.id,
        case_status="VERIFIED"
    )

# 45. Retry Review
@router.post("/reviews/{review_id}/retry", response_model=schemas.ReviewRetryResponse)
def retry_review(review_id: uuid.UUID, payload: schemas.ReviewRetryRequest, db: Session = Depends(get_db)):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise_error(404, "NOT_FOUND", "Review not found.")
        
    attempt = review.attempt
    validate_state_transition(attempt.current_step, "STARTED") # Transition HUMAN_REVIEW -> STARTED (new attempt)
    
    review.decision = "RETRY"
    review.status = "COMPLETED"
    review.notes = payload.reason
    review.completed_at = utc_now()
    
    attempt.status = "REVIEWED"
    
    session = attempt.video_session
    
    new_attempt = models.Attempt(
        session_id=session.id,
        attempt_number=attempt.attempt_number + 1,
        status="IN_PROGRESS",
        current_step="STARTED"
    )
    db.add(new_attempt)
    db.flush()
    
    session.current_step = "STARTED"
    
    create_audit_event(db, session.case_id, "REVIEW_REJECTED_RETRY", "USER", session.id, attempt.id)
    create_audit_event(db, session.case_id, "ATTEMPT_CREATED", "SYSTEM", session.id, new_attempt.id)
    db.commit()
    db.refresh(new_attempt)
    
    return schemas.ReviewRetryResponse(
        review_id=review.id,
        decision="RETRY",
        previous_attempt_id=attempt.id,
        new_attempt_id=new_attempt.id,
        new_attempt_number=new_attempt.attempt_number,
        status="IN_PROGRESS",
        current_step="STARTED"
    )

# 47. Attempt History
@router.get("/video-sessions/{session_id}/attempts", response_model=schemas.AttemptListResponse)
def list_attempts(session_id: uuid.UUID, db: Session = Depends(get_db)):
    attempts = db.query(models.Attempt).filter(models.Attempt.session_id == session_id).order_by(models.Attempt.attempt_number.asc()).all()
    res = []
    for att in attempts:
        rev = db.query(models.Review).filter(models.Review.attempt_id == att.id).first()
        res.append(schemas.AttemptListItem(
            attempt_id=att.id,
            attempt_number=att.attempt_number,
            status=att.status,
            review_decision=rev.decision if rev else None
        ))
    return schemas.AttemptListResponse(attempts=res)

# 48. Audit Events
@router.get("/video-sessions/{session_id}/attempts/{attempt_id}/audit", response_model=schemas.AuditEventListResponse)
def get_audit_events(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    events = db.query(models.AuditEvent).filter(models.AuditEvent.attempt_id == attempt_id).order_by(models.AuditEvent.created_at.asc()).all()
    res = []
    for ev in events:
        res.append(schemas.AuditEventItem(
            event_type=ev.event_type,
            timestamp=ev.created_at,
            actor_type=ev.actor_type
        ))
    return schemas.AuditEventListResponse(events=res)
