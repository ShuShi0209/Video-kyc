# Product Requirements Document (PRD)

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 Development Specification  
**Document:** `docs/PRD.md`

---

# 1. Product Overview

The AI-Assisted Video KYC system is a secure, recorded identity-verification workflow that allows a user to complete a Video KYC session for an existing KYC case.

The KYC case already contains documents uploaded by the user.

When the user clicks **Start Video KYC**, the system creates a new Video KYC session and verification attempt.

The system guides the user through:

1. Continuous video/audio recording
2. Face detection
3. Liveness / anti-spoofing
4. AI-driven general questions
5. Presentation of all previously uploaded documents
6. Camera-guided document capture
7. Evidence package creation
8. Human review
9. Approval or retry

The system is **AI-assisted, not AI-decided**.

The backend state machine controls the workflow, while the human reviewer makes the final KYC decision.

---

# 2. Product Principles

The following principles are mandatory:

1. The backend state machine is the source of truth.
2. The frontend must never be the source of truth for KYC state.
3. The LLM must never control the KYC workflow.
4. The LLM must never approve or reject a KYC case.
5. The human reviewer is the final decision maker.
6. The complete Video KYC session must be continuously recorded.
7. Every verification attempt must be independently auditable.
8. Previous attempts must never be deleted when a retry is created.
9. AI providers must be replaceable through provider abstractions.
10. Sensitive identity, biometric, audio, video, and document data must be protected.
11. Every important state transition and reviewer decision must be auditable.
12. Recoverable step failures should use bounded automatic retries within the current attempt.
13. A human-review retry creates a completely new verification attempt.

---

# 3. User Journey

The primary user journey is:

```text
EXISTING KYC CASE
        |
        | Uploaded Documents
        v
     STARTED
        |
        v
RECORDING STARTS
Camera + Microphone
        |
        v
      FACE
        |
        | Face Detection
        v
    LIVENESS
        |
        | Anti-Spoofing
        v
GENERAL QUESTIONS
        |
        | Randomly selected questions
        v
DOCUMENT PRESENTATION
        |
        | Show uploaded documents one by one
        v
CAMERA DOCUMENT FRAME
        |
        | Position document
        v
DOCUMENT CAPTURE
        |
        | Repeat for every uploaded document
        v
RECORDING STOPS
        |
        v
EVIDENCE PACKAGE
        |
        v
HUMAN REVIEW
        |
        +-------------------+
        |                   |
        v                   v
     APPROVE              RETRY
        |                   |
        v                   v
    VERIFIED           NEW ATTEMPT
                            |
                            v
                         STARTED
```

---

# 4. Existing KYC Case

Video KYC does not start from an empty case.

Before the Video KYC session begins, an existing KYC case must exist.

The case contains:

- User information
- Previously uploaded KYC documents
- Question configuration
- Video KYC configuration
- Other required KYC metadata

Conceptually:

```text
KYC Case
|
+-- User
|
+-- Uploaded Documents
|     |
|     +-- Document 1
|     +-- Document 2
|     +-- Document N
|
+-- Question Configuration
|
+-- Video KYC Configuration
|
+-- Case Status
```

The user starts Video KYC from this existing case.

---

# 5. Start Video KYC

When the user clicks:

```text
START VIDEO KYC
```

the backend must:

1. Validate the KYC case.
2. Verify that the case is eligible for Video KYC.
3. Verify that required uploaded documents exist.
4. Create a Video KYC session.
5. Create verification attempt #1.
6. Initialize the state machine.
7. Set the session state to `STARTED`.
8. Return the session and attempt information to the frontend.

Example conceptual response:

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "case_id": "case_001",
  "status": "STARTED",
  "current_step": "FACE"
}
```

The exact API contract will be defined separately in `API_CONTRACT.md`.

---

# 6. Video KYC Session and Attempts

A Video KYC session belongs to an existing KYC case.

A session contains one or more verification attempts.

```text
KYC CASE
|
+-- VIDEO KYC SESSION
      |
      +-- ATTEMPT 1
      |
      +-- ATTEMPT 2
      |
      +-- ATTEMPT N
