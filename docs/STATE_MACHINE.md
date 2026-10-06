# Video KYC State Machine

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 Workflow Specification

---

# 1. Purpose

This document defines the authoritative workflow state machine for the Video KYC system.

The backend owns the state machine.

The frontend displays the state returned by the backend.

The frontend must never independently decide the authoritative next KYC step.

---

# 2. Core Principle

```text
Frontend
   │
   │ command
   ▼
Backend State Machine
   │
   │ validate
   ▼
State Transition
   │
   ▼
Persist State
   │
   ▼
Return New State
   │
   ▼
Frontend renders UI
```

---

# 3. Complete V1 Workflow

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
   └── RETRY   → NEW ATTEMPT → STARTED
```

---

# 4. States

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

---

# 5. STARTED

## Purpose

Initial state after a Video KYC attempt is created.

## Entry

```text
Existing KYC Case
       ↓
Start Video KYC
       ↓
Create Session
       ↓
Create Attempt
       ↓
STARTED
```

## Actions

- Create attempt
- Set attempt number
- Initialize retry counters
- Prepare document sequence
- Start continuous recording

## Next state

```text
FACE
```

---

# 6. FACE

## Purpose

Detect whether a suitable face is visible.

V1 does not perform identity matching.

## Success

```text
Face detected
      ↓
FACE PASS
      ↓
LIVENESS
```

## Failure

```text
Face detection failure
      ↓
Retry
      ↓
FACE
```

---

# 7. Face Retry

Default V1:

```text
Maximum automatic retries = 3
```

Example:

```text
FACE
 ↓
FAIL
 ↓
retry_count = 1
 ↓
FACE
 ↓
FAIL
 ↓
retry_count = 2
 ↓
FACE
 ↓
PASS
 ↓
LIVENESS
```

The backend controls the counter.

---

# 8. Face Retry Limit

When:

```text
retry_count >= max_retries
```

the backend returns:

```text
RETRY_LIMIT_REACHED
```

The exact terminal behavior must be configured by the application state policy.

The frontend must not invent a new workflow state.

---

# 9. LIVENESS

## Purpose

Determine whether the user appears to be live rather than a spoof.

## Success

```text
LIVENESS PASS
      ↓
GENERAL_QUESTIONS
```

## Failure

```text
LIVENESS FAIL
      ↓
Retry
      ↓
LIVENESS
```

---

# 10. Liveness Retry

Example:

```text
LIVENESS
    ↓
FAIL
    ↓
Retry 1
    ↓
LIVENESS
    ↓
PASS
    ↓
GENERAL_QUESTIONS
```

---

# 11. GENERAL_QUESTIONS

## Purpose

Ask a configured random selection of questions.

The administrator configures:

```text
Question Pool
Question Count = N
Random Selection = true
```

Example:

```text
Pool = 10 questions
N = 3

Selected:
Q4
Q7
Q2
```

The selected sequence must be persisted.

---

# 12. Question Flow

```text
GENERAL_QUESTIONS
       ↓
Select Questions
       ↓
Ask Question
       ↓
User Speaks
       ↓
ASR
       ↓
Transcript
       ↓
LLM Evaluation
       ↓
Next Question
       ↓
...
       ↓
All Questions Complete
       ↓
DOCUMENT_PRESENTATION
```

---

# 13. Question State

The state machine does not create a separate global workflow state for every individual question.

Instead:

```text
current_step = GENERAL_QUESTIONS
```

and the attempt stores:

```text
current question sequence
total questions
completed questions
```

---

# 14. Question Failure

A provider failure is different from an answer failure.

### Provider failure

Example:

```text
Deepgram unavailable
```

The backend should return:

```text
PROVIDER_ERROR
```

The workflow should not silently mark the answer as passed.

### Answer evaluation

An answer may be:

```text
understood = false
relevant = false
```

The exact V1 behavior should be controlled by the conversation service rather than treating every answer-quality issue as a workflow failure.

---

# 15. DOCUMENT_PRESENTATION

## Purpose

Tell the user which uploaded document must be shown.

V1 rule:

```text
Show all uploaded documents
one by one
```

Example:

```text
Document 1 → Aadhaar
Document 2 → PAN
Document 3 → Other
```

---

# 16. Document Presentation Flow

```text
DOCUMENT_PRESENTATION
        ↓
Get current document
        ↓
Display instruction
        ↓
"Please show the same document you uploaded."
        ↓
DOCUMENT_CAPTURE
```

---

# 17. DOCUMENT_CAPTURE

## Purpose

Capture the physical document through the camera.

Frontend displays:

```text
+-------------------------+
|                         |
|   DOCUMENT FRAME        |
|                         |
|  Place document here    |
|                         |
+-------------------------+
```

---

# 18. Document Capture Success

```text
Capture
   ↓
