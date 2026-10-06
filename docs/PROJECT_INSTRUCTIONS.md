# Project Instructions

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 Development Instructions  
**Primary Product Specification:** `docs/PRD.md`

---

# 1. Purpose

This document defines the engineering rules, architecture principles, development standards, implementation constraints, and workflow rules for the AI-Assisted Video KYC system.

The `PRD.md` defines **what the product must do**.

This document defines **how the product must be built**.

When implementing a feature:

```text
PRD.md
   ↓
Architecture
   ↓
API Contract
   ↓
Implementation
   ↓
Tests
```

Do not implement frontend behavior based on assumptions when the backend contract has not been defined.

---

# 2(A). Source of Truth

The following hierarchy defines the project's authoritative documentation.

When documents appear to conflict, the more specific document takes precedence
within its defined scope. If a conflict cannot be resolved, stop implementation
and ask for clarification rather than making assumptions.

1. Product Requirements
   docs/PRD.md

   Defines:
   - Product goals
   - User requirements
   - V1 scope
   - Functional requirements
   - Product behavior

2. Project Instructions
   docs/PROJECT_INSTRUCTIONS.md

   Defines:
   - Development rules
   - Coding standards
   - Engineering principles
   - AI/vibe-coding rules
   - Project-wide constraints

3. Architecture
   docs/ARCHITECTURE.md

   Defines:
   - System architecture
   - Components
   - Service boundaries
   - Data flow
   - Technology responsibilities

4. API Contracts
   docs/API_CONTRACT.md

   Defines:
   - API endpoints
   - Request schemas
   - Response schemas
   - Error contracts
   - Frontend/backend communication

5. Database Schema
   docs/DATABASE_SCHEMA.md

   Defines:
   - Database tables
   - Fields
   - Relationships
   - Constraints
   - Indexes
   - Persistence rules

6. State Machine
   docs/STATE_MACHINE.md

   Defines:
   - KYC workflow states
   - Valid state transitions
   - Retry behavior
   - Attempt lifecycle
   - Workflow rules

7. AI Specification
   docs/AI_SPECIFICATION.md

   Defines:
   - ASR behavior
   - LLM behavior
   - TTS behavior
   - AI provider responsibilities
   - AI conversation flow
   - AI output schemas

8. Roadmap
   docs/ROADMAP.md

   Defines:
   - Implementation phases
   - Development order
   - Milestones
   - Phase completion criteria

9. Implementation
   Source code

   Implements the requirements and contracts defined above.

   Source code must not silently redefine product requirements,
   API contracts, database rules, state transitions, or AI behavior.

If two documents conflict:

1. Stop implementation.
2. Identify the conflict.
3. Resolve the product/architecture decision.
4. Update the relevant documentation.
5. Continue implementation only after the conflict is resolved.

Never silently choose an implementation that contradicts the documented product behavior.

---

# 2(B). Conflict Resolution

When implementing a feature:

1. Check the PRD for product requirements.
2. Check PROJECT_INSTRUCTIONS.md for development rules.
3. Check ARCHITECTURE.md for system design.
4. Check API_CONTRACT.md for API behavior.
5. Check DATABASE_SCHEMA.md for persistence requirements.
6. Check STATE_MACHINE.md for workflow transitions.
7. Check AI_SPECIFICATION.md for AI-related behavior.
8. Check ROADMAP.md for implementation phase and scope.

If two documents conflict:

- Do not guess.
- Do not silently modify either document.
- Identify the conflict.
- Ask for clarification if the conflict affects implementation.

A document should only define rules within its scope.

# 3. Core Engineering Principles

The project must follow these principles:

1. Backend is the source of truth.
2. Frontend is a presentation and interaction layer.
3. Backend state controls workflow progression.
4. LLM does not control the KYC state machine.
5. LLM does not approve or reject KYC.
6. Human reviewer makes the final KYC decision.
7. Every attempt must be independently auditable.
8. Previous attempts must never be deleted.
9. External AI providers must be abstracted.
10. Business logic must remain provider-independent.
11. Sensitive data must not appear in normal logs.
12. API contracts must be defined before frontend integration.
13. Every meaningful state transition must be testable.
14. Recoverable failures use bounded retries.
15. Human-review retry creates a new attempt.
16. Security must be considered from the beginning, not added at the end.
17. Do not build functionality that is outside the approved V1 scope without explicitly updating the PRD.