```

An attempt represents one complete user verification run.

Each attempt contains its own:

- Continuous recording
- Face result
- Liveness result
- Questions and answers
- Document captures
- Evidence
- Audit information
- Review result

Previous attempts must remain available for audit.

---

# 7. Continuous Recording

Video KYC uses one continuous recording per attempt.

Recording begins when the Video KYC workflow starts.

```text
START RECORDING
      |
      v
FACE
      |
      v
LIVENESS
      |
      v
GENERAL QUESTIONS
      |
      v
DOCUMENT 1
      |
      v
DOCUMENT 2
      |
      v
DOCUMENT N
      |
      v
STOP RECORDING
```

The recording must cover the complete verification attempt.

The recording must not be restarted between normal workflow steps.

---

# 8. Camera and Microphone

The frontend must request:

- Camera permission
- Microphone permission

The frontend must display:

- Camera preview
- Recording status
- Current verification step
- Relevant instructions
- Errors
- Document frame when document capture is active

The frontend must clearly communicate whether recording is active.

The frontend must not control the backend verification state.

---

# 9. Face Verification — V1 Scope

V1 does not perform identity face matching.

The V1 face stage consists of:

```text
Camera
   |
   v
Face Detection
   |
   v
Face Quality / Presence
   |
   v
Liveness
```

V1 does not perform:

```text
Document Face
      |
      v
Face Embedding
      |
      v
Live Face Embedding
      |
      v
Identity Matching
```

Actual face matching will be considered in a future version.

---

# 10. Face Detection

The system must determine whether an appropriate face is visible in the camera stream.

The system should validate relevant face conditions such as:

- Face presence
- Face visibility
- Face positioning
- Basic image quality

If the face is not detected correctly, the user should receive a clear instruction.

Example:

```text
Please position your face inside the camera view.
```

---

# 11. Liveness / Anti-Spoofing

After successful face detection, the system performs liveness / anti-spoofing.

The purpose is to determine whether the camera feed represents a live user rather than an obvious spoofing attempt.

The liveness implementation must be isolated behind a provider/service abstraction.

Example:

```text
LivenessProvider
        |
        +-- start()
        +-- evaluate()
        +-- result()
```

The exact provider/model can be selected during implementation.

---

# 12. Step-Level Failure and Automatic Retry

A failure during an individual live-session step does not automatically create a new KYC attempt.

Recoverable failures use bounded automatic retries within the current attempt.

Example:

```text
LIVENESS
   |
   +-- PASS ---> NEXT STEP
   |
   +-- FAIL
        |
        v
     RETRY 1
        |
        +-- PASS ---> NEXT STEP
        |
        +-- FAIL
             |
             v
          RETRY 2
             |
             +-- PASS ---> NEXT STEP
             |
             +-- FAIL
                  |
                  v
               RETRY 3
```

The retry limit must be configurable.

Example configuration:

```text
MAX_STEP_RETRIES=3
```

The exact limit may vary by step.

Possible configuration:

```json
{
  "face": 3,
  "liveness": 3,
  "document_capture": 5
}
```

The backend decides whether another retry is allowed.

The frontend only displays the appropriate instruction.

---

# 13. General Questions

The system must support an administrator-configurable question pool.

The administrator can define a collection of questions for a KYC configuration.

Example:

```text
Question Pool

1. What is your full name?
2. What is your date of birth?
3. What is the purpose of this account?
4. What is your current occupation?
5. Where do you currently live?
6. What is your employer name?
7. What is your nationality?
8. ...
```

The administrator also specifies the number of questions to ask.

Example:

```text
Question Pool = 20 questions
Questions to ask = 5
```

The backend randomly selects 5 questions from the configured pool.

---

# 14. Question Selection

Question selection must happen on the backend.

The frontend must not decide which questions are selected.

The backend should:

1. Load the configured question pool.
2. Validate the requested question count.
3. Randomly select the required number of questions.
4. Store the selected question sequence for the attempt.
5. Ask the selected questions sequentially.

Example:

```text
Question Pool
20 questions
      |
      v