Validation
   ↓
PASS
   ↓
More documents?
   ├── YES → DOCUMENT_PRESENTATION
   └── NO  → RECORDING_COMPLETE
```

---

# 19. Document Capture Failure

```text
Capture
   ↓
Quality validation
   ↓
FAIL
   ↓
Retry
   ↓
DOCUMENT_CAPTURE
```

Example reasons:

```text
DOCUMENT_NOT_VISIBLE
DOCUMENT_TOO_BLURRY
DOCUMENT_TOO_DARK
DOCUMENT_OUT_OF_FRAME
DOCUMENT_TOO_SMALL
```

---

# 20. Recording Completion

After all documents have been captured:

```text
Last Document
     ↓
Stop Recording
     ↓
Upload/Finalize Recording
     ↓
RECORDING_COMPLETE
```

---

# 21. RECORDING_COMPLETE

## Purpose

Confirm that the continuous recording has been finalized.

Required:

```text
Recording exists
Recording upload completed
Required session evidence exists
```

Next:

```text
EVIDENCE_PACKAGE_CREATED
```

---

# 22. EVIDENCE_PACKAGE_CREATED

## Purpose

Assemble evidence for human review.

Evidence contains references to:

```text
Continuous recording
Face result
Liveness result
Questions
Transcripts
Answer evaluations
Reference documents
Captured documents
Audit events
```

After successful creation:

```text
HUMAN_REVIEW
```

---

# 23. HUMAN_REVIEW

## Purpose

A human reviewer makes the final decision.

Possible decisions:

```text
APPROVE
RETRY
```

---

# 24. Human Approval

```text
HUMAN_REVIEW
      ↓
APPROVE
      ↓
VERIFIED
```

The reviewer decision must be persisted.

---

# 25. Human Retry

```text
HUMAN_REVIEW
      ↓
RETRY
      ↓
Create New Attempt
      ↓
attempt_number + 1
      ↓
STARTED
```

Important:

Human-review retry does not reset the existing attempt.

It creates a new attempt.

---

# 26. Attempt Isolation

Example:

```text
Session 001

Attempt 1
 ├── Recording
 ├── Face
 ├── Liveness
 ├── Questions
 ├── Documents
 └── Evidence
       ↓
     RETRY

Attempt 2
 ├── Recording
 ├── Face
 ├── Liveness
 ├── Questions
 ├── Documents
 └── Evidence
```

Attempt 1 remains available for audit.

---

# 27. VERIFIED

`VERIFIED` is the successful terminal workflow state.

```text
HUMAN_REVIEW
      ↓
APPROVE
      ↓
VERIFIED
```

No automatic transition should occur after `VERIFIED`.

---

# 28. Automatic Retry vs Human Retry

These are different mechanisms.

## Automatic retry

```text
Same attempt
Same step
Retry counter increases
```

Example:

```text
LIVENESS
   ↓
FAIL
   ↓
LIVENESS
```

## Human retry

```text
Old attempt
   ↓
Reviewer RETRY
   ↓
New attempt
   ↓
STARTED
```

---

# 29. Retry Counters

Retry counters should be maintained per step.

Example:

```json
{
  "FACE": 1,
  "LIVENESS": 0,
  "DOCUMENT_CAPTURE": 2
}
```

The backend is authoritative.

---

# 30. Retry Configuration

Recommended V1:

```text
FACE = 3
LIVENESS = 3
DOCUMENT_CAPTURE = 3
```

The values should be configurable rather than hard-coded throughout application code.

---

# 31. Invalid State Transition

Example:

Current state:

```text
GENERAL_QUESTIONS
```

User submits:

```text
LIVENESS
```

This is invalid.

Backend returns:

```text
409 Conflict
```

with:

```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Liveness cannot be submitted during the current KYC step.",
    "details": {
      "current_step": "GENERAL_QUESTIONS",
      "requested_step": "LIVENESS"
    }
  }
}
```

---

# 32. Browser Refresh

If the user refreshes:

```text
Browser
   ↓
GET /video-sessions/{session_id}
   ↓
Backend
   ↓
Current authoritative state
```

Example:

```text
current_step = DOCUMENT_CAPTURE
```

Frontend resumes:

```text
DOCUMENT_CAPTURE
```

---

# 33. Network Failure

Network failure must not automatically change workflow state.

Example:

```text
Frontend
   ↓
Submit Liveness
   ↓
