# Architecture Document

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 Architecture Specification  
**Product Specification:** `docs/PRD.md`  
**Engineering Rules:** `docs/PROJECT_INSTRUCTIONS.md`

---

# 1. Architecture Overview

The Video KYC system is a modular backend-driven application.

The core architecture is:

```text
                         USER
                           |
                           v
                    WEB FRONTEND
                           |
                           | HTTPS / REST
                           v
                    FASTAPI BACKEND
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
       State Machine    Services      API Layer
             |             |
             +------+------+ 
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
   PostgreSQL   Local Storage  AI Providers
                              |
                    +---------+---------+
                    |         |         |
                    v         v         v
                  Groq    Deepgram   Face/Liveness
```

The backend is the central orchestration layer.

The frontend does not own KYC state.

AI providers perform specialized tasks but do not control the overall workflow.

The human reviewer makes the final KYC decision.

---

# 2. Architecture Principles

The system follows these architectural principles:

1. Backend is the source of truth.
2. Workflow is controlled by an explicit state machine.
3. Frontend is responsible for user interaction and media capture.
4. Business logic is separated from API routes.
5. Database access is separated from business logic.
6. External AI providers are accessed through provider interfaces.
7. Large media files are stored outside PostgreSQL.
8. Attempts are isolated from each other.
9. Every important workflow action is auditable.
10. AI assists the workflow but does not own the workflow.
11. Human review is the final decision layer.
12. V1 is a modular monolith rather than a distributed microservice architecture.

---

# 3. Architectural Style

V1 uses a:

```text
Modular Monolith
+
Layered Architecture
+
Explicit State Machine
+
Provider Abstraction
```

Conceptually:

```text
Frontend
   |
   v
API Layer
   |
   v
Application Services
   |
   v
Domain / State Machine
   |
   +----------+----------+
   |          |          |
   v          v          v
Database   Storage    Providers
```

This provides clear boundaries without introducing unnecessary microservices.

---

# 4. High-Level System

```text
┌──────────────────────────────────────────────────────────────┐
│                         USER BROWSER                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    React Frontend                      │  │
│  │                                                        │  │
│  │ Camera │ Microphone │ Recording │ Questions │ Docs    │  │
│  │                                                        │  │
│  └───────────────────────────┬────────────────────────────┘  │
└───────────────────────────────┼──────────────────────────────┘
                                │
                         HTTPS / REST
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND                        │
│                                                              │
│  ┌──────────────┐    ┌───────────────────────────────────┐  │
│  │ API Layer    │───►│ Application Services              │  │
│  └──────────────┘    │                                   │  │
│                      │ Session │ Attempt │ Questions      │  │
│                      │ Recording │ Documents │ Review     │  │
│                      │ Evidence │ Audit                    │  │
│                      └────────────────┬──────────────────────┘  │
│                                       │                      │
│                              ┌────────▼────────┐             │
│                              │ State Machine   │             │
│                              └────────┬────────┘             │
│                                       │                      │
│                ┌──────────────────────┼──────────────────┐   │
│                │                      │                  │   │
│                ▼                      ▼                  ▼   │
│          PostgreSQL              Storage             Providers│
│                                                   ┌──────────┐│
│                                                   │   Groq   ││
│                                                   │ Deepgram ││
│                                                   │ Liveness ││
│                                                   └──────────┘│
└──────────────────────────────────────────────────────────────┘
```

---

# 5. Major Components

The system consists of the following major components:

```text
Frontend
Backend API
Session Service
Attempt Service
State Machine
Recording Service
Face Service
Liveness Service
Question Service
Conversation Service
Document Service
Evidence Service
Review Service
Audit Service
Provider Layer
Repository Layer
PostgreSQL
Storage Layer
```

---

# 6. Frontend Architecture

The frontend is responsible for user interaction.

Primary responsibilities:

```text
Camera Access
Microphone Access
Video Preview
Recording UI
Question UI
AI Audio Playback
Document Frame
Document Capture
Progress Display
Error Display
Review Status
```

The frontend receives authoritative state from the backend.

Example:

```text
Backend:
{
    "current_step": "LIVENESS"
}
        |
        v
Frontend:
Render Liveness UI
```

