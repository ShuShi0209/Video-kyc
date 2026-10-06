# API Contract

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 API Contract  
**Architecture:** `docs/ARCHITECTURE.md`  
**Product Specification:** `docs/PRD.md`  
**Engineering Rules:** `docs/PROJECT_INSTRUCTIONS.md`

---

# 1. Purpose

This document defines the API contract between the Video KYC frontend and backend.

The purpose is to ensure that:

- Frontend and backend use the same request formats.
- Frontend and backend use the same response formats.
- Workflow state is controlled by the backend.
- API errors have predictable structures.
- Retry behavior is explicit.
- AI provider details are hidden from the frontend.
- Media upload behavior is defined before frontend implementation.

This document is the contract that frontend and backend developers must follow.

---

# 2. API Base URL

Local development:

```text
http://localhost:8000
```

API prefix:

```text
/api/v1
```

Therefore:

```text
http://localhost:8000/api/v1
```

Frontend should not hard-code individual endpoint URLs throughout the application.

Use a centralized API client.

---

# 3. Communication Protocol

Primary protocol:

```text
HTTP/HTTPS
```

Data format:

```text
JSON
```

Media upload:

```text
multipart/form-data
```

Authentication:

```text
Bearer Token
```

V1 may initially use a simplified local authentication implementation, but API contracts should keep authentication boundaries explicit.

---

# 4. Common Headers

JSON requests:

```http
Content-Type: application/json
Authorization: Bearer <access_token>
```

Media requests:

```http
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

---

# 5. Common Response Rules

Successful response:

```text
2xx
```

Client error:

```text
4xx
```

Server error:

```text
5xx
```

The backend must return structured JSON errors.

Example:

```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "The requested operation is not valid for the current KYC step.",
    "details": {}
  }
}
```

---

# 6. Error Contract

All API errors should follow:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

Fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `error` | object | Yes | Error container |
| `error.code` | string | Yes | Machine-readable error code |
| `error.message` | string | Yes | Safe human-readable message |
| `error.details` | object | No | Additional structured information |

---

# 7. Standard Error Codes

V1 should support at least:

```text
UNAUTHORIZED
FORBIDDEN
NOT_FOUND
VALIDATION_ERROR
INVALID_STATE
INVALID_REQUEST
SESSION_NOT_FOUND
ATTEMPT_NOT_FOUND
DOCUMENT_NOT_FOUND
QUESTION_NOT_FOUND
RETRY_LIMIT_REACHED
MEDIA_UPLOAD_FAILED
MEDIA_PROCESSING_FAILED
PROVIDER_ERROR
LIVENESS_FAILED
FACE_DETECTION_FAILED
CONVERSATION_ERROR
EVIDENCE_CREATION_FAILED
REVIEW_NOT_ALLOWED
INTERNAL_ERROR
```

The backend may add additional codes when required.

---

# 8. HTTP Status Mapping

Recommended mapping:

| HTTP Status | Meaning |
|---|---|
| `200` | Successful request |
| `201` | Resource created |
| `204` | Successful request with no response body |
| `400` | Invalid request |
| `401` | Authentication required/invalid |
| `403` | Permission denied |
| `404` | Resource not found |
| `409` | State/conflict error |
| `422` | Validation error |
| `429` | Rate limit |
| `500` | Internal server error |
| `502` | External provider failure |
| `503` | Service temporarily unavailable |

---

# 9. Backend-Owned State

The backend is the source of truth for KYC workflow state.

Frontend must not independently decide:

```text
next_step
attempt_status
verification_status
review_status
```

The backend returns:

```json
{
  "status": "IN_PROGRESS",
  "current_step": "LIVENESS"
}
```

The frontend renders the appropriate UI.

---

# 10. KYC Workflow States

V1 workflow states:

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

# 11. Attempt Status

Recommended values:

```text
CREATED
IN_PROGRESS
COMPLETED
FAILED
RETRYING
```

The exact transition is controlled by the backend state machine.

---

# 12. Start Video KYC

## Endpoint

```http
POST /api/v1/kyc-cases/{case_id}/video-sessions
```

Purpose:

Start a Video KYC session for an existing KYC case.

---

## Request

No request body required for V1.

```http
POST /api/v1/kyc-cases/case_001/video-sessions
Authorization: Bearer <token>
```

---

## Response

Status:

```text
201 Created
```

Example:

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "status": "IN_PROGRESS",
  "current_step": "STARTED",
  "attempt_number": 1,
  "recording": {
    "status": "NOT_STARTED"
  },
  "documents": [
    {
      "id": "doc_001",
      "document_type": "AADHAAR",
      "filename": "aadhaar.jpg"
    },
    {
      "id": "doc_002",
      "document_type": "PAN",
      "filename": "pan.jpg"
    }
  ]
}
```