Backend Random Selection
      |
      v
Q7 → Q2 → Q15 → Q19 → Q4
```

The selected sequence must remain fixed for that attempt.

A retry that creates a new attempt may generate a new question sequence.

---

# 15. AI Conversation Flow

The question interaction follows:

```text
AI asks question
       |
       v
User speaks
       |
       v
ASR
       |
       v
LLM
       |
       +-- Understand answer
       +-- Extract answer
       +-- Evaluate semantic response
       |
       v
Backend Question Engine
       |
       v
Next Question
```

The AI should provide a natural conversational experience.

The LLM may:

- Understand spoken responses
- Extract the user's answer
- Interpret natural language
- Identify whether the response addresses the question
- Produce structured answer information

The LLM must not:

- Advance the KYC state machine
- Select arbitrary workflow states
- Approve the KYC case
- Reject the KYC case
- Decide whether the complete KYC session is verified

The backend remains responsible for workflow control.

---

# 16. ASR

Automatic speech recognition converts user speech into text.

V1 uses:

```text
Provider: Groq
Model: whisper-large-v3
```

The ASR component must be isolated behind an ASR provider interface.

Conceptually:

```text
ASRProvider
      |
      +-- transcribe(audio)
      |
      v
Transcript
```

---

# 17. LLM

The LLM is used to understand conversational responses.

V1 uses:

```text
Provider: Groq
Model: openai/gpt-oss-120b
```

The LLM must be isolated behind an LLM provider interface.

The business logic must not depend directly on provider-specific SDK behavior.

---

# 18. TTS

The AI uses text-to-speech to ask questions to the user.

V1 uses:

```text
Provider: Deepgram
Model: flux-cliff-en
```

The TTS component must be isolated behind a provider interface.

Conceptually:

```text
Question
   |
   v
TTS Provider
   |
   v
Audio
   |
   v
Browser
```

---

# 19. Document Presentation

After the question stage, the system begins document presentation.

The user must show **all previously uploaded documents**, one by one.

Example:

```text
Uploaded Documents

1. Aadhaar
2. PAN
3. Passport
```

The system presents:

```text
Please show the same Aadhaar document you uploaded.
```

After Aadhaar is captured:

```text
Please show the same PAN document you uploaded.
```

Then:

```text
Please show the same Passport document you uploaded.
```

The backend tracks the current document.

---

# 20. Document Camera Frame

The frontend must provide a visible document frame.

Example:

```text
+--------------------------------------+
|                                      |
|        PLACE DOCUMENT INSIDE         |
|              THE FRAME               |
|                                      |
|      +------------------------+      |
|      |                        |      |
|      |       DOCUMENT         |      |
|      |                        |      |
|      +------------------------+      |
|                                      |
|          Keep it steady              |
+--------------------------------------+
```

The user should be guided to position the document inside the frame.

The V1 objective is reliable document capture.

Advanced document detection, OCR, fraud analysis, and document authenticity verification are outside the initial V1 scope unless explicitly added later.

---

# 21. Document Capture

For each uploaded document:

```text
Document Presentation
        |
        v
Camera Frame
        |
        v
User Positions Document
        |
        v
Capture
        |
        v
Store Evidence
        |
        v
Next Document
```

The captured document must be associated with:

- KYC case
- Video KYC session
- Verification attempt
- Original uploaded document
- Document type
- Capture timestamp

---

# 22. Document Capture Retry

If document capture fails because the document is:

- Not inside the frame
- Too blurry
- Not sufficiently visible
- Not stable enough
- Otherwise unsuitable for capture

the user receives another capture opportunity within the same attempt.

Example:

```text
DOCUMENT CAPTURE
      |
      +-- VALID → NEXT DOCUMENT
      |
      +-- INVALID
             |
             v
          RETRY
             |
             v
          CAPTURE
```

This is a step-level retry, not a new KYC attempt.

---

# 23. End of Recording

After every uploaded document has been presented and captured:

```text
ALL DOCUMENTS CAPTURED
        |
        v