Network failure
```

Frontend should retrieve the current state:

```text
GET /video-sessions/{session_id}
```

before making assumptions about whether the operation succeeded.

---

# 34. Duplicate Requests

Example:

```text
POST /recording/start
```

is accidentally sent twice.

Backend should prevent:

```text
Two active recordings
```

Use idempotency where appropriate.

---

# 35. State Transition Table

| Current State | Event | Result |
|---|---|---|
| STARTED | Recording ready | FACE |
| FACE | Face pass | LIVENESS |
| FACE | Face fail + retry available | FACE |
| FACE | Retry limit | Failure policy |
| LIVENESS | Liveness pass | GENERAL_QUESTIONS |
| LIVENESS | Liveness fail + retry | LIVENESS |
| GENERAL_QUESTIONS | Questions complete | DOCUMENT_PRESENTATION |
| DOCUMENT_PRESENTATION | Document ready | DOCUMENT_CAPTURE |
| DOCUMENT_CAPTURE | Capture pass + documents remain | DOCUMENT_PRESENTATION |
| DOCUMENT_CAPTURE | Final capture pass | RECORDING_COMPLETE |
| DOCUMENT_CAPTURE | Capture fail + retry | DOCUMENT_CAPTURE |
| RECORDING_COMPLETE | Recording finalized | EVIDENCE_PACKAGE_CREATED |
| EVIDENCE_PACKAGE_CREATED | Evidence ready | HUMAN_REVIEW |
| HUMAN_REVIEW | APPROVE | VERIFIED |
| HUMAN_REVIEW | RETRY | New Attempt → STARTED |
| VERIFIED | Any workflow action | Invalid |

---

# 36. Backend Responsibilities

The backend must:

- Validate current state
- Validate requested operation
- Apply transition
- Persist transition
- Persist audit event
- Return resulting state
- Enforce retry limits
- Prevent invalid transitions

---

# 37. Frontend Responsibilities

The frontend must:

- Render current state
- Send commands through API
- Display retry information
- Display errors
- Handle loading states
- Handle network failures
- Recover session state
- Never override authoritative backend state

---

# 38. State Machine and API Contract

Every workflow-changing API endpoint must correspond to a state transition.

Example:

```text
POST /face
       ↓
FACE → LIVENESS
```

or:

```text
POST /face
       ↓
FACE → FACE
```

depending on the result.

---

# 39. State Machine and Database

The current workflow state must be persisted in:

```text
attempts.current_step
```

The session may also maintain its current status.

Audit events must record important transitions.

---

# 40. Audit Example

```json
{
  "event_type": "LIVENESS_PASSED",
  "actor_type": "SYSTEM",
  "attempt_id": "attempt_001",
  "metadata": {
    "previous_state": "LIVENESS",
    "new_state": "GENERAL_QUESTIONS"
  }
}
```

---

# 41. Terminal States

V1 terminal state:

```text
VERIFIED
```

An attempt may also reach failure conditions according to retry policy, but human-review retry creates a new attempt rather than mutating the old attempt.

---

# 42. Core State Machine Rule

The most important rule is:

```text
The backend decides where the KYC workflow goes next.
```

The frontend only renders what the backend says.

---

# 43. Final State Machine

```text
                        ┌─────────────┐
                        │   STARTED   │
                        └──────┬──────┘
                               │
                               ▼
                        ┌─────────────┐
                  ┌────►│    FACE     │
                  │     └──────┬──────┘
                  │            │ PASS
                  │            ▼
                  │     ┌─────────────┐
                  │     │  LIVENESS   │
                  │     └──────┬──────┘
                  │            │ PASS
                  │            ▼
                  │     ┌─────────────┐
                  │     │  QUESTIONS  │
                  │     └──────┬──────┘
                  │            │ COMPLETE
                  │            ▼
                  │     ┌─────────────┐
                  │     │  DOCUMENT   │
                  │     │ PRESENTATION│
                  │     └──────┬──────┘
                  │            │
                  │            ▼
                  │     ┌─────────────┐
                  │     │   DOCUMENT  │
                  │     │   CAPTURE   │
                  │     └──────┬──────┘
                  │            │ ALL DONE
                  │            ▼
                  │     ┌─────────────┐
                  │     │  RECORDING  │
                  │     │  COMPLETE   │
                  │     └──────┬──────┘
                  │            │
                  │            ▼
                  │     ┌─────────────┐
                  │     │   EVIDENCE  │
                  │     └──────┬──────┘
                  │            │
                  │            ▼
                  │     ┌─────────────┐
                  │     │    HUMAN    │
                  │     │    REVIEW   │
                  │     └──────┬──────┘
                  │            │
             ┌────┴────┐      │
             │         │      │
          RETRY      APPROVE  │
             │         │      │
             ▼         ▼      │
        NEW ATTEMPT  VERIFIED │
             │                │
             └──► STARTED ◄───┘

Automatic step failures:
FACE ───────────────► FACE
LIVENESS ───────────► LIVENESS
DOCUMENT_CAPTURE ───► DOCUMENT_CAPTURE
```

---

# 44. Final Principle

```text
State is data.
Transition is business logic.
Frontend is presentation.
Backend is authority.
Audit is evidence.
```