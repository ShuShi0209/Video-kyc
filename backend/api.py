import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

import models
import schemas
from core.config import settings
from core.database import get_db
from core.errors import ApiError
from core.storage import StorageError, StorageLimitExceeded, get_storage

logger = logging.getLogger("video_kyc.api")

router = APIRouter(prefix="/api/v1")

# Steps in which a session is still being captured live. A session that is further along
# (evidence packaged, waiting for human review) is never abandoned automatically.
LIVE_STEPS = {
    "STARTED", "FACE", "LIVENESS", "GENERAL_QUESTIONS",
    "DOCUMENT_PRESENTATION", "DOCUMENT_CAPTURE", "RECORDING_COMPLETE",
}

# Recording media rules (API_CONTRACT: the backend must not trust the filename or MIME type the browser sends).
ALLOWED_RECORDING_MIME = {"video/webm": "webm", "video/mp4": "mp4"}
ACCEPTED_DECLARED_MIME = set(ALLOWED_RECORDING_MIME) | {"application/octet-stream"}

FACE_MESSAGES = {
    "NO_FACE": "No face detected. Please position your face inside the camera view.",
    "MULTIPLE_FACES": "More than one face detected. Please make sure only you are in front of the camera.",
    "LOW_QUALITY": "We could not see your face clearly. Please improve the lighting and look straight at the camera.",
}


def utc_now():
    return datetime.now(timezone.utc)