STOP RECORDING
```

The backend then moves the attempt toward evidence creation.

---

# 24. Evidence Package

The system creates an evidence package for the completed attempt.

The evidence package may contain:

```text
Evidence Package
|
+-- Continuous Video
|
+-- Audio
|
+-- Face Result
|
+-- Liveness Result
|
+-- Question/Answer Records
|
+-- Transcript
|
+-- Document Captures
|
+-- Original Document References
|
+-- Session Metadata
|
+-- Attempt Metadata
|
+-- Audit Information
```

The evidence package must be associated with the specific attempt.

---

# 25. Human Review

After evidence creation:

```text
EVIDENCE PACKAGE
       |
       v
HUMAN REVIEW
```

The reviewer can inspect the available evidence.

The reviewer makes the final decision.

Available V1 decisions:

```text
APPROVE
RETRY
```

---

# 26. Approval

When the reviewer approves:

```text
HUMAN REVIEW
     |
     v
 APPROVE
     |
     v
 VERIFIED
```

The system records:

- Reviewer
- Decision
- Timestamp
- Relevant evidence
- Audit event

The AI does not make this decision.

---

# 27. Human-Review Retry

When the reviewer selects:

```text
RETRY
```

the current attempt is closed for review purposes and a new attempt is created.

```text
ATTEMPT 1
    |
    v
HUMAN REVIEW
    |
    v
  RETRY
    |
    v
ATTEMPT 2
    |
    v
STARTED
```

The new attempt starts from the beginning:

```text
STARTED
   ↓
RECORDING
   ↓
FACE
   ↓
LIVENESS
   ↓
QUESTIONS
   ↓
ALL DOCUMENTS
   ↓
RECORDING COMPLETE
   ↓
EVIDENCE
   ↓
REVIEW
```

Previous attempts must never be deleted.

---

# 28. Two Types of Retry

The system must distinguish between:

## Step Retry

Occurs during the current attempt.

```text
Liveness fails
    ↓
Retry liveness
```

Same attempt.

## Human-Review Retry

Occurs after human review.

```text
Reviewer selects RETRY
    ↓
Create new attempt
    ↓
Start from beginning
```

New attempt.

These two retry types must be represented separately in the backend.

---

# 29. V1 Technology Stack

## Frontend

The V1 frontend runs locally in Docker.

Responsibilities:

- Camera access
- Microphone access
- Video preview
- Recording UI
- Step UI
- AI instructions
- Question UI
- Document frame
- Document capture
- Error display
- Session status display

The frontend is never the source of truth for KYC state.

---

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
REST APIs
```

The backend owns:

- State machine
- Session management
- Attempt management
- Question selection
- Workflow control
- Evidence creation
- Review workflow
- Retry workflow
- Audit events

---

## Database

V1:

```text
PostgreSQL
```

PostgreSQL runs inside Docker.

Large binary files must not be stored directly in PostgreSQL.

---

## Storage

V1 uses local filesystem storage.

Example:

```text
storage/
└── video-kyc/
    ├── cases/
    ├── sessions/
    ├── attempts/
    ├── recordings/
    ├── documents/
    ├── audio/
    └── evidence/
```

A storage provider abstraction must be used so that cloud/object storage can be introduced later.

---

## LLM

```text
Provider: Groq
Model: openai/gpt-oss-120b
```

---

## ASR

```text
Provider: Groq
Model: whisper-large-v3
```

---

## TTS

```text
Provider: Deepgram
Model: flux-cliff-en
```

---

# 30. Provider Abstraction

External providers must not be directly embedded throughout business logic.

Required interfaces include:

```text
LLMProvider
ASRProvider
TTSProvider
FaceProvider
LivenessProvider
StorageProvider
```

Initial implementations:

```text
GroqLLMProvider
GroqASRProvider
DeepgramTTSProvider
FaceProvider
LivenessProvider
LocalStorageProvider
```

This allows providers to be replaced without rewriting the core workflow.

---

# 31. High-Level Architecture