---

# 4. Product Boundary

The V1 system includes:

```text
Existing KYC Case
        ↓
Video KYC Session
        ↓
Verification Attempt
        ↓
Continuous Recording
        ↓
Face Detection
        ↓
Liveness
        ↓
AI Questions
        ↓
All Uploaded Documents
        ↓
Document Capture
        ↓
Evidence Package
        ↓
Human Review
        ↓
Approve / Retry
```

V1 does not include automated face identity matching.

V1 does not include automated KYC approval or rejection.

---

# 5. Backend Authority

The backend owns the authoritative state of the Video KYC workflow.

The frontend must never independently decide that a step is complete.

Incorrect:

```text
Frontend:
"User completed liveness, so move to questions."
```

Correct:

```text
Frontend
   ↓
Submit liveness result
   ↓
Backend validates result
   ↓
Backend updates state
   ↓
Backend returns next state
   ↓
Frontend renders next state
```

The frontend must always follow the backend state.

---

# 6. State Machine

The Video KYC workflow must be implemented as an explicit state machine.

V1 flow:

```text
STARTED
   ↓
FACE
   ↓
LIVENESS
   ↓
GENERAL_QUESTIONS
   ↓
DOCUMENT_PRESENTATION
   ↓
DOCUMENT_CAPTURE
   ↓
RECORDING_COMPLETE
   ↓
EVIDENCE_PACKAGE_CREATED
   ↓
HUMAN_REVIEW
   ├── APPROVE → VERIFIED
   └── RETRY → NEW ATTEMPT → STARTED
```

State transitions must be:

- Explicit
- Validated
- Persisted
- Auditable
- Testable

Do not use scattered boolean flags as a replacement for the state machine.

Avoid designs such as:

```text
face_done = true
liveness_done = true
questions_done = true
```

without a centralized state representation.

---

# 7. Session and Attempt Model

The system must distinguish between:

```text
KYC Case
    ↓
Video KYC Session
    ↓
Verification Attempt
```

A KYC case may contain one Video KYC session.

A Video KYC session may contain multiple attempts.

Example:

```text
KYC Case
│
└── Video KYC Session
      │
      ├── Attempt 1
      │     └── RETRY
      │
      └── Attempt 2
            └── VERIFIED
```

Each attempt must have its own evidence.

Previous attempts must remain available for audit.

---

# 8. Attempt Isolation

An attempt must be treated as an independent verification run.

Attempt-specific data includes:

- Recording
- Audio
- Face result
- Liveness result
- Selected questions
- Answers
- Transcript
- Document captures
- Evidence package
- Audit events
- Reviewer decision

Do not overwrite Attempt 1 when Attempt 2 is created.

---

# 9. Retry Rules

There are two different retry mechanisms.

## 9.1 Step Retry

Used for recoverable failures during an active attempt.

Example:

```text
LIVENESS
   ↓
FAIL
   ↓
Retry
   ↓
LIVENESS
```

The attempt ID remains unchanged.

Example:

```text
attempt_id = attempt_001
```

---

## 9.2 Human-Review Retry

Used when the reviewer requests another KYC attempt.

Example:

```text
Attempt 1
   ↓
Human Review
   ↓
RETRY
   ↓
Create Attempt 2
   ↓
STARTED
```

A new attempt ID must be created.

Example:

```text
attempt_001
attempt_002
```

Attempt 1 must remain available.

---

# 10. Bounded Automatic Retry

Step-level retries must never be infinite.

Retry limits must be configurable.

Example:

```text
MAX_STEP_RETRIES=3
```

Possible configuration:

```json
{
  "face": 3,
  "liveness": 3,
  "document_capture": 5
}
```

The backend must determine whether the retry limit has been reached.

The frontend must not maintain the authoritative retry counter.

---

# 11. Continuous Recording

Every verification attempt uses one continuous recording.

Recording lifecycle:

```text
Start Attempt
    ↓
Start Recording
    ↓
Face
    ↓
Liveness
    ↓
Questions
    ↓
Document 1
    ↓
Document 2
    ↓
Document N
    ↓
Stop Recording
```

Do not create separate recordings for each normal workflow stage unless explicitly required by a future product change.

Recording start and stop must be recorded in audit events.

---

# 12. Camera and Microphone

The browser frontend is responsible for requesting:

- Camera permission
- Microphone permission

The frontend must clearly display:

- Camera status
- Microphone status
- Recording status
- Current workflow step
- User instructions

Permission failures must be handled gracefully.

Example:

```text
Camera permission denied
        ↓
Display clear instruction
        ↓
Allow user to retry permission
```

Do not expose raw browser errors directly to the user when a clearer message can be provided.

---

# 13. Face Detection

V1 only requires face detection.

The implementation must not add identity face matching unless explicitly approved.

Required conceptual flow:

```text
Camera
   ↓
Face Detection
   ↓
Face Quality / Presence
   ↓
Liveness
```

Future face matching should be implemented as a separate capability.

---

# 14. Liveness

Liveness must be implemented behind a dedicated abstraction.

Example:

```text
LivenessProvider
    ↓
evaluate()
    ↓
LivenessResult
```

Do not couple application logic directly to a specific liveness SDK.

The provider should be replaceable.

---

# 15. Question Configuration

Questions are administrator-configurable.

The system must support:

```text
Question Pool
    ↓
Configured Question Count
    ↓
Backend Random Selection
    ↓
Selected Question Sequence
```

Example:

```text
Question Pool = 20
Questions to Ask = 5
```

The backend randomly selects five questions.

The selected sequence must be stored for the attempt.

---

# 16. Question Selection Rules

Question selection must happen on the backend.

The frontend must never decide:

- Which questions are selected
- How many questions are selected
- The authoritative question order

The backend must store the selected question sequence.

Example:

```text
Question Pool
    ↓
Q7
Q2
Q15
Q19
Q4
```

The frontend receives the current question from the backend.

---

# 17. AI Conversation Architecture

The question flow is:

```text
Backend
   ↓
Question
   ↓
TTS
   ↓
User
   ↓
Speech
   ↓
ASR
   ↓
Transcript
   ↓
LLM
   ↓
Structured Understanding
   ↓
Backend
   ↓
Next Question
```

The LLM may understand and evaluate the user's answer.

The LLM must not decide:

```text
"Move to liveness"
"Move to document capture"
"Approve KYC"
"Reject KYC"
```

Those decisions belong to backend business logic and human review respectively.

---

# 18. Structured LLM Output

LLM responses must be structured.

Do not depend on free-form text parsing whenever structured output is possible.

Example:

```json
{
  "intent": "ANSWER",
  "answer": "My name is Rahul Sharma",
  "confidence": 0.96
}
```

The backend consumes this structured response.

The backend then decides how the workflow proceeds.

---

# 19. ASR Provider

V1 uses Groq for ASR.

Target model:

```text
whisper-large-v3
```

The application must use an abstraction such as:

```text
ASRProvider
    ↓
transcribe(audio)
    ↓
Transcript
```

Do not spread Groq-specific code throughout the application.

---

# 20. LLM Provider

V1 uses Groq.

Target model:

```text
openai/gpt-oss-120b
```

Use an abstraction:

```text
LLMProvider
    ↓
understand_answer(...)
    ↓
StructuredResult
```

Provider-specific implementation must remain isolated.

---

# 21. TTS Provider

V1 uses Deepgram.

Target model:

```text
flux-cliff-en
```

Use:

```text
TTSProvider
    ↓
synthesize(text)
    ↓
Audio
```

Do not couple question logic directly to Deepgram SDK calls.

---

# 22. Document Workflow

All uploaded documents belonging to the KYC case must be presented one by one.

Example:

```text
Document 1
   ↓
Capture
   ↓
Document 2
   ↓
Capture
   ↓
Document N
   ↓
Complete
```

The backend must know:

- Total documents
- Current document
- Captured documents
- Remaining documents

The frontend displays the current document instruction.

---

# 23. Document Frame

The frontend must provide a visible camera frame.

