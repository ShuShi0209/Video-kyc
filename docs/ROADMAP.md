# Video KYC — Development Roadmap

**Version:** 1.0  
**Status:** V1 Development Roadmap  
**Environment:** Local + Docker  
**Storage:** Local Filesystem  
**Database:** PostgreSQL  
**AI Providers:** Groq + Deepgram

---

# 1. Project Goal

Build an AI-assisted Video KYC system where an existing KYC case contains uploaded documents and the user completes a live verification session.

The V1 flow is:

```text
Existing KYC Case
      ↓
Start Video KYC
      ↓
Continuous Recording
      ↓
Face Detection
      ↓
Liveness / Anti-Spoof
      ↓
AI General Questions
      ↓
Document Presentation
      ↓
Document Capture
      ↓
Recording Stops
      ↓
Evidence Package
      ↓
Human Review
      ↓
   APPROVE / RETRY
      ↓
   VERIFIED / New Attempt
```

---

# 2. V1 Scope

V1 includes:

- Existing KYC case
- Uploaded reference documents
- Video KYC session
- Continuous camera recording
- Microphone recording
- Face detection
- Liveness / anti-spoofing
- Admin-configurable question pool
- Random selection of N questions
- Speech-to-text
- LLM-based answer understanding
- AI-driven question flow
- Document presentation
- Document camera frame
- Document capture
- Evidence package
- Human review
- Approve / Retry
- Automatic step retries
- New attempt after human-review retry
- PostgreSQL
- Local filesystem storage
- Docker development environment
- Groq API
- Deepgram API

---

# 3. Explicit V1 Non-Goals

The following are not required for V1:

- Face identity matching
- Advanced face recognition
- Document OCR
- Document authenticity verification
- Cloud object storage
- Production deployment
- Advanced fraud scoring
- Automated final KYC approval
- Fully autonomous KYC decision-making
- Multi-tenant SaaS architecture
- Advanced analytics
- Webhook system
- Mobile applications

These may be added in later versions.

---

# 4. Development Principles

The project should be implemented in phases.

Each phase must be completed and tested before moving to the next phase.

The implementation should follow:

```text
Requirements
    ↓
Architecture
    ↓
API Contract
    ↓
Database
    ↓
Backend
    ↓
Frontend
    ↓
AI Integration
    ↓
Evidence
    ↓
Human Review
    ↓
End-to-End Testing
```

Do not build the entire application at once.

---

# 5. Phase 0 — Project Foundation

## Goal

Create the initial project structure and development environment.

## Tasks

- Create repository
- Create backend project
- Create frontend project
- Create Docker configuration
- Create PostgreSQL container
- Configure environment variables
- Configure `.env.example`
- Configure Git
- Configure `.gitignore`
- Create documentation structure
- Configure local development commands

## Documentation

Required:

```text
docs/
├── PRD.md
├── PROJECT_INSTRUCTIONS.md
├── ARCHITECTURE.md
├── API_CONTRACT.md
└── ROADMAP.md
```

## Deliverable

The project should start locally with:

```text
Frontend
Backend
PostgreSQL
```

---

# 6. Phase 1 — Database Foundation

## Goal

Create the persistent data model.

## Core entities

Initial entities:

```text
KYC Case
Document
Video Session
Attempt
Recording
Question
Question Configuration
Answer
Document Capture
Evidence Package
Review
Audit Event
```

## Tasks

- Create PostgreSQL schema
- Create migrations
- Create database models
- Create repositories
- Add indexes where required
- Add foreign-key relationships
- Add timestamps
- Add status fields
- Add attempt numbering
- Add audit event storage

## Deliverable

Backend can create and retrieve a complete KYC case structure.

---

# 7. Phase 2 — Existing KYC Case

## Goal

Represent an existing KYC case containing uploaded documents.

Example:

```text
KYC Case
   |
   +── Aadhaar
   |
   +── PAN
   |
   +── Other Documents
```

## Tasks

- Create KYC case API
- Create document API
- Store document metadata
- Store reference documents in local filesystem
- Associate documents with KYC case
- Validate document ownership
- Implement document retrieval

## Deliverable

The system can display an existing KYC case and its uploaded documents.

---

# 8. Phase 3 — Video KYC Session

## Goal

Create a Video KYC session from an existing case.

## API

```text
POST /api/v1/kyc-cases/{case_id}/video-sessions
```

## Tasks