The frontend must not independently transition the workflow.

---

# 7. Frontend Component Structure

Suggested structure:

```text
frontend/
└── src/
    ├── components/
    │   ├── Camera/
    │   ├── Recording/
    │   ├── Face/
    │   ├── Liveness/
    │   ├── Questions/
    │   ├── Conversation/
    │   ├── Documents/
    │   ├── DocumentFrame/
    │   └── Common/
    │
    ├── pages/
    │   ├── KycCase/
    │   ├── VideoKyc/
    │   └── Review/
    │
    ├── services/
    │   ├── api/
    │   ├── recording/
    │   └── media/
    │
    ├── hooks/
    │
    ├── state/
    │
    ├── types/
    │
    └── utils/
```

The exact implementation can be adjusted during development.

---

# 8. Backend Architecture

The backend follows a layered architecture.

```text
HTTP Request
     |
     v
API Router
     |
     v
Schema Validation
     |
     v
Application Service
     |
     v
Domain / State Machine
     |
     +------------+------------+
     |            |            |
     v            v            v
Repository    Provider      Storage
     |            |            |
     v            v            v
PostgreSQL     AI APIs      Filesystem
```

---

# 9. Backend Layers

## 9.1 API Layer

Responsible for:

- HTTP endpoints
- Authentication
- Request validation
- Response serialization
- HTTP error mapping

It should remain thin.

---

## 9.2 Application Layer

Responsible for application use cases.

Examples:

```text
StartVideoKyc
CreateAttempt
StartRecording
CompleteFaceStep
CompleteLiveness
SelectQuestions
SubmitAnswer
PresentDocument
CaptureDocument
CompleteRecording
CreateEvidence
ApproveAttempt
RetryAttempt
```

---

## 9.3 Domain Layer

Responsible for core business rules.

Examples:

```text
KYC state transitions
Retry rules
Attempt rules
Question selection rules
Document sequence rules
Review rules
```

The domain layer should not depend directly on Groq or Deepgram SDKs.

---

## 9.4 Repository Layer

Responsible for persistence.

Examples:

```text
CaseRepository
SessionRepository
AttemptRepository
QuestionRepository
DocumentRepository
EvidenceRepository
ReviewRepository
AuditRepository
```

---

## 9.5 Provider Layer

Responsible for external services.

Examples:

```text
GroqLLMProvider
GroqASRProvider
DeepgramTTSProvider
LivenessProvider
FaceProvider
```

---

## 9.6 Storage Layer

Responsible for media and evidence files.

V1:

```text
LocalStorageProvider
```

Future:

```text
S3StorageProvider
GCSStorageProvider
AzureBlobStorageProvider
```

---

# 10. Core Domain Model

The primary relationship is:

```text
KYC Case
    |
    +── Uploaded Documents
    |
    +── Video KYC Session
             |
             +── Attempt 1
             |
             +── Attempt 2
             |
             +── Attempt N
```

---

# 11. KYC Case

The KYC case is the parent business entity.

Conceptually:

```text
KycCase
---------
id
user_id
status
created_at
updated_at
```

A case may have previously uploaded documents.

---

# 12. Uploaded Document

Conceptually:

```text
Document
---------
id
case_id
document_type
filename
storage_reference
created_at
```

The document is the reference document that the user must present during Video KYC.

---

# 13. Video KYC Session

A Video KYC session represents the overall Video KYC process for a case.

Conceptually:

```text
VideoKycSession
---------------
id
case_id
status
created_at
updated_at
```

---

# 14. Verification Attempt

Each attempt represents one complete verification run.

Conceptually:

```text
VerificationAttempt
-------------------
id
session_id
attempt_number
status
current_step
started_at
completed_at
```

Attempt-specific data must reference this entity.

---

# 15. Attempt Isolation

Example:

```text
Session 001
│
├── Attempt 001
│   ├── Recording
│   ├── Liveness
│   ├── Answers
│   ├── Captures
│   └── Evidence
│
└── Attempt 002
    ├── Recording
    ├── Liveness
    ├── Answers
    ├── Captures
    └── Evidence
```