The purpose is to guide the user to position the document correctly.

Example:

```text
+--------------------------------+
|                                |
|      PLACE DOCUMENT HERE       |
|                                |
|     +--------------------+     |
|     |                    |     |
|     |      DOCUMENT      |     |
|     |                    |     |
|     +--------------------+     |
|                                |
+--------------------------------+
```

The frontend may provide visual feedback.

However, final capture validation must remain backend-controlled.

---

# 24. Document Capture

Each document capture must be associated with:

```text
case_id
session_id
attempt_id
document_id
document_type
capture_id
timestamp
storage_reference
```

Do not store document captures without their parent attempt context.

---

# 25. Evidence Package

Evidence is created after the attempt is completed.

Evidence may include:

```text
Continuous Recording
Audio
Face Result
Liveness Result
Questions
Answers
Transcript
Document Captures
Session Metadata
Attempt Metadata
Audit Events
```

Evidence should reference stored files rather than unnecessarily duplicating large binary data.

---

# 26. Storage

V1 uses local filesystem storage.

Storage must be abstracted:

```text
StorageProvider
    ↓
LocalStorageProvider
```

Example:

```text
storage/
└── video-kyc/
    ├── cases/
    ├── sessions/
    ├── attempts/
    ├── recordings/
    ├── audio/
    ├── documents/
    └── evidence/
```

Future cloud storage should be possible without changing business logic.

---

# 27. Database

V1 uses PostgreSQL.

PostgreSQL runs in Docker.

Database responsibilities include:

- KYC cases
- Video sessions
- Attempts
- States
- Questions
- Question selections
- Answers
- Document references
- Captures
- Evidence metadata
- Review decisions
- Audit events

Large media files must not be stored directly in PostgreSQL.

The database should store metadata and storage references.

---

# 28. API-First Development

API contracts must be defined before frontend integration.

Do not start frontend implementation with assumptions such as:

```text
"I think the backend will return current_step."
```

The contract must explicitly define:

- Endpoint
- HTTP method
- Authentication
- Request body
- Path parameters
- Query parameters
- Response body
- Error responses
- State behavior
- Validation rules

The API contract should live in:

```text
docs/API_CONTRACT.md
```

---

# 29. API Contract Example

Conceptual endpoint:

```text
POST /api/v1/kyc-cases/{case_id}/video-sessions
```

Conceptual response:

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "case_id": "case_001",
  "status": "STARTED",
  "current_step": "FACE"
}
```

This is an example of the expected contract style.

The actual contract must be finalized before implementation.

---

# 30. Frontend Rules

Frontend responsibilities:

- Render current backend state
- Capture camera
- Capture microphone
- Display instructions
- Record media
- Submit events/results
- Display errors
- Display question interaction
- Display document frame
- Capture document images

Frontend must not:

- Approve KYC
- Reject KYC
- Choose authoritative questions
- Advance backend state independently
- Create reviewer decisions
- Modify attempt IDs
- Bypass retry limits

---

# 31. Backend Rules

Backend responsibilities:

- Authentication
- Authorization
- State machine
- Session creation
- Attempt creation
- Question selection
- Retry rules
- Evidence management
- Review workflow
- Audit logging
- Provider orchestration
- Storage references
- Validation

The backend is the central workflow authority.

---

# 32. Human Review Rules

Human review is the final decision layer.

Reviewer actions:

```text
APPROVE
RETRY
```

The system must record:

```text
reviewer_id
decision
timestamp
attempt_id
reason / notes where applicable
```

AI output may assist the reviewer but cannot replace the reviewer.

---

# 33. Authentication and Authorization

Protected APIs must require authentication.

Authorization must be role-based.

At minimum, the system should distinguish appropriate roles such as:

```text
USER
ADMIN
REVIEWER
```

Users must only access resources they are authorized to access.

Reviewers must only be able to perform reviewer actions.

Administrative functionality must be restricted to authorized administrators.

---

# 34. Security

Never commit:

```text
API keys
Passwords
JWT secrets
Database passwords
Private credentials
```

Use environment variables.

Example:

```text
GROQ_API_KEY=
DEEPGRAM_API_KEY=
DATABASE_URL=
JWT_SECRET=
```

`.env` must be excluded from Git.

Provide:

```text
.env.example
```

with placeholders.

---

# 35. Sensitive Data Logging

Do not log:

- Full identity documents
- Raw document images
- Full video
- Full audio
- API keys
- Passwords
- Authentication tokens
- Sensitive personal information unnecessarily

Use IDs instead.

Good:

```text
attempt_id=attempt_001
document_id=doc_001
```

Bad:

```text
user_name=...
aadhaar_number=...
document_image=...
```

---

# 36. Audit Logging

Important workflow events must be recorded.

Examples:

```text
SESSION_CREATED
ATTEMPT_CREATED
RECORDING_STARTED
RECORDING_STOPPED
FACE_COMPLETED
LIVENESS_COMPLETED
QUESTION_SELECTED
QUESTION_ANSWERED
DOCUMENT_PRESENTED
DOCUMENT_CAPTURED
EVIDENCE_CREATED
REVIEW_APPROVED
REVIEW_RETRY
NEW_ATTEMPT_CREATED
```

Audit events must be associated with the correct:

```text
case_id
session_id
attempt_id
actor
timestamp
```

---

# 37. Error Handling

Errors must be categorized.

Examples:

```text
Validation Error
Authentication Error
Authorization Error
Resource Not Found
State Transition Error
Provider Error
Storage Error
Recording Error
Capture Error
```

Do not expose internal stack traces to users.

Frontend should receive safe, actionable error messages.

---

# 38. External Provider Failures

External services can fail.

Examples:

```text
Groq unavailable
Deepgram unavailable
Liveness provider unavailable
```

Provider failures must not corrupt the KYC state.

The backend should handle provider errors explicitly.

Where appropriate:

```text
Provider failure
      ↓