---

# 13. Start Recording

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/recording/start
```

Purpose:

Register the start of continuous browser recording.

---

## Request

```json
{
  "started_at": "2026-10-01T12:00:00Z"
}
```

---

## Response

```json
{
  "attempt_id": "attempt_001",
  "recording_id": "recording_001",
  "status": "RECORDING",
  "started_at": "2026-10-01T12:00:00Z"
}
```

---

# 14. Recording Status

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/recording
```

---

## Response

```json
{
  "recording_id": "recording_001",
  "status": "RECORDING",
  "started_at": "2026-10-01T12:00:00Z",
  "ended_at": null
}
```

Possible statuses:

```text
NOT_STARTED
RECORDING
STOPPING
COMPLETED
FAILED
```

---

# 15. Upload Recording

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/recording
```

Content type:

```text
multipart/form-data
```

Form field:

```text
file
```

Example concept:

```text
file=<recorded_video.webm>
```

---

## Response

```json
{
  "recording_id": "recording_001",
  "status": "COMPLETED",
  "mime_type": "video/webm",
  "size": 10485760
}
```

The API must not expose internal filesystem paths.

---

# 16. Face Detection

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/face
```

Purpose:

Submit face verification step result.

V1 performs:

```text
Face Detection
```

and does not perform identity matching.

---

## Request

```json
{
  "detected": true,
  "face_count": 1,
  "quality": 0.94,
  "timestamp": "2026-10-01T12:01:00Z"
}
```

---

## Response — Success

```json
{
  "attempt_id": "attempt_001",
  "step": "FACE",
  "result": "PASS",
  "next_step": "LIVENESS",
  "retry": {
    "allowed": false,
    "retry_count": 0,
    "max_retries": 3
  }
}
```

---

# 17. Face Failure

Example response:

```json
{
  "attempt_id": "attempt_001",
  "step": "FACE",
  "result": "FAIL",
  "next_step": "FACE",
  "retry": {
    "allowed": true,
    "retry_count": 1,
    "max_retries": 3
  },
  "message": "Please position your face clearly in the camera."
}
```

The frontend should keep the user within the Face step.

---

# 18. Liveness

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/liveness
```

Purpose:

Submit liveness verification result.

---

## Request

The exact provider response must not be sent directly to the frontend contract.

Use an internal application-level result:

```json
{
  "status": "PASS",
  "score": 0.96,
  "timestamp": "2026-10-01T12:02:00Z"
}
```

---

## Response — Pass

```json
{
  "attempt_id": "attempt_001",
  "step": "LIVENESS",
  "result": "PASS",
  "next_step": "GENERAL_QUESTIONS",
  "retry": {
    "allowed": false,
    "retry_count": 0,
    "max_retries": 3
  }
}
```

---

# 19. Liveness Failure

```json
{
  "attempt_id": "attempt_001",
  "step": "LIVENESS",
  "result": "FAIL",
  "next_step": "LIVENESS",
  "retry": {
    "allowed": true,
    "retry_count": 1,
    "max_retries": 3
  },
  "message": "Liveness verification failed. Please try again."
}
```

---

# 20. Retry Contract

V1 supports automatic retries within the same attempt.

Example:

```text
Step
 |
 +── Attempt 1 → FAIL
 |
 +── Attempt 2 → FAIL
 |
 +── Attempt 3 → PASS