- Create session
- Create first attempt
- Set initial workflow state
- Return session information
- Return uploaded document list
- Implement session retrieval
- Implement attempt retrieval

## Deliverable

User can click:

```text
Start Video KYC
```

and receive:

```text
session_id
attempt_id
current_step
```

---

# 9. Phase 4 — Continuous Recording

## Goal

Start continuous recording at the beginning of the live session.

## Flow

```text
Start Video KYC
      ↓
Camera Permission
      ↓
Microphone Permission
      ↓
Recording Starts
      ↓
Face
      ↓
Liveness
      ↓
Questions
      ↓
Documents
      ↓
Recording Stops
```

## Tasks

- Implement browser camera access
- Implement microphone access
- Implement MediaRecorder
- Start recording
- Maintain recording during session
- Handle recording errors
- Stop recording
- Upload recording
- Store recording metadata
- Associate recording with attempt

## Deliverable

One continuous recording covers the live session.

---

# 10. Phase 5 — Face Detection

## Goal

Detect whether a valid face is present.

V1 does not perform identity matching.

## Tasks

- Implement face detection
- Detect face count
- Validate basic face quality
- Detect missing face
- Detect multiple faces
- Return structured result
- Implement automatic retries
- Persist face verification result
- Create audit event

## Success

```text
Face detected
      ↓
PASS
      ↓
LIVENESS
```

## Failure

```text
Face not detected
      ↓
RETRY
      ↓
Face step again
```

---

# 11. Phase 6 — Liveness / Anti-Spoof

## Goal

Determine whether the user appears to be a live person rather than a spoof.

## Tasks

- Integrate liveness mechanism
- Normalize provider/application response
- Store liveness result
- Store liveness score where available
- Implement retry handling
- Handle provider failures
- Create audit events

## Flow

```text
Face
 ↓
Liveness
 ↓
PASS
 ↓
Questions
```

---

# 12. Phase 7 — Retry State Machine

## Goal

Implement automatic retries within the same attempt.

Example:

```text
Liveness
   ↓
FAIL
   ↓
Retry 1
   ↓
FAIL
   ↓
Retry 2
   ↓
PASS
```

## Rules

The backend owns retry counts.

Frontend only displays the returned state.

Example:

```json
{
  "retry": {
    "allowed": true,
    "retry_count": 1,
    "max_retries": 3
  }
}
```

## Deliverable

Automatic retry behavior works consistently across supported steps.

---

# 13. Phase 8 — Admin Question Management

## Goal

Allow administrators to configure the question pool.

## Tasks

- Create question
- Update question
- Activate/deactivate question
- Delete or archive question
- List questions
- Categorize questions
- Configure number of questions
- Configure random selection

## Example

```text
Question Pool

Q1: What is your full name?
Q2: What is your date of birth?
Q3: What is your current address?
Q4: What is the purpose of this KYC?
Q5: What is your occupation?
```

Configuration:

```text
Question Count = 3
Random Selection = true
```

---

# 14. Phase 9 — AI Question Engine

## Goal

Implement the conversational question flow.

Architecture:

```text
AI asks question
      ↓
User speaks
      ↓
ASR
      ↓
Transcript
      ↓
LLM
      ↓
Answer understanding
      ↓
Next question
```

## Tasks

- Select N questions randomly
- Persist selected questions
- Maintain question sequence
- Generate TTS
- Capture user audio
- Send audio to ASR
- Store transcript
- Send transcript to LLM
- Evaluate answer
- Move to next question
- Detect question completion
- Handle provider errors

---

# 15. Phase 10 — Deepgram Integration

## Goal

Integrate Deepgram for speech-to-text.

## Tasks

- Configure API key
- Implement provider service
- Send user audio
- Receive transcript
- Normalize response
- Handle timeout
- Handle provider errors
- Store transcript
- Hide provider details from frontend

## Backend architecture

```text
Conversation Service
        ↓
ASR Interface
        ↓
Deepgram Adapter
```

The rest of the backend should not depend directly on Deepgram-specific implementation details.

---

# 16. Phase 11 — Groq Integration

## Goal

Use Groq for LLM-based answer understanding and conversation logic.

## Tasks

- Configure API key
- Implement LLM service
- Create structured evaluation prompt
- Evaluate answer relevance
- Determine whether answer is understood
- Handle malformed responses
- Handle provider errors
- Store evaluation result

The frontend must never communicate directly with Groq.

---

# 17. Phase 12 — TTS

## Goal

Allow the AI to speak questions to the user.