Retry / recover
      ↓
Continue only after successful result
```

Do not mark a step as successful merely because the provider request failed.

---

# 39. Provider Abstractions

Required abstraction boundaries:

```text
LLMProvider
ASRProvider
TTSProvider
LivenessProvider
FaceProvider
StorageProvider
```

Business logic should depend on interfaces/contracts rather than provider SDKs.

Example:

```text
QuestionService
      ↓
LLMProvider
      ↓
GroqLLMProvider
```

Not:

```text
QuestionService
      ↓
Groq SDK directly
```

---

# 40. Project Structure

Recommended structure:

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
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   └── workers/
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── state/
│   │
│   ├── tests/
│   ├── Dockerfile
│   └── package.json
│
├── storage/
│
├── docker-compose.yml
│
├── .env.example
├── .gitignore
└── README.md
```

The exact structure may be refined in `ARCHITECTURE.md`.

Do not create unnecessary directories merely to make the project appear more production-like.

---

# 41. Domain Separation

Business domains should remain separated.

Suggested domains:

```text
cases
sessions
attempts
recording
face
liveness
questions
conversation
documents
evidence
review
audit
```

Avoid putting all functionality into a single large service file.

---

# 42. Service Layer

Services should represent business operations.

Examples:

```text
VideoSessionService
AttemptService
QuestionService
ConversationService
DocumentService
RecordingService
EvidenceService
ReviewService
AuditService
```

Services should coordinate business logic.

They should not contain unrelated responsibilities.

---

# 43. Repository Layer

Database access should be isolated from business logic.

Example:

```text
AttemptService
      ↓
AttemptRepository
      ↓
PostgreSQL
```

Avoid embedding large amounts of raw database logic inside API route handlers.

---

# 44. API Route Rules

API routes should remain thin.

Preferred:

```text
API Route
   ↓
Validate Request
   ↓
Call Service
   ↓
Return Response
```

Avoid:

```text
API Route
   ↓
Database queries
   ↓
State machine
   ↓
LLM call
   ↓
File storage
   ↓
Question selection
   ↓
Everything
```

Complex business logic belongs in services/domain components.

---

# 45. Database Migration Rules

Database schema changes must use migrations.

Do not manually modify production-like databases without migration files.

Every schema change must be:

- Versioned
- Reproducible
- Reviewable

---

# 46. Testing Strategy

Testing is mandatory.