Attempt 002 must not overwrite Attempt 001.

---

# 16. State Machine Architecture

The state machine is one of the most important backend components.

V1 states:

```text
STARTED
FACE
LIVENESS
GENERAL_QUESTIONS
DOCUMENT_PRESENTATION
DOCUMENT_CAPTURE
RECORDING_COMPLETE
EVIDENCE_PACKAGE_CREATED
HUMAN_REVIEW
VERIFIED
```

Retry creates:

```text
NEW ATTEMPT
    ↓
STARTED
```

---

# 17. State Transition Model

The state machine should explicitly define allowed transitions.

Example:

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
   +----------------+
   |                |
   v                v
VERIFIED         NEW ATTEMPT
                     |
                     v
                  STARTED
```

---

# 18. State Transition Responsibility

Only the backend can commit state transitions.

Example:

```text
Frontend
   |
   | Submit liveness result
   v
Backend
   |
   | Validate result
   |
   | Validate current state
   |
   | Validate retry limit
   |
   | Persist result
   |
   | Transition state
   v
Next State
```

The frontend simply renders the returned state.

---

# 19. State Transition Transaction

A state transition should be atomic where possible.

Example:

```text
Validate result
      +
Store result
      +
Update attempt state
      +
Create audit event
```

These operations should be coordinated so that the database cannot end up with:

```text
Liveness = SUCCESS
State = FACE
```

or another inconsistent combination.

---

# 20. Retry Architecture

There are two independent retry systems.

## Step Retry

```text
Attempt 001
    |
    v
Liveness
    |
    v
Failure
    |
    v
Retry counter
    |
    v
Liveness again
```

## Human Review Retry

```text
Attempt 001
    |
    v
Human Review
    |
    v
RETRY
    |
    v
Create Attempt 002
    |
    v
STARTED
```

---

# 21. Retry State

Retry information should be stored explicitly.

Conceptually:

```text
StepAttempt
-----------
attempt_id
step
retry_count
max_retries
last_result
updated_at
```

The exact database design can be finalized during schema implementation.

---

# 22. Recording Architecture

Recording belongs to an attempt.

```text
Verification Attempt
        |
        v
Recording Service
        |
        +── Camera stream
        |
        +── Microphone stream
        |
        v
Continuous Media
        |
        v
Local Storage
```

The backend maintains recording metadata.

The browser performs actual media capture.

---

# 23. Recording Lifecycle

```text
Attempt Created
      |
      v
Recording Start Requested
      |
      v
Frontend Starts Media Capture
      |
      v
Recording Active
      |
      +---- Face
      |
      +---- Liveness
      |
      +---- Questions
      |
      +---- Documents
      |
      v
Recording Stop
      |
      v
Recording Finalized
      |
      v
Storage Reference Saved
```

---

# 24. Recording Metadata

Conceptually:

```text
Recording
---------
id
attempt_id
storage_reference
mime_type
size
started_at
ended_at
status
```

The database stores metadata and storage references.

The actual media is stored in the filesystem.

---

# 25. Face Architecture

V1 face functionality consists of:

```text
Camera
   |
   v
Face Detection
   |
   v
Face Result
```

The face component should be isolated.

Example:

```text
FaceProvider
    |
    v
detect(frame)
    |
    v
FaceResult
```

---

# 26. Face Result

Conceptually:

```text
FaceResult
----------
detected
face_count
quality
timestamp
metadata
```

V1 does not perform identity matching.

---

# 27. Liveness Architecture

```text
Camera
   |
   v
Liveness Service
   |
   v
Liveness Provider
   |
   v
Liveness Result
```

Example:

```text
LivenessProvider
       |
       +── evaluate()
       |
       v
LivenessResult
```

---

# 28. Liveness Result

Conceptually:

```text
LivenessResult
-------------
status
score
provider
timestamp
metadata
```

The application should not depend on a provider-specific response format.

---

# 29. Question Architecture

The question system has three major concepts:

```text
Question Pool
      |
      v
Question Selection
      |
      v