```

The retry count is maintained by the backend.

Frontend must not maintain the authoritative retry counter.

---

# 21. Retry Limit

Example:

```json
{
  "retry": {
    "allowed": false,
    "retry_count": 3,
    "max_retries": 3
  }
}
```

If the maximum retry limit is reached, the backend returns:

```text
RETRY_LIMIT_REACHED
```

The exact resulting attempt behavior must be controlled by the state machine.

---

# 22. Get Current Session State

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}
```

Purpose:

Allow frontend to restore the current session state.

---

## Response

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "status": "IN_PROGRESS",
  "current_step": "GENERAL_QUESTIONS",
  "attempt_number": 1,
  "recording": {
    "status": "RECORDING"
  }
}
```

This endpoint is important for browser refresh/reconnect behavior.

---

# 23. Get Current Attempt

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}
```

---

## Response

```json
{
  "attempt_id": "attempt_001",
  "attempt_number": 1,
  "status": "IN_PROGRESS",
  "current_step": "GENERAL_QUESTIONS",
  "retry_counts": {
    "FACE": 0,
    "LIVENESS": 0
  }
}
```

---

# 24. Question Configuration

Administrators configure a question pool.

## Endpoint

```http
POST /api/v1/questions
```

---

## Request

```json
{
  "text": "What is your full name?",
  "category": "GENERAL",
  "active": true
}
```

---

## Response

```json
{
  "id": "question_001",
  "text": "What is your full name?",
  "category": "GENERAL",
  "active": true
}
```

---

# 25. List Questions

## Endpoint

```http
GET /api/v1/questions
```

Optional filters:

```text
?active=true
?category=GENERAL
```

---

## Response

```json
{
  "questions": [
    {
      "id": "question_001",
      "text": "What is your full name?",
      "category": "GENERAL",
      "active": true
    },
    {
      "id": "question_002",
      "text": "What is your date of birth?",
      "category": "GENERAL",
      "active": true
    }
  ]
}
```

---

# 26. Configure Question Count

## Endpoint

```http
PUT /api/v1/question-config
```

---

## Request

```json
{
  "question_count": 3,
  "random_selection": true
}
```

---

## Response

```json
{
  "question_count": 3,
  "random_selection": true
}
```

The administrator controls how many questions are selected.

---

# 27. Select Questions for Attempt

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/questions/start
```

Purpose:

Select N random questions from the configured active question pool.

---

## Response

```json
{
  "attempt_id": "attempt_001",
  "current_step": "GENERAL_QUESTIONS",
  "total_questions": 3,
  "current_question": {
    "id": "question_014",
    "sequence_number": 1,
    "text": "What is your full name?"
  }
}
```

The selected sequence must be persisted for audit/review.

---

# 28. Get Current Question

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/questions/current
```

---

## Response

```json
{
  "question": {
    "id": "question_014",
    "sequence_number": 1,
    "total_questions": 3,
    "text": "What is your full name?"
  }
}
```

---

# 29. Submit Answer

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/questions/{question_id}/answer
```

---

## Request

```json
{
  "transcript": "My name is Rahul Sharma",
  "audio_duration_ms": 3200
}
```

The frontend does not directly provide an LLM evaluation.

The backend handles:

```text
Transcript
   ↓
LLM
   ↓
Answer Understanding
```

---

# 30. Answer Response

Example:

```json
{
  "question_id": "question_014",
  "answer_id": "answer_001",
  "transcript": "My name is Rahul Sharma",
  "evaluation": {
    "understood": true,
    "relevant": true
  },
  "next_question": {
    "id": "question_021",
    "sequence_number": 2,
    "text": "What is your date of birth?"
  }
}
```

---

# 31. Final Question Response

When there are no more questions:

```json
{
  "question_id": "question_021",
  "answer_id": "answer_003",
  "completed": true,
  "next_step": "DOCUMENT_PRESENTATION"
}
```

---

# 32. Conversation Audio / ASR

The architecture separates:

```text
ASR
LLM
TTS
```

The frontend may capture audio and submit it to the backend.

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/conversation/audio
```