## Flow

```text
Question
   ↓
Backend
   ↓
TTS Provider
   ↓
Audio
   ↓
Frontend
   ↓
User hears question
```

## Tasks

- Create TTS service interface
- Integrate selected TTS provider
- Generate question audio
- Return playable audio
- Handle provider failures
- Cache where useful

The frontend should only interact with the application API.

---

# 18. Phase 13 — Document Presentation

## Goal

Ask the user to present uploaded documents.

For V1:

```text
Show all uploaded documents
one by one
```

## Flow

```text
Questions Complete
       ↓
Document 1
       ↓
"Please show the same document you uploaded."
       ↓
Capture
       ↓
Document 2
       ↓
Capture
       ↓
...
```

## Tasks

- Retrieve documents for current attempt
- Determine document sequence
- Display document type
- Display instruction
- Move to next document
- Persist presentation state

---

# 19. Phase 14 — Document Camera Frame

## Goal

Help the user position the document correctly before capture.

Frontend displays:

```text
+--------------------------------+
|                                |
|      PUT DOCUMENT HERE         |
|                                |
|     ┌──────────────────┐       |
|     │                  │       |
|     │    DOCUMENT      │       |
|     │                  │       |
|     └──────────────────┘       |
|                                |
+--------------------------------+
```

## Tasks

- Create camera frame overlay
- Show positioning instructions
- Detect basic document presence
- Check image quality
- Capture document image
- Send capture to backend
- Display capture result
- Allow automatic retries

---

# 20. Phase 15 — Document Capture

## Goal

Capture the same documents that were uploaded to the KYC case.

## Tasks

- Capture document image
- Validate image
- Store capture
- Associate capture with original document
- Track sequence
- Handle low-quality capture
- Support automatic retries
- Create audit events

V1 does not require advanced document authenticity verification.

---

# 21. Phase 16 — Recording Completion

## Goal

Stop the continuous recording after document capture is complete.

## Flow

```text
Last Document Captured
        ↓
Recording Stops
        ↓
Recording Upload Complete
        ↓
Evidence Creation
```

## Tasks

- Stop MediaRecorder
- Upload final recording
- Confirm recording completion
- Update attempt state
- Create audit event

---

# 22. Phase 17 — Evidence Package

## Goal

Create a complete evidence package for human review.

Evidence should contain references to:

```text
Continuous Recording
Face Result
Liveness Result
Questions
Transcripts
Answer Evaluations
Original Documents
Captured Documents
Audit Events
```

## Tasks

- Create evidence package
- Associate all evidence
- Validate required evidence
- Generate evidence metadata
- Mark evidence package ready for review

---

# 23. Phase 18 — Human Review

## Goal

Allow an admin/reviewer to review the evidence package.

Flow:

```text
Evidence Package
       ↓
Human Reviewer
       ↓
+-------------+
|             |
APPROVE      RETRY
|             |
↓             ↓
VERIFIED   NEW ATTEMPT
```

## Tasks

- Create review queue
- List pending reviews
- Open evidence
- Review recording
- Review liveness
- Review questions
- Review document captures
- Add reviewer notes
- Approve
- Retry

---

# 24. Phase 19 — Human Review Retry

## Goal

Create a completely new attempt when a reviewer selects Retry.

Flow:

```text
Attempt 1
   ↓
Human Review
   ↓
RETRY
   ↓
Attempt 2
   ↓
STARTED
```

The new attempt starts from the beginning.

The previous attempt remains preserved for audit/history.

---

# 25. Phase 20 — Session Recovery

## Goal

Recover the session after browser refresh or temporary connection loss.

## Tasks

- Implement session state endpoint
- Restore current attempt
- Restore current step
- Restore question state
- Restore document state
- Handle reconnect
- Handle stale session
- Prevent invalid state transitions

---

# 26. Phase 21 — Frontend Integration

## Goal

Connect the frontend to the finalized backend APIs.

Frontend structure should use centralized API services.

Example:

```text
frontend/src/
├── api/
│   ├── client.ts
│   ├── sessions.ts
│   ├── attempts.ts
│   ├── questions.ts
│   ├── documents.ts
│   ├── recordings.ts
│   ├── evidence.ts
│   └── reviews.ts
│
├── components/
├── pages/
├── hooks/
├── types/
└── utils/
```

## Tasks

- Implement API client
- Implement TypeScript API types
- Implement session state
- Implement workflow screens
- Implement camera
- Implement microphone
- Implement recording
- Implement question UI
- Implement document UI
- Implement retry UI
- Implement error UI