```text
                    FRONTEND
                        |
                        v
                   API LAYER
                        |
                        v
              APPLICATION LAYER
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
 Session Service   State Machine   Question Service
       |                |                |
       +----------------+----------------+
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
 Recording        Document Service   Evidence Service
 Service
       |
       v
 Review Service
       |
       v
 Retry Service
       |
       v
 Audit Service
                        |
                        v
               INFRASTRUCTURE
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
 PostgreSQL      Local Storage      AI Providers
                                      |
                             +--------+--------+
                             |        |        |
                           Groq    Deepgram   Face/Liveness
```

---

# 32. State Machine

The backend state machine is the source of truth.

V1 states:

```text
STARTED
   |
   v
FACE
   |
   v
LIVENESS
   |
   v
GENERAL_QUESTIONS
   |
   v
DOCUMENT_PRESENTATION
   |
   v
DOCUMENT_CAPTURE
   |
   v
RECORDING_COMPLETE
   |
   v
EVIDENCE_PACKAGE_CREATED
   |
   v
HUMAN_REVIEW
   |
   +------------+
   |            |
   v            v
APPROVED      RETRY
   |            |
   v            v
VERIFIED    NEW_ATTEMPT
                |
                v
             STARTED
```

The exact internal state representation will be defined in the architecture and API specifications.

---

# 33. Security Requirements

The system handles sensitive:

- Identity information
- Documents
- Video
- Audio
- Biometric information
- KYC evidence

Therefore:

1. Secrets must never be hardcoded.
2. API keys must be stored using environment variables/secrets management.
3. `.env` must never be committed.
4. `.env.example` should contain placeholders.
5. Sensitive data must not appear in normal application logs.
6. Access to evidence must be restricted.
7. Reviewer actions must be audited.
8. State transitions must be auditable.
9. Stored evidence must have controlled access.
10. Retention and deletion policies must be defined.
11. Sensitive data should be encrypted appropriately.
12. Authentication and authorization must be enforced for protected APIs.

---

# 34. Audit Requirements

Important actions must generate audit events.

Examples:

```text
SESSION_CREATED
ATTEMPT_CREATED
RECORDING_STARTED
RECORDING_COMPLETED
FACE_COMPLETED
LIVENESS_COMPLETED
QUESTION_ANSWERED
DOCUMENT_CAPTURED
EVIDENCE_CREATED
REVIEW_STARTED
REVIEW_APPROVED
REVIEW_RETRY
NEW_ATTEMPT_CREATED
```

Audit records should contain appropriate metadata such as:

```text
event
case_id
session_id
attempt_id
actor
timestamp
metadata
```

Sensitive information should not be unnecessarily duplicated inside audit logs.

---

# 35. Configuration Requirements

Configuration must be centralized.

Examples:

```text
APP_ENV
DATABASE_URL

GROQ_API_KEY
LLM_MODEL
ASR_MODEL

DEEPGRAM_API_KEY
TTS_MODEL

LOCAL_STORAGE_ROOT

JWT_SECRET

MAX_STEP_RETRIES
```

Configuration values must not be hardcoded into business logic.

---

# 36. Non-Functional Requirements

The V1 system should be:

### Modular

Services should have clear responsibilities.

### Testable

Core business logic should be testable without external AI providers.

### Auditable

Every important KYC action should be traceable.

### Secure

Sensitive identity and media data must be protected.

### Provider-independent

AI providers should be replaceable.

### Recoverable

Temporary step failures should support bounded retries.

### Deterministic workflow

The backend state machine controls progression.

### Human-controlled decision

AI never makes the final KYC decision.

---

# 37. V1 Scope

## Included

- Existing KYC case
- Uploaded document references
- Video KYC session
- Verification attempts
- Continuous video/audio recording
- Camera and microphone access
- Face detection
- Liveness / anti-spoofing
- Admin-configurable question pool
- Random selection of N questions
- ASR
- LLM-based answer understanding
- TTS
- All uploaded documents shown one by one
- Camera document frame
- Document capture
- Evidence package
- Human reviewer dashboard/workflow
- Approve
- Human-review retry
- Step-level automatic retries
- Audit trail
- Local filesystem storage
- Docker-based local development
- PostgreSQL in Docker
- Groq API
- Deepgram API

---