Content type:

```text
multipart/form-data
```

---

## Request

```text
file=<audio.webm>
```

---

## Response

```json
{
  "transcript": "My name is Rahul Sharma",
  "duration_ms": 3200
}
```

The backend may internally send the audio to the configured ASR provider.

---

# 33. TTS

## Endpoint

```http
POST /api/v1/conversation/tts
```

---

## Request

```json
{
  "text": "What is your full name?"
}
```

---

## Response

The response may be an audio stream or a temporary media reference.

Recommended V1 contract:

```json
{
  "audio_url": "/api/v1/conversation/audio/tts_001",
  "content_type": "audio/mpeg"
}
```

The frontend plays the returned audio.

The exact provider is hidden from the frontend.

---

# 34. Document Presentation

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/documents/current
```

---

## Response

```json
{
  "document": {
    "id": "doc_001",
    "document_type": "AADHAAR",
    "display_name": "Aadhaar Card",
    "sequence_number": 1,
    "total_documents": 2
  },
  "instruction": "Please show the same document you uploaded."
}
```

The frontend uses this information to display the correct instruction.

---

# 35. Document Frame

The document frame is a frontend UI component.

The backend does not need to control its visual dimensions in V1.

Frontend displays:

```text
+-----------------------------+
|                             |
|       DOCUMENT FRAME        |
|                             |
|    Place document here      |
|                             |
+-----------------------------+
```

The frontend captures the document image when ready.

---

# 36. Document Capture

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/documents/{document_id}/capture
```

Content type:

```text
multipart/form-data
```

Form field:

```text
file
```

---

## Response

```json
{
  "capture_id": "capture_001",
  "document_id": "doc_001",
  "status": "CAPTURED",
  "next_document": {
    "id": "doc_002",
    "document_type": "PAN",
    "sequence_number": 2
  }
}
```

---

# 37. Final Document Capture

When all documents are captured:

```json
{
  "capture_id": "capture_002",
  "document_id": "doc_002",
  "status": "CAPTURED",
  "completed": true,
  "next_step": "RECORDING_COMPLETE"
}
```

---

# 38. Document Capture Validation Failure

Example:

```json
{
  "capture_id": null,
  "status": "REJECTED",
  "reason": {
    "code": "DOCUMENT_QUALITY_LOW",
    "message": "Please position the document clearly inside the frame."
  },
  "retry": {
    "allowed": true,
    "retry_count": 1,
    "max_retries": 3
  }
}
```

---

# 39. Stop Recording

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/recording/stop
```

---

## Request

```json
{
  "ended_at": "2026-10-01T12:10:00Z"
}
```

---

## Response

```json
{
  "recording_id": "recording_001",
  "status": "COMPLETED",
  "ended_at": "2026-10-01T12:10:00Z",
  "next_step": "EVIDENCE_PACKAGE_CREATED"
}
```

---

# 40. Evidence Package

## Endpoint

```http
POST /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/evidence
```

Purpose:

Create the evidence package after recording and verification steps are complete.

---

## Response

```json
{
  "evidence_id": "evidence_001",
  "attempt_id": "attempt_001",
  "status": "CREATED",
  "created_at": "2026-10-01T12:11:00Z",
  "next_step": "HUMAN_REVIEW"
}
```

---

# 41. Get Evidence

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/evidence
```

---

## Response

```json
{
  "evidence_id": "evidence_001",
  "attempt_id": "attempt_001",
  "status": "CREATED",
  "recording": {
    "available": true
  },
  "face": {
    "available": true
  },
  "liveness": {
    "available": true
  },
  "questions": {
    "count": 3
  },
  "documents": {
    "count": 2
  }
}
```