At minimum:

```text
Unit Tests
Integration Tests
End-to-End Tests
```

---

# 47. Unit Tests

Unit tests should cover:

- State transitions
- Retry limits
- Question selection
- Question count validation
- Attempt creation
- Document sequencing
- Evidence generation logic
- Authorization rules
- Provider response parsing

Example:

```text
test_liveness_failure_allows_retry()
test_retry_limit_is_enforced()
test_new_attempt_created_after_review_retry()
test_all_documents_are_selected()
test_question_selection_returns_n_questions()
```

---

# 48. Integration Tests

Integration tests should cover:

- PostgreSQL
- Storage
- API endpoints
- Provider adapters
- Authentication
- Authorization

External AI providers should be mocked where appropriate.

---

# 49. End-to-End Tests

The primary E2E flow should test:

```text
Create/Load KYC Case
      ↓
Start Video KYC
      ↓
Start Recording
      ↓
Face
      ↓
Liveness
      ↓
Questions
      ↓
Documents
      ↓
Stop Recording
      ↓
Evidence
      ↓
Human Review
      ↓
Approve
      ↓
Verified
```

A separate E2E test must verify:

```text
Human Review
      ↓
Retry
      ↓
New Attempt
      ↓
Start From Beginning
```

---

# 50. Test Provider Abstractions

Provider interfaces must be testable without requiring real external API calls.

Use fake/mock implementations where appropriate.

Example:

```text
FakeLLMProvider
FakeASRProvider
FakeTTSProvider
FakeLivenessProvider
FakeStorageProvider
```

This makes tests deterministic.

---

# 51. Frontend Testing

Frontend tests should verify:

- Camera UI
- Permission states
- Recording state
- Backend state rendering
- Question display
- Document frame
- Capture controls
- Error states
- Retry states

Frontend tests must not assume state transitions that are not present in the API contract.

---

# 52. API Contract Testing

Once `API_CONTRACT.md` is finalized, frontend and backend implementations must follow it.

API contract changes require:

1. Update contract.
2. Update backend.
3. Update frontend.
4. Update tests.
5. Verify compatibility.

Do not silently change response structures.

---

# 53. Configuration

Centralize configuration.

Use environment variables for environment-specific settings.

Example:

```text
APP_ENV
DATABASE_URL

GROQ_API_KEY
GROQ_LLM_MODEL
GROQ_ASR_MODEL

DEEPGRAM_API_KEY
DEEPGRAM_TTS_MODEL

LOCAL_STORAGE_ROOT

MAX_STEP_RETRIES
```

Do not scatter configuration values throughout source files.

---

# 54. Docker

V1 must run using Docker.

Expected services:

```text
frontend
backend
postgres
```

External APIs remain external:

```text
Groq
Deepgram
```

The local filesystem is mounted appropriately for persistent development storage.

---

# 55. Docker Development Rules

The project should support a simple development workflow such as:

```text
docker compose up
```

The exact commands will be documented in `README.md`.

Containers should have clear responsibilities.

Do not combine PostgreSQL, backend, and frontend into one container.

---

# 56. Environment Separation

At minimum, support:

```text
development
testing
production
```

Development may use local filesystem storage.

Production architecture may later use cloud/object storage.

Do not hardcode development assumptions into business logic.

---

# 57. Logging

Use structured logging where practical.

Logs should include safe identifiers:

```text
case_id
session_id
attempt_id
event
timestamp
```

Do not log sensitive data unnecessarily.

Use appropriate log levels:

```text
DEBUG
INFO
WARNING
ERROR
```

---

# 58. Observability

The system should make it possible to determine:

- Which case is active
- Which session is active
- Which attempt is active
- Current state
- Provider errors
- Recording failures
- Document capture failures
- Review decisions

Observability must not compromise sensitive user information.

---

# 59. API Versioning

APIs should be versioned.

Preferred pattern:

```text
/api/v1/...
```

Avoid breaking existing APIs without an explicit versioning decision.

---

# 60. Data Ownership

Every piece of KYC evidence must have clear ownership.

Use relationships such as:

```text
case_id
session_id
attempt_id
```

Avoid orphaned media or evidence.