def raise_error(status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
    raise ApiError(status_code, code, message, details)


def _invalid_state(current_step: str, requested_step: str):
    raise_error(
        409, "INVALID_STATE",
        f"{requested_step} cannot be submitted during the current KYC step.",
        {"current_step": current_step, "requested_step": requested_step},
    )


def validate_state_transition(current_step: str, requested_step: str):
    transitions = {
        "STARTED": ["FACE"],
        "FACE": ["FACE", "LIVENESS"],
        "LIVENESS": ["LIVENESS", "GENERAL_QUESTIONS"],
        "GENERAL_QUESTIONS": ["GENERAL_QUESTIONS", "DOCUMENT_PRESENTATION"],
        "DOCUMENT_PRESENTATION": ["DOCUMENT_CAPTURE"],
        "DOCUMENT_CAPTURE": ["DOCUMENT_CAPTURE", "DOCUMENT_PRESENTATION", "RECORDING_COMPLETE"],
        "RECORDING_COMPLETE": ["EVIDENCE_PACKAGE_CREATED"],
        "EVIDENCE_PACKAGE_CREATED": ["HUMAN_REVIEW"],
        "HUMAN_REVIEW": ["VERIFIED", "STARTED"],
    }
    if requested_step not in transitions.get(current_step, []):
        _invalid_state(current_step, requested_step)


def require_step(attempt: models.Attempt, step: str):
    """A submission for ``step`` is only valid while the attempt is exactly at that step."""
    if attempt.current_step != step:
        _invalid_state(attempt.current_step, step)


def get_session(db: Session, session_id: uuid.UUID) -> models.VideoSession:
    db_session = db.query(models.VideoSession).filter(models.VideoSession.id == session_id).first()
    if not db_session:
        raise_error(404, "SESSION_NOT_FOUND", "The requested session was not found.")
    return db_session


def get_attempt(
    db: Session,
    attempt_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
    lock: bool = False,
) -> models.Attempt:
    """Load an attempt. When ``session_id`` is given the attempt must belong to that session.

    ``lock=True`` takes a row lock so concurrent requests for the same attempt are serialised
    (retry counters, one-recording-per-attempt, no double uploads).
    """
    if session_id is not None:
        get_session(db, session_id)
    query = db.query(models.Attempt).filter(models.Attempt.id == attempt_id)
    if lock:
        query = query.with_for_update()
    attempt = query.first()
    if not attempt or (session_id is not None and attempt.session_id != session_id):
        raise_error(404, "ATTEMPT_NOT_FOUND", "The requested attempt was not found.")
    return attempt


def create_audit_event(
    db: Session,
    case_id: uuid.UUID,
    event_type: str,
    actor_type: str = "SYSTEM",
    session_id: Optional[uuid.UUID] = None,
    attempt_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    event = models.AuditEvent(
        case_id=case_id,
        session_id=session_id,
        attempt_id=attempt_id,
        event_type=event_type,
        actor_type=actor_type,
        metadata_=metadata,
    )
    db.add(event)
    return event


def set_step(attempt: models.Attempt, step: str) -> None:
    """Move the attempt, and the session that mirrors it, to a new workflow step."""
    attempt.current_step = step
    attempt.video_session.current_step = step


def _case_id(attempt: models.Attempt) -> uuid.UUID:
    return attempt.video_session.case_id


def _latest_attempt(db: Session, session_id: uuid.UUID) -> Optional[models.Attempt]:
    return (
        db.query(models.Attempt)
        .filter(models.Attempt.session_id == session_id)
        .order_by(models.Attempt.attempt_number.desc())
        .first()
    )


def _get_recording(db: Session, attempt_id: uuid.UUID) -> Optional[models.Recording]:
    return (
        db.query(models.Recording)
        .filter(models.Recording.attempt_id == attempt_id)
        .order_by(models.Recording.created_at.desc())
        .first()
    )


def _count_results(db: Session, model, attempt_id: uuid.UUID) -> int:
    return db.query(func.count(model.id)).filter(model.attempt_id == attempt_id).scalar() or 0


def _fail_attempt(attempt: models.Attempt) -> None:
    """Terminal policy for an exhausted retry limit: the attempt is closed as FAILED.

    The workflow step is left untouched (the frontend must not invent states) and further
    submissions are answered with RETRY_LIMIT_REACHED until the user starts a new session.
    """
    attempt.status = "FAILED"
    attempt.completed_at = utc_now()


def _guard_retryable_step(db: Session, attempt: models.Attempt, step: str, model, max_retries: int) -> int:
    """Shared guards for steps with automatic retries. Returns how many results are already stored."""
    require_step(attempt, step)
    count = _count_results(db, model, attempt.id)
    if count >= max_retries:
        raise_error(
            409, "RETRY_LIMIT_REACHED", f"Maximum {step.lower()} retries reached.",
            {"retry_count": count, "max_retries": max_retries},
        )
    if attempt.status != "IN_PROGRESS":
        raise_error(
            409, "INVALID_STATE", "This attempt is no longer active.",
            {"current_step": attempt.current_step, "attempt_status": attempt.status},
        )
    return count


# ----------------------------------------------------------------------------- sessions

def _is_pristine(db: Session, session: models.VideoSession) -> bool:
    """True when nothing has happened in the session yet, so it can safely be handed out again."""
    attempt = _latest_attempt(db, session.id)
    return (
        session.current_step == "STARTED"
        and attempt is not None
        and attempt.status == "IN_PROGRESS"
        and attempt.current_step == "STARTED"
        and _get_recording(db, attempt.id) is None
    )


def _abandon_session(db: Session, session: models.VideoSession, reason: str) -> None:
    now = utc_now()
    session.status = "CANCELLED"
    session.completed_at = now
    latest = _latest_attempt(db, session.id)
    for attempt in session.attempts:
        if attempt.status in ("CREATED", "IN_PROGRESS", "RETRYING"):
            attempt.status = "FAILED"
            attempt.completed_at = now
        for recording in attempt.recordings:
            if recording.status in ("RECORDING", "STOPPING"):
                recording.status = "FAILED"
                recording.ended_at = recording.ended_at or now
    create_audit_event(
        db, session.case_id, "SESSION_ABANDONED", "SYSTEM", session.id,
        latest.id if latest else None, {"reason": reason},
    )


# 12. Start Video KYC
@router.post("/kyc-cases/{case_id}/video-sessions", status_code=201, response_model=schemas.SessionStartResponse)
def start_video_session(case_id: uuid.UUID, response: Response, db: Session = Depends(get_db)):
    # Lock the case so two concurrent starts cannot both create a session.
    case = db.query(models.KycCase).filter(models.KycCase.id == case_id).with_for_update().first()
    if not case:
        raise_error(404, "NOT_FOUND", "The requested KYC case was not found.")
    if case.status in ("VERIFIED", "CLOSED"):
        raise_error(409, "INVALID_STATE", "This KYC case is already verified or closed.", {"case_status": case.status})

    active = (
        db.query(models.VideoSession)
        .filter(models.VideoSession.case_id == case.id, models.VideoSession.status == "IN_PROGRESS")
        .order_by(models.VideoSession.created_at.desc())
        .all()
    )
    past_capture = next((s for s in active if s.current_step not in LIVE_STEPS), None)
    if past_capture:
        raise_error(
            409, "INVALID_STATE", "A video KYC session for this case is already past live capture.",
            {"session_id": str(past_capture.id), "current_step": past_capture.current_step},
        )

    # A session where nothing happened yet is handed out again (duplicate requests, double clicks,
    # React StrictMode). Anything else is abandoned: a reloaded browser has lost its in-memory
    # recording, so the old attempt cannot be continued.
    reusable = next((s for s in active if _is_pristine(db, s)), None)
    for stale in active:
        if stale is not reusable:
            _abandon_session(db, stale, "NEW_SESSION_REQUESTED")

    if reusable is not None:
        session = reusable
        attempt = _latest_attempt(db, session.id)
        response.status_code = 200
    else:
        session = models.VideoSession(case_id=case.id, status="IN_PROGRESS", current_step="STARTED")
        db.add(session)
        db.flush()
        attempt = models.Attempt(session_id=session.id, attempt_number=1, status="IN_PROGRESS", current_step="STARTED")
        db.add(attempt)
        db.flush()
        create_audit_event(db, case.id, "SESSION_CREATED", "SYSTEM", session.id, attempt.id)
        create_audit_event(db, case.id, "ATTEMPT_CREATED", "SYSTEM", session.id, attempt.id)

    case.status = "IN_PROGRESS"
    db.commit()

    documents = sorted(case.documents, key=lambda d: d.sequence_number)
    return schemas.SessionStartResponse(
        session_id=session.id,
        attempt_id=attempt.id,
        status=session.status,
        current_step=attempt.current_step,
        attempt_number=attempt.attempt_number,
        recording=schemas.RecordingStatusInfo(status="NOT_STARTED"),
        documents=[schemas.DocumentInfo(id=d.id, document_type=d.document_type, filename=d.filename) for d in documents],
    )


# ----------------------------------------------------------------------------- recording

def _start_response(attempt: models.Attempt, recording: models.Recording) -> schemas.RecordingStartResponse:
    return schemas.RecordingStartResponse(
        attempt_id=attempt.id, recording_id=recording.id, status=recording.status, started_at=recording.started_at,
    )


def _base_mime(value: Optional[str]) -> str:
    """'video/webm;codecs=vp9,opus' -> 'video/webm'."""
    return (value or "application/octet-stream").split(";")[0].strip().lower()


def sniff_recording_mime(head: bytes) -> Optional[str]:
    """Identify the container from its first bytes instead of trusting the browser."""
    if head[:4] == b"\x1a\x45\xdf\xa3":  # EBML header: WebM / Matroska
        return "video/webm"
    if len(head) >= 12 and head[4:8] == b"ftyp":  # ISO base media: MP4 (Safari)
        return "video/mp4"
    return None


def _advance_after_recording(attempt: models.Attempt, recording: models.Recording) -> None:
    """Once the last step is done and the recording is both uploaded and stopped, evidence can be packaged."""
    if (
        recording.status == "COMPLETED"
        and recording.ended_at is not None
        and attempt.current_step == "RECORDING_COMPLETE"
    ):
        set_step(attempt, "EVIDENCE_PACKAGE_CREATED")


@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/recording/start", response_model=schemas.RecordingStartResponse)
def start_recording(session_id: uuid.UUID, attempt_id: uuid.UUID, payload: schemas.RecordingStartRequest, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id, lock=True)
    recording = _get_recording(db, attempt.id)

    if recording is not None:
        if recording.status == "RECORDING":
            return _start_response(attempt, recording)  # duplicate start: one active recording per attempt
        raise_error(
            409, "INVALID_STATE", "A recording already exists for this attempt and is no longer active.",
            {"recording_status": recording.status},
        )
    if attempt.status != "IN_PROGRESS" or attempt.current_step != "STARTED":
        raise_error(
            409, "INVALID_STATE", "The recording can only be started at the beginning of an active attempt.",
            {"current_step": attempt.current_step, "attempt_status": attempt.status},
        )

    recording = models.Recording(
        attempt_id=attempt.id, storage_key="", mime_type="video/webm", file_size=0,
        status="RECORDING", started_at=payload.started_at,
    )
    db.add(recording)
    set_step(attempt, "FACE")  # state machine: STARTED --recording ready--> FACE
    create_audit_event(db, _case_id(attempt), "RECORDING_STARTED", "SYSTEM", session_id, attempt.id)
    db.commit()
    db.refresh(recording)
    return _start_response(attempt, recording)


@router.get("/video-sessions/{session_id}/attempts/{attempt_id}/recording", response_model=schemas.RecordingStatusResponse)
def get_recording_status(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    recording = _get_recording(db, attempt.id)
    if not recording:
        raise_error(404, "NOT_FOUND", "Recording not found.")
    return schemas.RecordingStatusResponse(
        recording_id=recording.id, status=recording.status, started_at=recording.started_at, ended_at=recording.ended_at,
    )


@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/recording", response_model=schemas.RecordingUploadResponse)
def upload_recording(session_id: uuid.UUID, attempt_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id, lock=True)
    recording = _get_recording(db, attempt.id)
    if not recording:
        raise_error(404, "NOT_FOUND", "Recording not found. Start the recording before uploading it.")
    if recording.status not in ("RECORDING", "STOPPING"):
        # Never overwrite evidence that was already stored.
        raise_error(
            409, "INVALID_STATE", "This recording cannot accept an upload in its current state.",
            {"recording_status": recording.status},
        )

    declared = _base_mime(file.content_type)
    if declared not in ACCEPTED_DECLARED_MIME:
        raise_error(
            415, "MEDIA_UPLOAD_FAILED", "Unsupported recording type.",
            {"reason": "UNSUPPORTED_MEDIA_TYPE", "received": declared, "allowed": sorted(ALLOWED_RECORDING_MIME)},
        )

    detected: Dict[str, str] = {}

    def check_head(chunk: bytes) -> None:
        if not chunk:
            raise ApiError(422, "MEDIA_UPLOAD_FAILED", "The uploaded recording is empty.", {"reason": "EMPTY_FILE"})
        mime = sniff_recording_mime(chunk)
        if mime is None:
            raise ApiError(422, "MEDIA_UPLOAD_FAILED", "The uploaded file is not a readable video recording.", {"reason": "UNREADABLE_MEDIA"})
        detected["mime"] = mime

    storage = get_storage()
    staging_key = f"recordings/{attempt.id}/recording.upload"
    try:
        size = storage.save_stream(staging_key, file.file, settings.MAX_UPLOAD_BYTES, check_head)
    except StorageLimitExceeded:
        raise_error(
            413, "MEDIA_UPLOAD_FAILED", "The recording is too large.",
            {"reason": "FILE_TOO_LARGE", "max_bytes": settings.MAX_UPLOAD_BYTES},
        )
    except StorageError:
        logger.exception("Could not store recording for attempt %s", attempt.id)
        raise_error(500, "MEDIA_UPLOAD_FAILED", "The recording could not be stored.", {"reason": "STORAGE_ERROR"})

    # The stored name and MIME type come from the sniffed container, never from the browser's filename.
    final_mime = detected["mime"]
    key = f"recordings/{attempt.id}/recording.{ALLOWED_RECORDING_MIME[final_mime]}"
    try:
        storage.move(staging_key, key)
    except OSError:
        logger.exception("Could not finalise recording for attempt %s", attempt.id)
        storage.delete(staging_key)
        raise_error(500, "MEDIA_UPLOAD_FAILED", "The recording could not be stored.", {"reason": "STORAGE_ERROR"})

    recording.status = "COMPLETED"
    recording.mime_type = final_mime
    recording.file_size = size
    recording.storage_key = key
    create_audit_event(
        db, _case_id(attempt), "RECORDING_UPLOADED", "SYSTEM", session_id, attempt.id,
        {"size": size, "mime_type": final_mime},
    )
    _advance_after_recording(attempt, recording)
    try:
        db.commit()
    except Exception:
        storage.delete(key)
        raise
    return schemas.RecordingUploadResponse(recording_id=recording.id, status=recording.status, mime_type=final_mime, size=size)


@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/recording/stop", response_model=schemas.RecordingStopResponse)
def stop_recording(session_id: uuid.UUID, attempt_id: uuid.UUID, payload: schemas.RecordingStopRequest, db: Session = Depends(get_db)):
    """Close the recording. This never skips workflow steps: the attempt only advances to
    EVIDENCE_PACKAGE_CREATED when it already finished every step (RECORDING_COMPLETE) and the file is uploaded."""
    attempt = get_attempt(db, attempt_id, session_id, lock=True)
    recording = _get_recording(db, attempt.id)
    if not recording:
        raise_error(404, "NOT_FOUND", "Recording not found.")
    if recording.status == "FAILED":
        raise_error(409, "INVALID_STATE", "This recording failed and cannot be stopped.", {"recording_status": recording.status})

    if recording.ended_at is None:
        recording.ended_at = payload.ended_at
        if recording.status == "RECORDING":
            recording.status = "STOPPING"  # stopped, file not uploaded yet
        create_audit_event(db, _case_id(attempt), "RECORDING_STOPPED", "SYSTEM", session_id, attempt.id)
    # Calling stop again (retry after a lost response) is a no-op that returns the same state.

    _advance_after_recording(attempt, recording)
    db.commit()
    return schemas.RecordingStopResponse(
        recording_id=recording.id, status=recording.status, ended_at=recording.ended_at, next_step=attempt.current_step,
    )


# ----------------------------------------------------------------------------- face + liveness

def _evaluate_face(payload: schemas.FaceDetectionRequest) -> Optional[str]:
    """Return None when the face check passes, otherwise the reason it failed."""
    if not payload.detected or payload.face_count == 0:
        return "NO_FACE"
    if payload.face_count > 1:
        return "MULTIPLE_FACES"
    if payload.quality < settings.FACE_MIN_QUALITY:
        return "LOW_QUALITY"
    return None


# 17. Face Detection
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/face", response_model=schemas.FaceDetectionResponse)
def face_detection(session_id: uuid.UUID, attempt_id: uuid.UUID, payload: schemas.FaceDetectionRequest, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id, lock=True)
    max_retries = settings.max_retries_for("FACE")
    count = _guard_retryable_step(db, attempt, "FACE", models.FaceResult, max_retries)

    reason = _evaluate_face(payload)
    passed = reason is None
    db.add(models.FaceResult(
        attempt_id=attempt.id,
        detected=payload.detected,
        face_count=payload.face_count,
        quality_score=payload.quality,
        result="PASS" if passed else "FAIL",
        retry_count=count,  # retries that happened before this result (0 on the first try)
    ))
    case_id = _case_id(attempt)

    if passed:
        set_step(attempt, "LIVENESS")
        create_audit_event(db, case_id, "FACE_PASSED", "SYSTEM", session_id, attempt.id, {"quality": payload.quality, "retry_count": count})
        db.commit()
        return schemas.FaceDetectionResponse(
            attempt_id=attempt.id, step="FACE", result="PASS", next_step="LIVENESS",
            retry=schemas.RetryInfo(allowed=False, retry_count=count, max_retries=max_retries),
        )

    failures = count + 1
    allowed = failures < max_retries
    message = FACE_MESSAGES[reason]
    if not allowed:
        _fail_attempt(attempt)
        message = "We could not verify your face after several attempts. Please start a new session."
    create_audit_event(
        db, case_id, "FACE_FAILED", "SYSTEM", session_id, attempt.id,
        {"reason": reason, "retry_count": failures, "retry_limit_reached": not allowed},
    )
    db.commit()
    return schemas.FaceDetectionResponse(
        attempt_id=attempt.id, step="FACE", result="FAIL", next_step="FACE",
        retry=schemas.RetryInfo(allowed=allowed, retry_count=failures, max_retries=max_retries),
        message=message,
    )


# 18. Liveness
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/liveness", response_model=schemas.LivenessResponse)
def liveness(session_id: uuid.UUID, attempt_id: uuid.UUID, payload: schemas.LivenessRequest, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id, lock=True)
    max_retries = settings.max_retries_for("LIVENESS")
    count = _guard_retryable_step(db, attempt, "LIVENESS", models.LivenessResult, max_retries)

    passed = payload.status == "PASS" and payload.score >= settings.LIVENESS_MIN_SCORE
    db.add(models.LivenessResult(
        attempt_id=attempt.id,
        result="PASS" if passed else "FAIL",
        score=payload.score,
        retry_count=count,
        provider=payload.provider or "BROWSER",
    ))
    case_id = _case_id(attempt)

    if passed:
        set_step(attempt, "GENERAL_QUESTIONS")
        create_audit_event(db, case_id, "LIVENESS_PASSED", "SYSTEM", session_id, attempt.id, {"score": payload.score, "retry_count": count})
        db.commit()
        return schemas.LivenessResponse(
            attempt_id=attempt.id, step="LIVENESS", result="PASS", next_step="GENERAL_QUESTIONS",
            retry=schemas.RetryInfo(allowed=False, retry_count=count, max_retries=max_retries),
        )

    failures = count + 1
    allowed = failures < max_retries
    message = "Liveness check failed. Please follow the on-screen instruction and try again."
    if not allowed:
        _fail_attempt(attempt)
        message = "We could not complete the liveness check after several attempts. Please start a new session."
    create_audit_event(
        db, case_id, "LIVENESS_FAILED", "SYSTEM", session_id, attempt.id,
        {"score": payload.score, "retry_count": failures, "retry_limit_reached": not allowed},
    )
    db.commit()
    return schemas.LivenessResponse(
        attempt_id=attempt.id, step="LIVENESS", result="FAIL", next_step="LIVENESS",
        retry=schemas.RetryInfo(allowed=allowed, retry_count=failures, max_retries=max_retries),
        message=message,
    )


# ----------------------------------------------------------------------------- state

@router.get("/video-sessions/{session_id}", response_model=schemas.SessionStateResponse)
def get_current_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = get_session(db, session_id)
    attempt = _latest_attempt(db, session.id)
    if not attempt:
        raise_error(404, "ATTEMPT_NOT_FOUND", "The requested attempt was not found.")
    recording = _get_recording(db, attempt.id)
    return schemas.SessionStateResponse(
        session_id=session.id,
        attempt_id=attempt.id,
        status=session.status,
        current_step=attempt.current_step,  # the attempt is the source of truth for the workflow step
        attempt_number=attempt.attempt_number,
        recording=schemas.RecordingStatusInfo(status=recording.status if recording else "NOT_STARTED"),
    )


@router.get("/video-sessions/{session_id}/attempts/{attempt_id}", response_model=schemas.AttemptStateResponse)
def get_current_attempt(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    return schemas.AttemptStateResponse(
        attempt_id=attempt.id,
        attempt_number=attempt.attempt_number,
        status=attempt.status,
        current_step=attempt.current_step,
        retry_counts={
            "FACE": _count_results(db, models.FaceResult, attempt.id),
            "LIVENESS": _count_results(db, models.LivenessResult, attempt.id),
        },
    )


# 24. Question Configuration (POST)
@router.post("/questions", response_model=schemas.QuestionResponse)
def create_question(payload: schemas.QuestionBase, db: Session = Depends(get_db)):
    q = models.Question(**payload.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return q

# 25. List Questions (GET)
@router.get("/questions", response_model=schemas.QuestionListResponse)
def list_questions(active: Optional[bool] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Question)
    if active is not None:
        query = query.filter(models.Question.active == active)
    if category is not None:
        query = query.filter(models.Question.category == category)
    questions = query.all()
    return schemas.QuestionListResponse(questions=questions)

# 26. Configure Question Count
@router.put("/question-config", response_model=schemas.QuestionConfigRequest)
def configure_question_count(payload: schemas.QuestionConfigRequest, db: Session = Depends(get_db)):
    config = db.query(models.QuestionConfig).first()
    if not config:
        config = models.QuestionConfig(**payload.model_dump())
        db.add(config)
    else:
        config.question_count = payload.question_count
        config.random_selection = payload.random_selection
    db.commit()
    return payload