---

# 42. Human Review Queue

## Endpoint

```http
GET /api/v1/reviews
```

Purpose:

Allow authorized reviewers/admins to retrieve cases requiring review.

---

## Response

```json
{
  "reviews": [
    {
      "review_id": "review_001",
      "case_id": "case_001",
      "session_id": "session_001",
      "attempt_id": "attempt_001",
      "status": "PENDING",
      "created_at": "2026-10-01T12:12:00Z"
    }
  ]
}
```

---

# 43. Get Review

## Endpoint

```http
GET /api/v1/reviews/{review_id}
```

---

## Response

```json
{
  "review_id": "review_001",
  "case_id": "case_001",
  "attempt_id": "attempt_001",
  "status": "PENDING",
  "evidence_id": "evidence_001"
}
```

---

# 44. Approve Review

## Endpoint

```http
POST /api/v1/reviews/{review_id}/approve
```

---

## Request

```json
{
  "notes": "All required verification evidence reviewed."
}
```

---

## Response

```json
{
  "review_id": "review_001",
  "decision": "APPROVED",
  "attempt_id": "attempt_001",
  "case_status": "VERIFIED"
}
```

---

# 45. Retry Review

## Endpoint

```http
POST /api/v1/reviews/{review_id}/retry
```

---

## Request

```json
{
  "reason": "Document capture is unclear."
}
```

---

## Response

```json
{
  "review_id": "review_001",
  "decision": "RETRY",
  "previous_attempt_id": "attempt_001",
  "new_attempt_id": "attempt_002",
  "new_attempt_number": 2,
  "status": "IN_PROGRESS",
  "current_step": "STARTED"
}
```

A human-review retry always creates a new attempt.

---

# 46. Retry Attempt Rules

The frontend must understand the following distinction:

### Automatic step retry

```text
Same attempt
   ↓
Same step
   ↓
Retry counter increases
```

### Human-review retry

```text
Previous attempt
   ↓
Reviewer selects RETRY
   ↓
New attempt
   ↓
STARTED
```

---

# 47. Attempt History

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts
```

---

## Response

```json
{
  "attempts": [
    {
      "attempt_id": "attempt_001",
      "attempt_number": 1,
      "status": "REVIEWED",
      "review_decision": "RETRY"
    },
    {
      "attempt_id": "attempt_002",
      "attempt_number": 2,
      "status": "IN_PROGRESS",
      "review_decision": null
    }
  ]
}
```

---

# 48. Audit Events

## Endpoint

```http
GET /api/v1/video-sessions/{session_id}/attempts/{attempt_id}/audit
```

Purpose:

Retrieve audit events for authorized users/reviewers.

---

## Response

```json
{
  "events": [
    {
      "event_type": "ATTEMPT_CREATED",
      "timestamp": "2026-10-01T12:00:00Z",
      "actor_type": "USER"
    },
    {
      "event_type": "FACE_PASSED",
      "timestamp": "2026-10-01T12:01:00Z",
      "actor_type": "SYSTEM"
    },
    {
      "event_type": "LIVENESS_PASSED",
      "timestamp": "2026-10-01T12:02:00Z",
      "actor_type": "SYSTEM"
    }
  ]
}
```

---

# 49. State Synchronization

The frontend should use the backend response after every workflow-changing API call.

Example:

```text
Frontend
   |
   | Submit liveness
   v
Backend
   |
   | Update state
   v
Response
   |
   | current_step = GENERAL_QUESTIONS
   v
Frontend
   |
   v
Render Questions UI
```

Do not assume the next state locally.

---

# 50. Browser Refresh

If the browser refreshes during an active session:

```text
Frontend
   |
   v
GET /video-sessions/{session_id}
   |
   v
Backend
   |
   v