If an artifact cannot be associated with a valid attempt, the system should treat it as an error condition.

---

# 61. State Transition Validation

Before every state transition, the backend must verify:

1. Current state is valid.
2. Requested transition is allowed.
3. Required data exists.
4. Required previous step succeeded.
5. Retry limits are respected.
6. Attempt is still active.

Example:

```text
FACE
  ↓
LIVENESS
```

is valid.

But:

```text
FACE
  ↓
DOCUMENT_CAPTURE
```

must not be allowed unless the workflow explicitly supports that transition.

---

# 62. Idempotency

Important API operations should be designed with idempotency where appropriate.

Examples:

```text
Start session
Create attempt
Submit capture
Complete recording
Create evidence
```

Repeated client requests should not accidentally create duplicate resources.

---

# 63. Concurrency

The backend must protect state transitions from concurrent requests.

Example:

```text
Two requests attempt:

LIVENESS → GENERAL_QUESTIONS
```

Only one valid transition should be committed.

Database transactions/locking should be used where appropriate.

---

# 64. Media Uploads

Large media uploads should not unnecessarily pass through memory-heavy application paths.

The implementation should consider:

- Streaming
- Chunking
- File size limits
- MIME validation
- Storage lifecycle
- Cleanup of incomplete uploads

Exact implementation can be defined in `ARCHITECTURE.md`.

---

# 65. File Validation

Uploaded/captured files must be validated.

Validate:

- File type
- MIME type
- Size
- Expected format
- File integrity where applicable

Never trust client-provided filenames or MIME types alone.

---

# 66. Security Boundaries

Treat these as sensitive boundaries:

```text
Browser → Backend
Backend → Database
Backend → Storage
Backend → Groq
Backend → Deepgram
Reviewer → Evidence
```

Every boundary must have appropriate authentication, authorization, validation, and error handling.

---

# 67. No Hidden Business Logic

Do not place important business decisions inside:

- React components
- API serializers
- Database models
- Provider SDK wrappers

Business rules should live in appropriate domain/service components.

---

# 68. No Premature AI Complexity

Do not introduce an AI agent framework merely because the project uses AI.

The V1 workflow is deterministic.

Use:

```text
Backend State Machine
+
Provider Services
+
LLM for Answer Understanding
```

rather than an autonomous agent controlling the KYC process.

---

# 69. No Premature Microservices

V1 should start as a modular application.

Do not split into many independent microservices unless there is a clear requirement.

Preferred initial architecture:

```text
Frontend
   ↓
Backend Application
   ↓
PostgreSQL
   +
Local Storage
   +
External AI Providers
```

Internal modules should remain well separated so services can be extracted later if necessary.

---

# 70. Development Workflow

For each feature:

```text
1. Read PRD
2. Confirm requirements
3. Update architecture if needed
4. Define API contract
5. Define database changes
6. Implement backend
7. Implement provider abstraction
8. Implement frontend
9. Add tests
10. Run tests
11. Verify end-to-end flow
12. Update documentation
```

Do not skip API design for features involving frontend/backend interaction.

---

# 71. Feature Implementation Rule

Before implementing a feature, identify:

```text
What is the requirement?
What state does it belong to?
What data does it need?
What API is required?
What database changes are required?
What provider is required?
What failure cases exist?
What retry behavior exists?
What tests are required?
```

---

# 72. Definition of Done

A feature is not complete when the code merely works locally.

A feature is complete when:

- Requirement is implemented.
- API contract is defined.
- Backend validation exists.
- Frontend integration exists where required.
- Error handling exists.
- Retry behavior is defined.
- Tests exist.
- Security considerations are addressed.
- Audit requirements are addressed.
- Documentation is updated.
- Existing functionality is not broken.

---

# 73. Git Rules

Do not commit:

```text
.env
.env.local
API keys
Secrets
Passwords
Large generated media
Temporary recordings
Temporary captures
Local database files
Python virtual environments
Node modules
Build artifacts
```

Use `.gitignore`.

Commit source code, configuration templates, migrations, tests, and documentation.

---

# 74. Commit Strategy

Commits should represent logical changes.

Good:

