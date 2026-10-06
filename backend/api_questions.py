import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from core.database import get_db
import models
import schemas
from api import get_attempt, validate_state_transition, raise_error, create_audit_event
import random

router = APIRouter(prefix="/api/v1")

# 27. Select Questions for Attempt
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/questions/start", response_model=schemas.QuestionStartResponse)
def start_questions(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    validate_state_transition(attempt.current_step, "GENERAL_QUESTIONS")
    
    # Check if already started
    existing = db.query(models.AttemptQuestion).filter(models.AttemptQuestion.attempt_id == attempt_id).order_by(models.AttemptQuestion.sequence_number.asc()).all()
    
    config = db.query(models.QuestionConfig).first()
    count = config.question_count if config else 3
    
    if not existing:
        questions = db.query(models.Question).filter(models.Question.active == True).all()
        if len(questions) < count:
            raise_error(500, "INTERNAL_ERROR", "Not enough active questions available.")
            
        selected = random.sample(questions, count)
        for i, q in enumerate(selected):
            aq = models.AttemptQuestion(attempt_id=attempt_id, question_id=q.id, sequence_number=i+1)
            db.add(aq)
        db.commit()
        existing = db.query(models.AttemptQuestion).filter(models.AttemptQuestion.attempt_id == attempt_id).order_by(models.AttemptQuestion.sequence_number.asc()).all()

    first_q = existing[0]
    return schemas.QuestionStartResponse(
        attempt_id=attempt_id,
        current_step="GENERAL_QUESTIONS",
        total_questions=count,
        current_question=schemas.CurrentQuestionInfo(
            id=first_q.question.id,
            sequence_number=first_q.sequence_number,
            text=first_q.question.text
        )
    )

# 28. Get Current Question
@router.get("/video-sessions/{session_id}/attempts/{attempt_id}/questions/current", response_model=schemas.CurrentQuestionResponse)
def get_current_question(session_id: uuid.UUID, attempt_id: uuid.UUID, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    aqs = db.query(models.AttemptQuestion).filter(models.AttemptQuestion.attempt_id == attempt_id).order_by(models.AttemptQuestion.sequence_number.asc()).all()
    if not aqs:
        raise_error(404, "NOT_FOUND", "No questions generated for this attempt.")
        
    total = len(aqs)
    current_aq = None
    for aq in aqs:
        if not db.query(models.Answer).filter(models.Answer.attempt_question_id == aq.id).first():
            current_aq = aq
            break
            
    if not current_aq:
        return schemas.CurrentQuestionResponse(question=None)
        
    return schemas.CurrentQuestionResponse(
        question=schemas.CurrentQuestionDetailInfo(
            id=current_aq.question.id,
            sequence_number=current_aq.sequence_number,
            total_questions=total,
            text=current_aq.question.text
        )
    )

# 29. Submit Answer
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/questions/{question_id}/answer", response_model=schemas.AnswerSubmitResponse)
def submit_answer(session_id: uuid.UUID, attempt_id: uuid.UUID, question_id: uuid.UUID, payload: schemas.AnswerSubmitRequest, db: Session = Depends(get_db)):
    attempt = get_attempt(db, attempt_id, session_id)
    validate_state_transition(attempt.current_step, "GENERAL_QUESTIONS")
    
    aqs = db.query(models.AttemptQuestion).filter(models.AttemptQuestion.attempt_id == attempt_id).order_by(models.AttemptQuestion.sequence_number.asc()).all()
    current_aq = None
    for aq in aqs:
        if not db.query(models.Answer).filter(models.Answer.attempt_question_id == aq.id).first():
            current_aq = aq
            break
            
    if not current_aq or current_aq.question_id != question_id:
        raise_error(409, "INVALID_STATE", "Not the current question.")
        
    ans = models.Answer(
        attempt_question_id=current_aq.id,
        transcript=payload.transcript,
        audio_duration_ms=payload.audio_duration_ms,
        understood=True,
        relevant=True
    )
    db.add(ans)
    db.flush()
    
    next_aq = None
    for aq in aqs:
        if aq.sequence_number == current_aq.sequence_number + 1:
            next_aq = aq
            break
            
    if next_aq:
        db.commit()
        return schemas.AnswerSubmitResponse(
            question_id=question_id,
            answer_id=ans.id,
            transcript=ans.transcript,
            evaluation=schemas.AnswerEvaluation(understood=True, relevant=True),
            next_question=schemas.CurrentQuestionInfo(
                id=next_aq.question.id,
                sequence_number=next_aq.sequence_number,
                text=next_aq.question.text
            )
        )
    else:
        attempt.current_step = "DOCUMENT_PRESENTATION"
        db.query(models.VideoSession).filter(models.VideoSession.id == session_id).update({"current_step": "DOCUMENT_PRESENTATION"})
        create_audit_event(db, attempt.video_session.case_id, "QUESTIONS_PASSED", "SYSTEM", session_id, attempt_id)
        db.commit()
        return schemas.AnswerSubmitResponse(
            question_id=question_id,
            answer_id=ans.id,
            completed=True,
            next_step="DOCUMENT_PRESENTATION"
        )

# 32. Conversation Audio / ASR
@router.post("/video-sessions/{session_id}/attempts/{attempt_id}/conversation/audio", response_model=schemas.ConversationAudioResponse)
def conversation_audio(session_id: uuid.UUID, attempt_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Mock ASR
    return schemas.ConversationAudioResponse(transcript="Simulated audio transcript", duration_ms=2000)

# 33. TTS
@router.post("/conversation/tts", response_model=schemas.TTSResponse)
def tts(payload: schemas.TTSRequest):
    return schemas.TTSResponse(audio_url="/api/v1/conversation/audio/tts_dummy", content_type="audio/mpeg")