Current authoritative state
```

Example:

```json
{
  "session_id": "session_001",
  "attempt_id": "attempt_001",
  "current_step": "DOCUMENT_CAPTURE",
  "status": "IN_PROGRESS"
}
```

Frontend resumes the correct screen.

---

# 51. Duplicate Requests

The frontend may retry requests because of network failures.

Backend commands that create resources or advance workflow should be designed for idempotency where appropriate.

For example:

```http
POST /recording/start
```

should not create multiple active recordings for the same attempt.

---

# 52. Idempotency Key

For important mutation requests, the frontend may send:

```http
Idempotency-Key: <unique-request-id>
```

Example:

```http
Idempotency-Key: 7d6a1b2c-...
```

The backend may use this to prevent duplicate processing.

---

# 53. Media Upload Rules

V1 media upload validation should include:

```text
File exists
File size limit
Allowed MIME type
Allowed extension
Readable media
Associated session
Associated attempt
Authorized user
```

The backend must not trust the filename or MIME type supplied by the browser.

---

# 54. File Storage Contract

Frontend receives references, not physical storage paths.

Bad:

```json
{
  "path": "D:\\project\\storage\\attempt_001\\video.webm"
}
```

Correct:

```json
{
  "recording_id": "recording_001"
}
```

Internal storage paths remain backend-only.

---

# 55. Provider Abstraction

The frontend must never know:

```text
Groq API key
Deepgram API key
Provider model names
Provider-specific response formats
Provider-specific error structures
```

Frontend communicates only with the application API.

---

# 56. AI Conversation Contract

The frontend sees:

```text
Question
Audio
Transcript
Answer status
Next question
```

The frontend does not see the internal pipeline:

```text
ASR Provider
      ↓
LLM Provider
      ↓
Evaluation
```

Example frontend response:

```json
{
  "answer_id": "answer_001",
  "understood": true,
  "next_question": {
    "id": "question_002",
    "text": "What is your date of birth?"
  }
}
```

---

# 57. API Contract for Provider Failures

If Groq or Deepgram fails, do not expose raw provider errors.

Bad:

```json
{
  "error": "Groq APIError: ..."
}
```

Correct:

```json
{
  "error": {
    "code": "PROVIDER_ERROR",
    "message": "The conversation service is temporarily unavailable.",
    "details": {
      "service": "conversation"
    }
  }
}
```

---

# 58. API Contract for Invalid State

Example:

User submits liveness while current state is:

```text
GENERAL_QUESTIONS
```

Backend returns:

```http
409 Conflict
```

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

# 59. API Contract for Unauthorized Access

```http
401 Unauthorized
```

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication is required.",
    "details": {}
  }
}
```

---

# 60. API Contract for Forbidden Access

```http
403 Forbidden
```

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to access this resource.",
    "details": {}
  }
}
```

---

# 61. API Contract for Missing Resource

```http
404 Not Found
```

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested resource was not found.",
    "details": {}
  }
}
```

---

# 62. API Contract for Validation

```http
422 Unprocessable Entity
```

Example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": {
      "fields": {
        "question_count": "Must be greater than zero."
      }
    }
  }
}
```

---

# 63. Frontend API Client

Frontend should use one centralized API client.

Conceptually:

```text
frontend/src/services/api/
│
├── client.ts
├── sessions.ts
├── attempts.ts
├── questions.ts
├── documents.ts
├── recordings.ts
├── evidence.ts
└── reviews.ts
```

Components should not directly call `fetch()` throughout the application.

---

# 64. Example Frontend API Usage

Conceptually:

```typescript
const session = await videoKycApi.startSession(caseId);
```

Instead of:

```typescript
fetch("http://localhost:8000/api/v1/...");
```

inside UI components.

---

# 65. API Type Definitions

Frontend types should mirror API contracts.

Example:

```typescript
type KycStep =
  | "STARTED"
  | "FACE"
  | "LIVENESS"
  | "GENERAL_QUESTIONS"
  | "DOCUMENT_PRESENTATION"
  | "DOCUMENT_CAPTURE"
  | "RECORDING_COMPLETE"
  | "EVIDENCE_PACKAGE_CREATED"
  | "HUMAN_REVIEW"
  | "VERIFIED";
