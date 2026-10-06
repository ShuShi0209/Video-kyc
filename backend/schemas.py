from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from typing import Annotated, List, Literal, Optional, Any, Dict
from datetime import datetime, timezone
from uuid import UUID

def _as_utc(value: datetime) -> datetime:
    """Timestamps that arrive without a timezone are treated as UTC."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class ErrorDetails(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = {}

class ErrorResponse(BaseModel):
    error: ErrorDetails

class RetryInfo(BaseModel):
    allowed: bool
    retry_count: int
    max_retries: int

class DocumentInfo(BaseModel):
    id: UUID
    document_type: str
    filename: str
    
class RecordingStatusInfo(BaseModel):
    status: str

class SessionStartResponse(BaseModel):
    session_id: UUID
    attempt_id: UUID
    status: str
    current_step: str
    attempt_number: int
    recording: RecordingStatusInfo
    documents: List[DocumentInfo]

class RecordingStartRequest(BaseModel):
    started_at: UtcDatetime

class RecordingStartResponse(BaseModel):
    attempt_id: UUID
    recording_id: UUID
    status: str
    started_at: datetime

class RecordingStatusResponse(BaseModel):
    recording_id: UUID
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class RecordingUploadResponse(BaseModel):
    recording_id: UUID
    status: str
    mime_type: str
    size: int

class FaceDetectionRequest(BaseModel):
    detected: bool
    face_count: int = Field(ge=0, le=50)
    quality: float = Field(ge=0, le=1)
    timestamp: UtcDatetime

class FaceDetectionResponse(BaseModel):
    attempt_id: UUID
    step: str
    result: str
    next_step: str
    retry: RetryInfo
    message: Optional[str] = None

class LivenessRequest(BaseModel):
    status: Literal["PASS", "FAIL"]
    score: float = Field(ge=0, le=1)
    timestamp: UtcDatetime
    provider: Optional[str] = Field(default=None, max_length=64)

class LivenessResponse(BaseModel):
    attempt_id: UUID
    step: str
    result: str
    next_step: str
    retry: RetryInfo
    message: Optional[str] = None

class SessionStateResponse(BaseModel):
    session_id: UUID
    attempt_id: UUID
    status: str
    current_step: str
    attempt_number: int
    recording: RecordingStatusInfo

class AttemptStateResponse(BaseModel):
    attempt_id: UUID
    attempt_number: int
    status: str
    current_step: str
    retry_counts: Dict[str, int]

class QuestionBase(BaseModel):
    text: str
    category: str
    active: bool = True

class QuestionResponse(QuestionBase):
    id: UUID
    
class QuestionListResponse(BaseModel):
    questions: List[QuestionResponse]

class QuestionConfigRequest(BaseModel):
    question_count: int = Field(gt=0)
    random_selection: bool = True

class CurrentQuestionInfo(BaseModel):
    id: UUID
    sequence_number: int
    text: str

class CurrentQuestionDetailInfo(CurrentQuestionInfo):
    total_questions: int

class QuestionStartResponse(BaseModel):
    attempt_id: UUID
    current_step: str
    total_questions: int
    current_question: Optional[CurrentQuestionInfo] = None

class CurrentQuestionResponse(BaseModel):
    question: Optional[CurrentQuestionDetailInfo] = None

class AnswerSubmitRequest(BaseModel):
    transcript: str
    audio_duration_ms: int

class AnswerEvaluation(BaseModel):
    understood: bool
    relevant: bool

class AnswerSubmitResponse(BaseModel):
    question_id: UUID
    answer_id: UUID
    transcript: Optional[str] = None
    evaluation: Optional[AnswerEvaluation] = None
    next_question: Optional[CurrentQuestionInfo] = None
    completed: Optional[bool] = False
    next_step: Optional[str] = None

class ConversationAudioResponse(BaseModel):
    transcript: str
    duration_ms: int

class TTSRequest(BaseModel):
    text: str

class TTSResponse(BaseModel):
    audio_url: str
    content_type: str

class DocumentPresentationDocument(BaseModel):
    id: UUID
    document_type: str
    display_name: str
    sequence_number: int
    total_documents: int

class DocumentPresentationResponse(BaseModel):
    document: Optional[DocumentPresentationDocument] = None
    instruction: Optional[str] = None

class NextDocumentInfo(BaseModel):
    id: UUID
    document_type: str
    sequence_number: int

class DocumentCaptureRejectReason(BaseModel):
    code: str
    message: str

class DocumentCaptureResponse(BaseModel):
    capture_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    status: str
    next_document: Optional[NextDocumentInfo] = None
    completed: Optional[bool] = False
    next_step: Optional[str] = None
    reason: Optional[DocumentCaptureRejectReason] = None
    retry: Optional[RetryInfo] = None

class RecordingStopRequest(BaseModel):
    ended_at: UtcDatetime

class RecordingStopResponse(BaseModel):
    recording_id: UUID
    status: str
    ended_at: datetime
    next_step: str

class EvidenceCreateResponse(BaseModel):
    evidence_id: UUID
    attempt_id: UUID
    status: str
    created_at: datetime
    next_step: str

class AvailableFlag(BaseModel):
    available: bool

class CountFlag(BaseModel):
    count: int

class EvidenceGetResponse(BaseModel):
    evidence_id: UUID
    attempt_id: UUID
    status: str
    recording: AvailableFlag
    face: AvailableFlag
    liveness: AvailableFlag
    questions: CountFlag
    documents: CountFlag

class ReviewListItem(BaseModel):
    review_id: UUID
    case_id: UUID
    session_id: Optional[UUID] = None
    attempt_id: UUID
    status: str
    created_at: datetime

class ReviewListResponse(BaseModel):
    reviews: List[ReviewListItem]

class ReviewGetResponse(BaseModel):
    review_id: UUID
    case_id: UUID
    attempt_id: UUID
    status: str
    evidence_id: UUID

class ReviewApproveRequest(BaseModel):
    notes: Optional[str] = None

class ReviewApproveResponse(BaseModel):
    review_id: UUID
    decision: str
    attempt_id: UUID
    case_status: str

class ReviewRetryRequest(BaseModel):
    reason: str

class ReviewRetryResponse(BaseModel):
    review_id: UUID
    decision: str
    previous_attempt_id: UUID
    new_attempt_id: UUID
    new_attempt_number: int
    status: str
    current_step: str

class AttemptListItem(BaseModel):
    attempt_id: UUID
    attempt_number: int
    status: str
    review_decision: Optional[str] = None

class AttemptListResponse(BaseModel):
    attempts: List[AttemptListItem]

class AuditEventItem(BaseModel):
    event_type: str
    timestamp: datetime
    actor_type: str

class AuditEventListResponse(BaseModel):
    events: List[AuditEventItem]