# 38. Out of Scope for V1

The following are not required for the initial V1:

- Automated face identity matching
- Face matching against document
- Automated KYC approval
- Automated KYC rejection
- Cloud object storage
- Advanced document fraud detection
- Advanced document authenticity verification
- Advanced OCR-based identity extraction unless separately required
- Fully automated KYC decision making
- AI-controlled workflow transitions

These may be considered in future versions.

---

# 39. V1 Development Environment

The target development environment is:

```text
Browser
   |
   v
Frontend Docker Container
   |
   v
Backend Docker Container
   |
   +------> PostgreSQL Docker Container
   |
   +------> Local Filesystem
   |
   +------> Groq API
   |
   +------> Deepgram API
```

All core application components should be runnable locally using Docker.

---

# 40. Success Criteria

V1 is successful when a user can:

```text
1. Open an existing KYC case
2. Click Start Video KYC
3. Grant camera/microphone permissions
4. Start continuous recording
5. Complete face detection
6. Complete liveness
7. Answer randomly selected configured questions
8. Present every uploaded document
9. Position each document inside the camera frame
10. Capture every document
11. Complete the recording
12. Generate an evidence package
13. Submit the case for human review
14. Have a reviewer approve the case
15. Reach VERIFIED state
```

The system must also support:

```text
Step failure
    ↓
Automatic bounded retry
```

and:

```text
Human reviewer
    ↓
RETRY
    ↓
New attempt
    ↓
Complete workflow from beginning
```

Previous attempts must remain available for audit.

---

# 41. Definition of Done for V1

V1 is considered complete when:

- The complete user flow works end-to-end.
- Backend state transitions are enforced.
- Frontend mirrors backend state.
- Continuous recording works.
- Face detection works.
- Liveness works.
- Configured questions can be randomly selected.
- ASR works.
- LLM answer understanding works.
- TTS works.
- All uploaded documents can be presented and captured.
- Evidence packages are generated.
- Human reviewers can approve or retry.
- Retry creates a new attempt.
- Previous attempts remain preserved.
- Step-level failures support bounded automatic retries.
- Authentication and authorization are implemented.
- Audit events are recorded.
- Sensitive information is protected.
- Unit tests exist for core business logic.
- Integration tests exist for infrastructure/providers.
- End-to-end testing covers the primary workflow.
- The complete system can run locally using Docker.

---

# 42. Product Decision Summary

The final V1 product decisions are:

```text
Existing KYC case?
→ YES

Uploaded documents?
→ YES, already available before Video KYC

Documents shown during Video KYC?
→ ALL uploaded documents, one by one

Face matching?
→ NO, future feature

Face detection?
→ YES

Liveness?
→ YES

Questions?
→ Admin-configurable question pool

Number of questions?
→ Configurable N

Question selection?
→ Backend randomly selects N questions

Conversation?
→ AI asks → User speaks → ASR → LLM → Next question

Recording?
→ One continuous recording

Document capture?
→ Camera document frame

Human review?
→ YES

Final KYC decision?
→ Human reviewer

Human decisions?
→ APPROVE / RETRY

Human-review RETRY?
→ Create new attempt and start from beginning

Step failure?
→ Automatic bounded retry within same attempt

V1 frontend?
→ Local browser + Docker

V1 backend?
→ Docker

Database?
→ PostgreSQL + Docker

Storage?
→ Local filesystem

LLM?
→ Groq

ASR?
→ Groq Whisper Large V3

TTS?
→ Deepgram

Cloud storage?
→ NO for V1

Automated KYC approval?
→ NO
```

---

# 43. Core Product Rule

The most important rule of this entire system is:

```text
                    AI
                    |
              ASSISTS THE USER
                    |
                    v
              BACKEND
                    |
             CONTROLS WORKFLOW
                    |
                    v
                 HUMAN
                    |
              MAKES FINAL
               DECISION
```

Therefore:

```text
AI ≠ KYC Decision Maker

Frontend ≠ Workflow Authority

Backend = Workflow Authority

Human Reviewer = Final Decision Maker
```

This principle must be preserved throughout the entire implementation.