---

# 27. Phase 22 — API Contract Testing

## Goal

Verify that frontend and backend follow `API_CONTRACT.md`.

## Tasks

Test:

```text
Start session
Start recording
Face
Liveness
Questions
Answers
Document capture
Stop recording
Evidence
Review
Approve
Retry
```

Also test:

```text
401
403
404
409
422
500
Provider failure
Network failure
Invalid state
Retry limit
```

---

# 28. Phase 23 — End-to-End Testing

## Goal

Test the complete V1 workflow.

### Successful flow

```text
Existing Case
    ↓
Start KYC
    ↓
Recording
    ↓
Face PASS
    ↓
Liveness PASS
    ↓
Questions PASS
    ↓
Documents Captured
    ↓
Recording Stops
    ↓
Evidence Created
    ↓
Human Review
    ↓
APPROVE
    ↓
VERIFIED
```

### Automatic retry flow

```text
Face
 ↓
FAIL
 ↓
Retry
 ↓
PASS
 ↓
Continue
```

### Human retry flow

```text
Attempt 1
 ↓
Review
 ↓
RETRY
 ↓
Attempt 2
 ↓
STARTED
```

---

# 29. Phase 24 — Failure Testing

Test failure scenarios:

## Camera

```text
Camera permission denied
Camera unavailable
Camera disconnects
```

## Microphone

```text
Microphone permission denied
Microphone unavailable
```

## Recording

```text
Recording fails
Upload fails
Browser interruption
```

## Face

```text
No face
Multiple faces
Poor quality
```

## Liveness

```text
Liveness fail
Provider unavailable
Timeout
```

## AI

```text
ASR failure
LLM failure
TTS failure
Malformed LLM output
```

## Documents

```text
Poor quality
No document
Incorrect positioning
Upload failure
```

## Network

```text
Request timeout
Connection lost
Duplicate request
Browser refresh
```

---

# 30. Phase 25 — Security Hardening

Before considering V1 complete:

- Validate authentication
- Validate authorization
- Validate case ownership
- Validate attempt ownership
- Validate uploaded files
- Prevent path traversal
- Hide API keys
- Hide provider errors
- Validate media types
- Apply upload size limits
- Protect reviewer APIs
- Protect admin APIs
- Add audit logging
- Avoid sensitive information in logs

---

# 31. Phase 26 — Dockerization

## Goal

Run the entire V1 environment using Docker.

Services:

```text
Frontend
Backend
PostgreSQL
```

Local storage remains mounted as a Docker volume.

Conceptually:

```text
Docker
│
├── frontend
├── backend
├── postgres
└── local-storage volume
```

Groq and Deepgram remain external APIs.

---

# 32. Phase 27 — Local Deployment

V1 target environment:

```text
Frontend → Local Browser + Docker
Backend  → Local Machine + Docker
Database → PostgreSQL + Docker
Storage  → Local Filesystem
Groq     → API
Deepgram → API
```

## Deliverable

A developer should be able to start the project with a documented Docker command and run the complete KYC flow locally.

---

# 33. Phase 28 — V1 Acceptance Testing

V1 is considered functionally complete when:

### Session

- [ ] Existing KYC case can start Video KYC
- [ ] Session is created
- [ ] Attempt is created

### Recording

- [ ] Camera works
- [ ] Microphone works
- [ ] Continuous recording starts
- [ ] Recording stops correctly
- [ ] Recording is stored

### Face

- [ ] Face detection works
- [ ] Face failure triggers retry
- [ ] Retry limit works

### Liveness

- [ ] Liveness works
- [ ] Liveness failure triggers retry
- [ ] Provider failure is handled

### Questions

- [ ] Admin can create questions
- [ ] Admin can activate/deactivate questions
- [ ] Admin can configure N
- [ ] Questions are randomly selected
- [ ] User can answer questions
- [ ] ASR works
- [ ] LLM evaluates answers
- [ ] AI asks the next question
- [ ] Question sequence is persisted

### Documents

- [ ] All uploaded documents are presented
- [ ] Document frame is displayed
- [ ] Document capture works
- [ ] Poor capture can retry
- [ ] Captures are stored

### Evidence

- [ ] Evidence package is created
- [ ] Recording is included
- [ ] Face result is included
- [ ] Liveness result is included
- [ ] Questions/transcripts are included
- [ ] Document captures are included