```

---

# 66. API Contract Ownership

The API contract is jointly relevant to:

```text
Backend
Frontend
QA
```

Any breaking change must update:

```text
API_CONTRACT.md
Frontend types
Backend schemas
Tests
```

---

# 67. Breaking Changes

Examples of breaking changes:

```text
Renaming response fields
Changing enum values
Removing fields
Changing required fields
Changing endpoint paths
Changing authentication behavior
Changing state names
Changing media upload requirements
```

These require an API contract update.

---

# 68. Non-Breaking Changes

Examples:

```text
Adding optional response fields
Adding optional request fields
Adding new non-conflicting metadata
```

These should still be documented.

---

# 69. V1 API Flow

Complete frontend interaction:

```text
START
  |
  v
POST /kyc-cases/{case_id}/video-sessions
  |
  v
POST /recording/start
  |
  v
POST /face
  |
  v
POST /liveness
  |
  v
POST /questions/start
  |
  v
GET /questions/current
  |
  v
POST /questions/{id}/answer
  |
  v
GET /documents/current
  |
  v
POST /documents/{id}/capture
  |
  v
POST /recording/stop
  |
  v
POST /evidence
  |
  v
HUMAN REVIEW
```

---

# 70. V1 Human Review Flow

```text
GET /reviews
      |
      v
GET /reviews/{review_id}
      |
      +----------------+
      |                |
      v                v
POST /approve       POST /retry
      |                |
      v                v
 VERIFIED          NEW ATTEMPT
                       |
                       v
                    STARTED
```

---

# 71. Contract Rules for Frontend Development

Before implementing frontend integration:

1. Do not invent API response fields.
2. Do not assume state transitions.
3. Do not store authoritative KYC state only in frontend state.
4. Do not expose provider APIs to the browser.
5. Do not expose storage paths.
6. Use centralized API client functions.
7. Handle structured API errors.
8. Handle session recovery.
9. Handle retry states.
10. Handle network failures.
11. Use backend response as the source of truth.
12. Keep frontend types synchronized with this document.

---

# 72. Contract Rules for Backend Development

Backend must:

1. Validate every request.
2. Validate current workflow state.
3. Validate resource ownership/authorization.
4. Return stable response schemas.
5. Return structured errors.
6. Never expose internal provider errors.
7. Never expose filesystem paths.
8. Persist important workflow transitions.
9. Persist audit events.
10. Enforce retry limits.
11. Maintain attempt isolation.
12. Prevent invalid state transitions.

---

# 73. V1 Contract Boundary

The following are explicitly outside the frontend contract:

```text
Groq SDK
Deepgram SDK
Database implementation
Filesystem implementation
Internal state-machine implementation
Provider-specific response formats
Provider API keys
Internal service classes
Repository implementation
```

The frontend communicates only with the application API.

---

# 74. Future API Extensions

The API can later support:

```text
Face Matching
Document OCR
Document Authenticity
Advanced Liveness
Fraud Detection
Risk Score
Cloud Storage
Webhook Notifications
Background Processing
Reviewer Comments
Analytics
```

These should be introduced through versioned or backward-compatible API changes.

---

# 75. API Versioning

Current:

```text
/api/v1
```

Future breaking API changes:

```text
/api/v2
```

Do not silently introduce breaking V1 behavior.

---

# 76. Final API Contract Principle

The frontend should think in terms of:

```text
Command
   ↓
Backend
   ↓
Authoritative Result
   ↓
Render Next State
```

Not:

```text
Frontend
   ↓
Guess what happens next
```

The backend owns the workflow.

The frontend owns the user experience.

AI providers remain behind the backend.

The human reviewer remains the final decision-maker.

This contract must be finalized and reviewed before implementing the frontend-backend integration.