Attempt Question Sequence
```

---

# 30. Question Pool

Administrators configure questions.

Conceptually:

```text
Question
--------
id
text
category
active
created_at
updated_at
```

---

# 31. Question Configuration

Conceptually:

```text
QuestionConfiguration
--------------------
id
case/configuration reference
question_count
random_selection
```

The exact relationship can be refined based on the admin configuration model.

---

# 32. Selected Questions

Selected questions must belong to the attempt.

Conceptually:

```text
AttemptQuestion
---------------
id
attempt_id
question_id
sequence_number
status
```

This guarantees that the exact question sequence can be reconstructed later.

---

# 33. Conversation Architecture

Conversation processing follows:

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
User
   |
   v
Microphone
   |
   v
ASR Provider
   |
   v
Transcript
   |
   v
LLM Provider
   |
   v
Structured Answer Understanding
   |
   v
Question Service
```

---

# 34. Conversation Responsibility

The Conversation Service is responsible for coordinating:

- Current question
- User response
- Transcript
- LLM interpretation
- Answer record

It does not own the overall KYC state machine.

---

# 35. ASR Architecture

```text
Audio
  |
  v
ASRProvider
  |
  v
GroqASRProvider
  |
  v
Transcript
```

Provider-specific response objects should be converted into an internal transcript model.

---

# 36. LLM Architecture

```text
Transcript
    |
    v
ConversationService
    |
    v
LLMProvider
    |
    v
GroqLLMProvider
    |
    v
StructuredAnswer
```

The LLM should return structured information.

---

# 37. TTS Architecture

```text
Question Text
     |
     v
TTSProvider
     |
     v
DeepgramTTSProvider
     |
     v
Audio
     |
     v
Browser
```

---

# 38. Provider Interfaces

The application should define internal interfaces.

Example:

```python
class LLMProvider:
    async def understand_answer(...):
        ...
```

```python
class ASRProvider:
    async def transcribe(...):
        ...
```

```python
class TTSProvider:
    async def synthesize(...):
        ...
```

```python
class LivenessProvider:
    async def evaluate(...):
        ...
```

```python
class StorageProvider:
    async def save(...):
        ...
```

Concrete implementations live in the provider layer.

---

# 39. Document Architecture

The document workflow is:

```text
Uploaded Document
       |
       v
Document Presentation
       |
       v
Camera Frame
       |
       v
Document Capture
       |
       v
Capture Validation
       |
       v
Storage
       |
       v
Evidence
```

---

# 40. Document Sequencing

The backend maintains document order.

Example:

```text
Documents:
1. Aadhaar
2. PAN
3. Passport
```

Backend state:

```text
current_document_index = 0
```

After successful capture:

```text
current_document_index = 1
```

The frontend receives the current document information from the backend.

---

# 41. Document Capture Architecture

```text
Browser Camera
      |
      v
Document Frame
      |
      v
Capture Image
      |
      v
Upload / Submit
      |
      v
Document Service
      |
      +── Validate
      |
      +── Associate with attempt
      |
      +── Store
      |
      +── Record metadata
      |
      v
Next Document
```

---

# 42. Document Capture Validation

The architecture should allow validation of:

- Image presence
- File format
- File size
- Basic quality
- Document visibility
- Frame positioning

The exact detection algorithm can be selected during implementation.

---

# 43. Evidence Architecture

Evidence is assembled after the verification attempt completes.

```text
Attempt
  |
  +── Recording
  +── Face Result
  +── Liveness Result
  +── Questions
  +── Answers
  +── Transcripts
  +── Document Captures
  +── Audit Events
  |
  v
Evidence Service
  |
  v
Evidence Package
```

---

# 44. Evidence Package

Conceptually:

```text
EvidencePackage
---------------
id
attempt_id
status
created_at
completed_at
manifest_reference
```

The manifest may reference all evidence artifacts.

---

# 45. Evidence Manifest

Example conceptual structure:

```json
{
  "attempt_id": "attempt_001",
  "recording": "storage://...",
  "face_result": "...",
  "liveness_result": "...",
  "questions": "...",
  "answers": "...",
  "documents": [
    "...",
    "..."
  ]
}
```

The exact schema belongs in the implementation/API specifications.

---

# 46. Human Review Architecture

After evidence creation:

```text
Evidence Package
      |
      v
Review Service
      |
      v
Reviewer
      |
      +------ APPROVE
      |
      +------ RETRY
```

The reviewer operates through a protected reviewer interface/API.

---

# 47. Review Decision Flow

Approve:

```text
HUMAN_REVIEW
     |
     v
APPROVE
     |
     v
VERIFIED
```

Retry:

```text
HUMAN_REVIEW
     |
     v
RETRY
     |
     v
Create New Attempt
     |
     v
STARTED
```

---

# 48. Review Data

Conceptually:

```text
Review
------
id
attempt_id
reviewer_id
decision
reason
notes
created_at
```

Reviewer decisions must be auditable.

---

# 49. Audit Architecture

Audit events are generated by backend services.

```text
Service
   |
   v
AuditService
   |
   v
AuditRepository
   |
   v
PostgreSQL
```

Example:

```text
AttemptService
      |
      +── ATTEMPT_CREATED
      |
      +── AuditService
```

---

# 50. Audit Event

Conceptually:

```text
AuditEvent
----------
id
case_id
session_id
attempt_id
event_type
actor_type
actor_id
timestamp
metadata
```

Sensitive information should not be unnecessarily duplicated in metadata.

---

# 51. Database Architecture

PostgreSQL stores structured application data.

High-level relationship:

```text
KycCase
   |
   +── Document
   |
   +── VideoKycSession
           |
           +── VerificationAttempt
                    |
                    +── AttemptQuestion
                    |
                    +── Answer
                    |
                    +── FaceResult
                    |
                    +── LivenessResult
                    |
                    +── Recording
                    |
                    +── DocumentCapture
                    |
                    +── EvidencePackage
                    |
                    +── Review
                    |
                    +── AuditEvent
```

---

# 52. Storage Architecture

V1 uses local filesystem storage.

```text
Backend
   |
   v
StorageProvider
   |
   v
LocalStorageProvider
   |
   v
Filesystem
```

Suggested structure:

```text
storage/
└── video-kyc/
    ├── cases/
    │
    ├── sessions/
    │
    ├── attempts/
    │   ├── attempt_001/
    │   │   ├── recording/
    │   │   ├── audio/
    │   │   ├── documents/
    │   │   └── evidence/
    │   │
    │   └── attempt_002/
    │
    └── temporary/
```

---

# 53. Storage References

The database should store references such as:

```text
storage_path
storage_key
mime_type
size
checksum
```

rather than embedding large binary content into database rows.

---

# 54. Future Cloud Storage

The architecture should allow:

```text
StorageProvider
      |
      +── LocalStorageProvider
      |
      +── S3StorageProvider
      |
      +── GCSStorageProvider
      |
      +── AzureBlobStorageProvider
```

Changing storage providers should not require changing core KYC business logic.

---

# 55. API Architecture

API structure should be versioned:

```text
/api/v1/
```

Suggested groups:

```text
/api/v1/auth
/api/v1/kyc-cases
/api/v1/video-sessions
/api/v1/attempts
/api/v1/questions
/api/v1/conversation
/api/v1/documents
/api/v1/evidence
/api/v1/reviews
```

The exact endpoint definitions belong in:

```text
docs/API_CONTRACT.md
```

---

# 56. Start Video KYC Flow

```text
Frontend
   |
   | POST /api/v1/kyc-cases/{case_id}/video-sessions
   v
Backend
   |
   +── Validate case
   +── Validate documents
   +── Create session
   +── Create attempt
   +── Set STARTED
   +── Create audit event
   |
   v
Response
   |
   +── session_id
   +── attempt_id
   +── status
   +── current_step
```

---

# 57. Face Step Flow

```text
Frontend
   |
   | Face result
   v
Backend
   |
   +── Validate current state
   +── Validate result
   +── Store face result
   +── Create audit event
   |
   +── Success
   |      ↓
   |   LIVENESS
   |
   +── Failure
          ↓
       Retry
```

---

# 58. Liveness Step Flow

```text
Camera Data
    |
    v
Liveness Provider
    |
    v
Liveness Result
    |
    v
Backend
    |
    +── PASS → GENERAL_QUESTIONS
    |
    +── FAIL → Retry
```