```text
feat: add video session creation
feat: implement liveness state
feat: add question selection service
feat: add document capture flow
test: add attempt retry tests
docs: define video kyc api contract
```

Avoid huge commits containing unrelated changes.

---

# 75. Documentation Rules

Documentation must be updated when behavior changes.

Important documents:

```text
docs/
├── PRD.md
├── PROJECT_INSTRUCTIONS.md
├── ARCHITECTURE.md
├── API_CONTRACT.md
├── ROADMAP.md
└── SECURITY.md
```

Documentation must not describe functionality that does not exist unless clearly marked as planned.

---

# 76. Change Management

When a requirement changes:

```text
Requirement Change
       ↓
Update PRD
       ↓
Review Architecture
       ↓
Update API Contract
       ↓
Update Database Design
       ↓
Update Implementation
       ↓
Update Tests
       ↓
Update Roadmap
```

Do not modify code first and document the change afterward.

---

# 77. V1 Technology Constraints

The following are fixed for V1:

```text
Frontend:
Local browser + Docker

Backend:
Python/FastAPI + Docker

Database:
PostgreSQL + Docker

Storage:
Local filesystem

LLM:
Groq

ASR:
Groq Whisper Large V3

TTS:
Deepgram

Face:
Face detection only

Liveness:
Dedicated provider abstraction
```

Changing one of these requires an explicit architecture/product decision.

---

# 78. V1 AI Responsibility

AI is responsible for assistance.

```text
LLM
 ├── Understand user response
 ├── Extract answer
 └── Evaluate semantic response

ASR
 └── Convert speech to text

TTS
 └── Convert question to speech

Liveness
 └── Assess liveness

Face Detection
 └── Detect face
```

AI is not responsible for:

```text
Final KYC approval
Final KYC rejection
Workflow state authority
Reviewer decisions
```

---

# 79. Final Architecture Principle

The system should follow:

```text
                    USER
                      |
                      v
                  FRONTEND
                      |
                      v
                BACKEND API
                      |
                      v
              STATE MACHINE
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Services    Providers    Storage
          |           |           |
          |      +----+----+      |
          |      |         |      |
          |     Groq    Deepgram  |
          |                        |
          +----------+-------------+
                     |
                     v
                 PostgreSQL
```

The architecture must remain deterministic even though AI components are probabilistic.

---

# 80. Final Engineering Rule

When in doubt, follow this hierarchy:

```text
PRODUCT REQUIREMENT
        ↓
BACKEND STATE MACHINE
        ↓
API CONTRACT
        ↓
BUSINESS LOGIC
        ↓
AI PROVIDERS
        ↓
FRONTEND PRESENTATION
```

Never reverse this hierarchy.

The frontend must not define the backend workflow.

The LLM must not define the KYC workflow.

The AI must not make the final KYC decision.

The backend controls the workflow.

The human reviewer makes the final decision.

---

# 81. Final V1 Flow

The complete implementation must ultimately support:

```text
EXISTING KYC CASE
        |
        v
USER CLICKS START VIDEO KYC
        |
        v
CREATE SESSION
        |
        v
CREATE ATTEMPT
        |
        v
START CONTINUOUS RECORDING
        |
        v
FACE DETECTION
        |
        +---- FAIL → BOUNDED RETRY
        |
        v
LIVENESS
        |
        +---- FAIL → BOUNDED RETRY
        |
        v
GENERAL QUESTIONS
        |
        v
BACKEND RANDOMLY SELECTS N QUESTIONS
        |
        v
AI ASKS QUESTION
        |
        v
USER SPEAKS
        |
        v
ASR
        |
        v
LLM UNDERSTANDS ANSWER
        |
        v
NEXT QUESTION
        |
        v
ALL QUESTIONS COMPLETE
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
        +---- FAIL → BOUNDED RETRY
        |
        v
DOCUMENT 2
        |
        v
...
        |
        v
ALL DOCUMENTS CAPTURED
        |
        v
STOP RECORDING
        |
        v
CREATE EVIDENCE PACKAGE
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
    VERIFIED           CREATE NEW ATTEMPT
                            |
                            v
                         STARTED
```

This flow is the baseline engineering contract for V1.