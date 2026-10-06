import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, BigInteger, Numeric, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class KycCase(Base):
    __tablename__ = "kyc_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    documents = relationship("Document", back_populates="kyc_case", cascade="all, delete-orphan")
    video_sessions = relationship("VideoSession", back_populates="kyc_case", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="kyc_case")

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("kyc_cases.id"), nullable=False, index=True)
    document_type = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    kyc_case = relationship("KycCase", back_populates="documents")

class VideoSession(Base):
    __tablename__ = "video_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("kyc_cases.id"), nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    current_step = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    kyc_case = relationship("KycCase", back_populates="video_sessions")
    attempts = relationship("Attempt", back_populates="video_session", cascade="all, delete-orphan")

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("video_sessions.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)
    current_step = Column(String, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('session_id', 'attempt_number', name='uq_attempt_session_number'),
    )

    video_session = relationship("VideoSession", back_populates="attempts")
    recordings = relationship("Recording", back_populates="attempt", cascade="all, delete-orphan")
    face_results = relationship("FaceResult", back_populates="attempt", cascade="all, delete-orphan")
    liveness_results = relationship("LivenessResult", back_populates="attempt", cascade="all, delete-orphan")
    attempt_questions = relationship("AttemptQuestion", back_populates="attempt", cascade="all, delete-orphan")
    document_captures = relationship("DocumentCapture", back_populates="attempt", cascade="all, delete-orphan")
    evidence_package = relationship("EvidencePackage", back_populates="attempt", uselist=False, cascade="all, delete-orphan")

class Recording(Base):
    __tablename__ = "recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    storage_key = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    attempt = relationship("Attempt", back_populates="recordings")

class FaceResult(Base):
    __tablename__ = "face_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    detected = Column(Boolean, nullable=False)
    face_count = Column(Integer, nullable=False)
    quality_score = Column(Numeric, nullable=True)
    result = Column(String, nullable=False)
    retry_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    attempt = relationship("Attempt", back_populates="face_results")

class LivenessResult(Base):
    __tablename__ = "liveness_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    result = Column(String, nullable=False)
    score = Column(Numeric, nullable=True)
    retry_count = Column(Integer, nullable=False)
    provider = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    attempt = relationship("Attempt", back_populates="liveness_results")

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(String, nullable=False)
    category = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

class QuestionConfig(Base):
    __tablename__ = "question_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_count = Column(Integer, nullable=False)
    random_selection = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('attempt_id', 'sequence_number', name='uq_attempt_question_sequence'),
    )

    attempt = relationship("Attempt", back_populates="attempt_questions")
    question = relationship("Question")
    answers = relationship("Answer", back_populates="attempt_question", cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_question_id = Column(UUID(as_uuid=True), ForeignKey("attempt_questions.id"), nullable=False, index=True)
    transcript = Column(String, nullable=False)
    audio_storage_key = Column(String, nullable=True)
    audio_duration_ms = Column(Integer, nullable=True)
    understood = Column(Boolean, nullable=True)
    relevant = Column(Boolean, nullable=True)
    evaluation_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    attempt_question = relationship("AttemptQuestion", back_populates="answers")

class DocumentCapture(Base):
    __tablename__ = "document_captures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    storage_key = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False)
    quality_score = Column(Numeric, nullable=True)
    retry_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    attempt = relationship("Attempt", back_populates="document_captures")
    document = relationship("Document")

class EvidencePackage(Base):
    __tablename__ = "evidence_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    attempt = relationship("Attempt", back_populates="evidence_package")
    reviews = relationship("Review", back_populates="evidence_package", cascade="all, delete-orphan")

class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=False, index=True)
    evidence_id = Column(UUID(as_uuid=True), ForeignKey("evidence_packages.id"), nullable=False)
    status = Column(String, nullable=False, index=True)
    decision = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    reviewer_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    attempt = relationship("Attempt")
    evidence_package = relationship("EvidencePackage", back_populates="reviews")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("kyc_cases.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("video_sessions.id"), nullable=True, index=True)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("attempts.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    kyc_case = relationship("KycCase", back_populates="audit_events")
    video_session = relationship("VideoSession")
    attempt = relationship("Attempt")