### Review

- [ ] Reviewer sees pending case
- [ ] Reviewer can inspect evidence
- [ ] Reviewer can approve
- [ ] Reviewer can retry
- [ ] Retry creates new attempt
- [ ] New attempt starts from beginning

---

# 34. Recommended Implementation Order

The recommended implementation sequence is:

```text
1. Project Foundation
        ↓
2. Database
        ↓
3. Existing KYC Case
        ↓
4. Video Session
        ↓
5. API State Machine
        ↓
6. Recording
        ↓
7. Face Detection
        ↓
8. Liveness
        ↓
9. Retry System
        ↓
10. Question Management
        ↓
11. ASR
        ↓
12. LLM
        ↓
13. TTS
        ↓
14. Document Presentation
        ↓
15. Document Frame
        ↓
16. Document Capture
        ↓
17. Evidence Package
        ↓
18. Human Review
        ↓
19. Review Retry
        ↓
20. Session Recovery
        ↓
21. Frontend Integration
        ↓
22. Testing
        ↓
23. Security
        ↓
24. Docker
        ↓
25. V1 Acceptance
```

---

# 35. Important Development Rule

Do not start full frontend integration until these documents are stable:

```text
PRD.md
PROJECT_INSTRUCTIONS.md
ARCHITECTURE.md
API_CONTRACT.md
ROADMAP.md
```

The implementation should follow the API contract instead of allowing frontend and backend to independently invent interfaces.

---

# 36. Definition of Done

A phase is complete only when:

```text
Implementation
     +
Tests
     +
Error Handling
     +
Documentation
```

are complete.

A feature should not be marked complete merely because the happy path works.

---

# 37. V1 Final Architecture

The completed V1 system should follow:

```text
                    USER
                     │
                     ▼
              ┌──────────────┐
              │   FRONTEND   │
              │              │
              │ Camera       │
              │ Microphone   │
              │ KYC UI       │
              └──────┬───────┘
                     │
                     │ HTTP API
                     ▼
              ┌──────────────┐
              │   BACKEND    │
              │              │
              │ State Machine│
              │ KYC Service  │
              │ AI Services  │
              │ Evidence     │
              │ Review       │
              └──────┬───────┘
                     │
          ┌──────────┼───────────┐
          │          │           │
          ▼          ▼           ▼
     PostgreSQL   Filesystem   AI APIs
                              │
                         ┌────┴────┐
                         ▼         ▼
                       Groq    Deepgram
```

---

# 38. Final V1 Flow

```text
┌──────────────────────────┐
│ EXISTING KYC CASE        │
│ Uploaded Documents       │
└────────────┬─────────────┘
             │
             ▼
      ┌──────────────┐
      │ START KYC    │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ START RECORD │
      │ Camera + Mic │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ FACE         │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ LIVENESS     │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ AI QUESTIONS │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ DOCUMENT 1   │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ DOCUMENT 2   │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ STOP RECORD  │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ EVIDENCE     │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ HUMAN REVIEW │
      └──────┬───────┘
             │
       ┌─────┴─────┐
       ▼           ▼
    APPROVE       RETRY
       │           │
       ▼           ▼
   VERIFIED    NEW ATTEMPT
                   │
                   ▼
                STARTED
```

---

# 39. Post-V1 Roadmap

After V1 is stable, future phases can add:

## V1.1

- Better document quality detection
- Better camera guidance
- Improved conversation handling
- Better reviewer UI
- Improved evidence viewer

## V2

- Face matching against uploaded/reference identity
- OCR
- Document field extraction
- Document authenticity checks
- Advanced liveness
- Risk scoring
- Automated fraud signals

## V3

- Cloud object storage
- Production deployment
- Multi-tenant architecture
- Advanced analytics
- Webhooks
- Enterprise authentication
- Scalable background processing

---

# 40. Final Roadmap Principle

Build the system in this order:

```text
Stable Contracts
      ↓
Reliable Backend State
      ↓
Working Media Pipeline
      ↓
AI Services
      ↓
Document Verification
      ↓
Evidence
      ↓
Human Review
      ↓
Testing
      ↓
Production Hardening
```

Do not optimize for AI complexity first.

The core V1 objective is:

> **Create a reliable, auditable, state-driven Video KYC workflow in which the user completes a continuous recorded session, the system performs face/liveness checks and AI-assisted questions, the user presents all uploaded documents, and a human reviewer makes the final APPROVE/RETRY decision.**