---

# 59. Question Flow

```text
Backend
   |
   +── Load Question Pool
   |
   +── Randomly select N
   |
   +── Store selected sequence
   |
   v
Frontend
   |
   v
Question
   |
   v
TTS
   |
   v
User
   |
   v
ASR
   |
   v
LLM
   |
   v
Structured Answer
   |
   v
Backend
   |
   v
Next Question
```

---

# 60. Document Flow

```text
Backend
   |
   v
Current Document
   |
   v
Frontend
   |
   v
Document Frame
   |
   v
Capture
   |
   v
Backend
   |
   +── Validate
   +── Store
   +── Record capture
   |
   v
Next Document
```

---

# 61. Recording and Workflow Coordination

Recording should operate across the complete attempt.

The recording lifecycle should not depend on individual workflow components.

Conceptually:

```text
Attempt Lifecycle
       |
       +--------------------------+
       |                          |
       v                          v
Workflow State              Recording
       |                          |
       +----------+---------------+
                  |
                  v
             Finalization
```

The workflow can move between steps while recording remains active.

---

# 62. Asynchronous Processing

Some operations may be asynchronous.

Potential candidates:

```text
Video finalization
Evidence packaging
Large file processing
Transcoding
Provider processing
```

V1 should keep asynchronous processing limited to cases where it provides a clear benefit.

Do not introduce a distributed task system without a real requirement.

---

# 63. Background Jobs

If background jobs become necessary, use a dedicated worker abstraction.

Example:

```text
Backend
   |
   v
Job Queue
   |
   v
Worker
   |
   v
Evidence Processing
```

The exact queue technology is not fixed by the current V1 requirements.

---

# 64. Authentication Architecture

Conceptual flow:

```text
Browser
   |
   v
Authentication
   |
   v
Access Token / Session
   |
   v
Protected API
```

Every protected request must be authenticated.

Authorization is evaluated based on user role and resource ownership.

---

# 65. Authorization

Example:

```text
USER
 └── Access own KYC case

ADMIN
 └── Configure questions
 └── Manage system configuration

REVIEWER
 └── Review evidence
 └── Approve / Retry
```

Exact permissions should be defined in the security specification.

---

# 66. Error Architecture

Errors should move through controlled layers:

```text
Provider Error
     |
     v
Service Error
     |
     v
API Error Mapping
     |
     v
Safe HTTP Response
     |
     v
Frontend Message
```

Internal exception details should not be exposed to users.

---

# 67. Provider Failure Example

```text
Groq API Failure
      |
      v
GroqASRProvider
      |
      v
ProviderError
      |
      v
ConversationService
      |
      v
Recoverable Error / Retry / Failure State
```

The provider failure must not silently mark the question as answered.

---

# 68. Security Architecture

Sensitive data flows through:

```text
Browser
   |
 HTTPS
   |
Backend
   |
 +-------------+
 |             |
 v             v
Database     Storage
   |
   +------+
          |
          v
     AI Providers
```

Security requirements include:

- HTTPS in deployed environments
- Authentication
- Authorization
- Input validation
- Secure secret handling
- Restricted evidence access
- Sensitive logging controls
- File validation
- Access auditing

---

# 69. Data Lifecycle

Conceptually:

```text
Capture
   ↓
Validate
   ↓
Store
   ↓
Associate with Attempt
   ↓
Evidence
   ↓
Review
   ↓
Retention
   ↓
Deletion according to policy
```

Retention/deletion policy must be defined before production deployment.

---

# 70. Concurrency Control

Concurrent requests must not corrupt attempt state.

Example:

```text
Request A:
LIVENESS → QUESTIONS

Request B:
LIVENESS → QUESTIONS
```

The backend must ensure only one valid transition is committed.

Use appropriate database transactions and concurrency controls.

---

# 71. Idempotency

Important commands should be designed to avoid duplicate effects.

Example:

```text
Start session
```

Repeated requests should not accidentally create multiple sessions if the business rule expects one active session.

Similarly:

```text
Create evidence
```

must not create duplicate evidence packages because of repeated client requests.

---

# 72. API and Frontend Contract

Frontend and backend communicate through explicitly defined contracts.

```text
API_CONTRACT.md
       |
       +── Request schema
       +── Response schema
       +── Errors
       +── State behavior
       +── Authentication
       +── Retry behavior
```

No frontend implementation should depend on undocumented response fields.

---

# 73. API Response Model

Responses should expose the information required by the frontend without exposing unnecessary internal implementation details.

Example:

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "status": "IN_PROGRESS",
  "current_step": "DOCUMENT_CAPTURE",
  "current_document": {
    "id": "doc_002",
    "type": "PAN"
  }
}
```

Exact schemas belong in `API_CONTRACT.md`.

---

# 74. Project Directory

Recommended V1 structure:

```text
video-kyc/
│
├── docs/
│   ├── PRD.md
│   ├── PROJECT_INSTRUCTIONS.md
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACT.md
│   ├── ROADMAP.md
│   └── SECURITY.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── services/
│   │   ├── providers/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── workers/
│   │
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── package.json
│
├── storage/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# 75. Dependency Direction

Dependencies should move inward toward business logic.

Preferred:

```text
API
 ↓
Application
 ↓
Domain
 ↓
Interfaces
 ↑
Infrastructure Implementations
```

Provider SDKs must remain at the infrastructure boundary.

---

# 76. Example Dependency Structure

```text
QuestionService
      |
      v
LLMProvider Interface
      ^
      |
GroqLLMProvider
      |
      v
Groq SDK
```

The QuestionService should not import the Groq SDK directly.

---

# 77. Testing Architecture

Testing layers:

```text
              E2E
               |
        +------+------+
        |             |
   Integration      Frontend
        |
      Unit
```

Unit tests validate business logic.

Integration tests validate component boundaries.

E2E tests validate the complete workflow.

---

# 78. Mock Provider Architecture

Tests should support:

```text
FakeLLMProvider
FakeASRProvider
FakeTTSProvider
FakeFaceProvider
FakeLivenessProvider
FakeStorageProvider
```

Example:

```text
QuestionService
      |
      v
FakeLLMProvider
      |
      v
Deterministic Result
```

This avoids depending on external API availability during tests.

---

# 79. Deployment Architecture — V1

Local development:

```text
┌───────────────────────┐
│       Browser         │
└──────────┬────────────┘
           │
           v
┌───────────────────────┐
│ Frontend Container    │
└──────────┬────────────┘
           │
           v
┌───────────────────────┐
│ Backend Container     │
└──────┬─────────┬──────┘
       │         │
       v         v
┌──────────┐  ┌──────────────┐
│PostgreSQL│  │Local Storage │
│Container │  │Volume        │
└──────────┘  └──────────────┘

Backend
   |
   +------ Groq API
   |
   +------ Deepgram API
```

---

# 80. Docker Compose

The local environment should contain:

```text
frontend
backend
postgres
```

Potential volumes:

```text
postgres_data
video_kyc_storage
```

Environment variables should be injected through Docker configuration.

---

# 81. Scalability Direction

V1 is intentionally simple.

Future scaling could evolve toward:

```text
Load Balancer
      |
      v
Multiple Backend Instances
      |
      +------ PostgreSQL
      |
      +------ Object Storage
      |
      +------ Queue
      |
      +------ Workers
      |
      +------ AI Providers
```

The V1 architecture should avoid blocking this future evolution.

---

# 82. Future Cloud Migration

V1:

```text
Local Filesystem
```

Future:

```text
Object Storage
```

The migration should primarily require replacing:

```text
LocalStorageProvider
```

with:

```text
CloudStorageProvider
```

rather than rewriting the evidence or KYC workflow.

---

# 83. Future Face Matching

V1:

```text
Face Detection
+
Liveness
```

Future:

```text
Uploaded Document Face
        |
        v
Face Extraction
        |
        v
Face Embedding
        |
        v
Live Face
        |
        v
Face Embedding
        |
        v
Similarity Matching
```

This should be implemented as a separate capability.

It must not be silently added to V1.

---

# 84. Future AI Enhancements

Possible future capabilities:

```text
Document OCR
Document authenticity
Fraud detection
Face matching
Advanced conversational analysis
Risk scoring
Automated reviewer assistance
```

These are future extensions and must not alter the V1 architecture without explicit approval.

---

# 85. Architecture Decision: No Autonomous Agent

The system should not use an autonomous AI agent as the primary workflow controller.

Incorrect:

```text
LLM Agent
   |
   +── Decide next KYC step
   +── Decide document requirements
   +── Decide approval
   +── Decide retry
```

Correct:

```text
Backend State Machine
   |
   +── Controls workflow
   |
   +── Calls AI providers
   |
   +── Stores results
   |
   +── Requests human decision
```

The LLM is a specialized service inside the system.

---

# 86. Architecture Decision: AI as a Service

AI capabilities should be treated as infrastructure services:

```text
LLM
ASR
TTS
Face
Liveness
```

They should expose predictable internal interfaces.

The rest of the system should not depend on provider-specific details.

---

# 87. Architecture Decision: Human-in-the-Loop

The final decision architecture is:

```text
AI Processing
      |
      v
Evidence
      |
      v
Human Reviewer
      |
      +── APPROVE
      |
      +── RETRY
```

The system must preserve this boundary.

---

# 88. Complete Runtime Flow

```text
                       EXISTING KYC CASE
                               |
                               v
                       START VIDEO KYC
                               |
                               v
                         CREATE SESSION
                               |
                               v
                         CREATE ATTEMPT
                               |
                               v
                      START RECORDING
                               |
                               v
                         FACE DETECTION
                               |
                    +----------+----------+
                    |                     |
                  FAIL                   PASS
                    |                     |
                    v                     v
                  RETRY                LIVENESS
                                          |
                               +----------+----------+
                               |                     |
                             FAIL                   PASS
                               |                     |
                               v                     v
                             RETRY              QUESTIONS
                                                   |
                                                   v
                                            SELECT N QUESTIONS
                                                   |
                                                   v
                                             AI QUESTION
                                                   |
                                                   v
                                               USER SPEAKS
                                                   |
                                                   v
                                                  ASR
                                                   |
                                                   v
                                                  LLM
                                                   |
                                                   v
                                             NEXT QUESTION
                                                   |
                                                   v
                                            ALL QUESTIONS
                                                   |
                                                   v
                                           DOCUMENT 1
                                                   |
                                                   v
                                           DOCUMENT FRAME
                                                   |
                                                   v
                                              CAPTURE
                                                   |
                                                   v
                                           NEXT DOCUMENT
                                                   |
                                                   v
                                          ALL DOCUMENTS
                                                   |
                                                   v
                                          STOP RECORDING
                                                   |
                                                   v
                                         CREATE EVIDENCE
                                                   |
                                                   v
                                            HUMAN REVIEW
                                             /          \
                                            /            \
                                       APPROVE          RETRY
                                          |                |
                                          v                v
                                      VERIFIED        NEW ATTEMPT
                                                           |
                                                           v
                                                        STARTED
```

---

# 89. Final Architecture Rules

The implementation must preserve these boundaries:

```text
Frontend
    = User Interaction

Backend
    = Workflow Authority

State Machine
    = State Authority

Services
    = Business Operations

Providers
    = External Capabilities

Database
    = Structured Persistence

Storage
    = Media Persistence

AI
    = Assistance

Human Reviewer
    = Final Decision Maker
```

The architecture must remain modular, deterministic, testable, auditable, and secure.

---

# 90. Architecture Summary

The V1 Video KYC system is a backend-controlled modular monolith.

The browser captures video, audio, and document images.

The FastAPI backend controls the verification workflow through an explicit state machine.

PostgreSQL stores structured application data.

Local filesystem storage stores large media and evidence files.

Groq provides LLM and ASR capabilities.

Deepgram provides TTS.

Face detection and liveness are isolated behind provider interfaces.

The system supports bounded step-level retries and creates a new attempt when a human reviewer requests a retry.

The final KYC decision remains with the human reviewer.

The architecture is intentionally designed so that future improvements—cloud storage, face matching, document intelligence, advanced fraud detection, background workers, and additional AI providers—can be introduced without rewriting the core workflow.