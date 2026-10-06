# Database Schema

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 Database Design  
**Database:** PostgreSQL

---

# 1. Purpose

This document defines the V1 PostgreSQL database structure for the Video KYC system.

The database must persist:

- Existing KYC cases
- Uploaded reference documents
- Video KYC sessions
- Attempts
- Recording metadata
- Face verification results
- Liveness results
- Questions
- Question configuration
- Selected questions
- User answers
- Document captures
- Evidence packages
- Human reviews
- Audit events

The database is the persistent source of truth for KYC workflow state.

---

# 2. Entity Relationship Overview

```text
KYC_CASE
   │
   ├────────────── DOCUMENT
   │
   └────────────── VIDEO_SESSION
                       │
                       └──────────── ATTEMPT
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
           RECORDING             FACE_RESULT         LIVENESS_RESULT
                │
                │
                ├──────────── SELECTED_QUESTION
                │                       │
                │                       ▼
                │                    ANSWER
                │
                ├──────────── DOCUMENT_CAPTURE
                │
                ├──────────── EVIDENCE_PACKAGE
                │                       │
                │                       ▼
                │                    REVIEW
                │
                └──────────── AUDIT_EVENT
```

---

# 3. Database Naming Convention

Use:

```text
snake_case
```

Examples:

```text
kyc_cases
video_sessions
attempts
document_captures
audit_events
```

Primary key:

```text
id
```

Recommended ID format:

```text
UUID
```

All major entities should use UUID identifiers.

---

# 4. Common Timestamp Fields

Major entities should contain:

```text
created_at
updated_at
```

Timestamp type:

```text
TIMESTAMPTZ
```

Timestamps should be stored in UTC.

---

# 5. KYC Cases

## Table

```text
kyc_cases
```

Purpose:

Represents an existing KYC case.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | UUID | Yes | Primary key |
| `status` | VARCHAR | Yes | Current KYC case status |
| `created_at` | TIMESTAMPTZ | Yes | Creation time |
| `updated_at` | TIMESTAMPTZ | Yes | Last update |
| `completed_at` | TIMESTAMPTZ | No | Completion time |

Example:

```text
id: case_uuid
status: IN_PROGRESS
```

---

# 6. KYC Case Status

Recommended values:

```text
CREATED
IN_PROGRESS
VERIFIED
RETRY_REQUIRED
CLOSED
```

The application may extend this list as requirements evolve.

---

# 7. Documents

## Table

```text
documents
```

Purpose:

Stores metadata for documents uploaded to an existing KYC case.

### Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `id` | UUID | Yes | Primary key |
| `case_id` | UUID | Yes | Related KYC case |
| `document_type` | VARCHAR | Yes | Document type |
| `filename` | VARCHAR | Yes | Original filename |
| `mime_type` | VARCHAR | Yes | MIME type |
| `storage_key` | VARCHAR | Yes | Internal storage reference |
| `sequence_number` | INTEGER | Yes | Presentation order |
| `created_at` | TIMESTAMPTZ | Yes | Creation time |

Foreign key:

```text
documents.case_id
    →
kyc_cases.id
```

---

# 8. Document Storage

The database must not store the physical file contents for V1.

Instead:

```text
documents.storage_key
```

references the local filesystem object.

Example:

```text
storage_key:
documents/case_001/aadhaar_001.jpg
```

The physical path must remain an internal backend concern.

The API must never expose absolute filesystem paths.

---

# 9. Video Sessions

## Table

```text
video_sessions
```

Purpose:

Represents a Video KYC session associated with an existing KYC case.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `case_id` | UUID | Yes |
| `status` | VARCHAR | Yes |
| `current_step` | VARCHAR | Yes |
| `created_at` | TIMESTAMPTZ | Yes |
| `updated_at` | TIMESTAMPTZ | Yes |
| `completed_at` | TIMESTAMPTZ | No |

Foreign key:

```text
video_sessions.case_id
    →
kyc_cases.id
```

---

# 10. Video Session Status

Recommended:

```text
STARTED
IN_PROGRESS
COMPLETED
CANCELLED
```

---

# 11. Attempts

## Table

```text
attempts
```

Purpose:

Represents an individual execution of the Video KYC flow.

A human-review retry creates a new attempt.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `session_id` | UUID | Yes |
| `attempt_number` | INTEGER | Yes |
| `status` | VARCHAR | Yes |
| `current_step` | VARCHAR | Yes |
| `started_at` | TIMESTAMPTZ | Yes |
| `completed_at` | TIMESTAMPTZ | No |
| `created_at` | TIMESTAMPTZ | Yes |
| `updated_at` | TIMESTAMPTZ | Yes |

Foreign key:

```text
attempts.session_id
    →
video_sessions.id
```

Constraint:

```text
(session_id, attempt_number)
```

must be unique.

---

# 12. Attempt Status

Recommended:

```text
CREATED
IN_PROGRESS
COMPLETED
FAILED
REVIEW
RETRYING
```

---

# 13. KYC Workflow Step

The `current_step` field should use controlled values:

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

These values must remain consistent with:

```text
STATE_MACHINE.md
API_CONTRACT.md
```

---

# 14. Recordings

## Table

```text
recordings
```

Purpose:

Stores metadata for the continuous Video KYC recording.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `storage_key` | VARCHAR | Yes |
| `mime_type` | VARCHAR | Yes |
| `file_size` | BIGINT | Yes |
| `status` | VARCHAR | Yes |
| `started_at` | TIMESTAMPTZ | No |
| `ended_at` | TIMESTAMPTZ | No |
| `created_at` | TIMESTAMPTZ | Yes |

Foreign key:

```text
recordings.attempt_id
    →
attempts.id
```

V1 expects one continuous recording per attempt.

---

# 15. Recording Status

```text
NOT_STARTED
RECORDING
STOPPING
COMPLETED
FAILED
```

---

# 16. Face Results

## Table

```text
face_results
```

Purpose:

Stores the V1 face detection result.

V1 does not perform identity matching.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `detected` | BOOLEAN | Yes |
| `face_count` | INTEGER | Yes |
| `quality_score` | NUMERIC | No |
| `result` | VARCHAR | Yes |
| `retry_count` | INTEGER | Yes |
| `created_at` | TIMESTAMPTZ | Yes |

---

# 17. Liveness Results

## Table

```text
liveness_results
```

Purpose:

Stores liveness / anti-spoof results.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `result` | VARCHAR | Yes |
| `score` | NUMERIC | No |
| `retry_count` | INTEGER | Yes |
| `provider` | VARCHAR | No |
| `created_at` | TIMESTAMPTZ | Yes |

Provider-specific response data should not be exposed directly through the frontend API.

---

# 18. Questions

## Table

```text
questions
```

Purpose:

Stores the administrator-configured question pool.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `text` | TEXT | Yes |
| `category` | VARCHAR | Yes |
| `active` | BOOLEAN | Yes |
| `created_at` | TIMESTAMPTZ | Yes |
| `updated_at` | TIMESTAMPTZ | Yes |

---

# 19. Question Configuration

## Table

```text
question_config
```

V1 may maintain one active global configuration.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `question_count` | INTEGER | Yes |
| `random_selection` | BOOLEAN | Yes |
| `updated_at` | TIMESTAMPTZ | Yes |

Example:

```text
question_count = 3
random_selection = true
```

---

# 20. Selected Questions

## Table

```text
attempt_questions
```

Purpose:

Stores the questions selected for a specific attempt.

This is important because the question sequence must remain auditable.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `question_id` | UUID | Yes |
| `sequence_number` | INTEGER | Yes |
| `created_at` | TIMESTAMPTZ | Yes |

Constraints:

```text
(attempt_id, sequence_number)
```

must be unique.

---

# 21. Answers

## Table

```text
answers
```

Purpose:

Stores the user's answer and AI evaluation.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_question_id` | UUID | Yes |
| `transcript` | TEXT | Yes |
| `audio_storage_key` | VARCHAR | No |
| `audio_duration_ms` | INTEGER | No |
| `understood` | BOOLEAN | No |
| `relevant` | BOOLEAN | No |
| `evaluation_metadata` | JSONB | No |
| `created_at` | TIMESTAMPTZ | Yes |

---

# 22. AI Evaluation Metadata

The normalized evaluation should be stored.

Example:

```json
{
  "understood": true,
  "relevant": true
}
```

Provider-specific raw responses should be handled carefully and should not be required by the frontend.

---

# 23. Document Captures

## Table

```text
document_captures
```

Purpose:

Stores documents captured during the live Video KYC session.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `document_id` | UUID | Yes |
| `storage_key` | VARCHAR | Yes |
| `mime_type` | VARCHAR | Yes |
| `file_size` | BIGINT | Yes |
| `status` | VARCHAR | Yes |
| `quality_score` | NUMERIC | No |
| `retry_count` | INTEGER | Yes |
| `created_at` | TIMESTAMPTZ | Yes |

Relationships:

```text
document_captures.document_id
        ↓
documents.id
```

---

# 24. Evidence Packages

## Table

```text
evidence_packages
```

Purpose:

Represents the complete evidence package submitted for human review.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `status` | VARCHAR | Yes |
| `created_at` | TIMESTAMPTZ | Yes |
| `completed_at` | TIMESTAMPTZ | No |

One attempt should have at most one finalized evidence package.

---

# 25. Evidence Status

```text
CREATING
CREATED
FAILED
```

---

# 26. Reviews

## Table

```text
reviews
```

Purpose:

Stores human reviewer decisions.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `attempt_id` | UUID | Yes |
| `evidence_id` | UUID | Yes |
| `status` | VARCHAR | Yes |
| `decision` | VARCHAR | No |
| `notes` | TEXT | No |
| `reviewer_id` | UUID | No |
| `created_at` | TIMESTAMPTZ | Yes |
| `completed_at` | TIMESTAMPTZ | No |

---

# 27. Review Status

```text
PENDING
IN_REVIEW
COMPLETED
```

---

# 28. Review Decision

```text
APPROVED
RETRY
```

---

# 29. Audit Events

## Table

```text
audit_events
```

Purpose:

Provides an immutable audit trail for important workflow events.

### Fields

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | Yes |
| `case_id` | UUID | Yes |
| `session_id` | UUID | No |
| `attempt_id` | UUID | No |
| `event_type` | VARCHAR | Yes |
| `actor_type` | VARCHAR | Yes |
| `actor_id` | UUID | No |
| `metadata` | JSONB | No |
| `created_at` | TIMESTAMPTZ | Yes |

---

# 30. Actor Types

```text
USER
SYSTEM
ADMIN
REVIEWER
```

---

# 31. Important Audit Events

Examples:

```text
CASE_CREATED
SESSION_CREATED
ATTEMPT_CREATED

RECORDING_STARTED
RECORDING_STOPPED

FACE_PASSED
FACE_FAILED

LIVENESS_PASSED
LIVENESS_FAILED

QUESTION_STARTED
ANSWER_SUBMITTED
QUESTION_COMPLETED

DOCUMENT_PRESENTED
DOCUMENT_CAPTURED
DOCUMENT_CAPTURE_FAILED

EVIDENCE_CREATED

REVIEW_STARTED
REVIEW_APPROVED
REVIEW_RETRY

ATTEMPT_RESTARTED
```

---

# 32. Relationships

Core relationships:

```text
KYC Case
  1 ─── N Documents

KYC Case
  1 ─── N Video Sessions

Video Session
  1 ─── N Attempts

Attempt
  1 ─── N Recordings

Attempt
  1 ─── N Face Results

Attempt
  1 ─── N Liveness Results

Attempt
  1 ─── N Attempt Questions

Attempt Question
  1 ─── N Answers

Attempt
  1 ─── N Document Captures

Attempt
  1 ─── 1 Evidence Package

Evidence Package
  1 ─── N Reviews

Attempt
  1 ─── N Audit Events
```

---

# 33. Important Constraints

The database should enforce:

### Attempt numbering

```text
UNIQUE(session_id, attempt_number)
```

### Question ordering

```text
UNIQUE(attempt_id, sequence_number)
```

### Required relationships

Documents cannot exist without a KYC case.

Attempts cannot exist without a session.

Sessions cannot exist without a KYC case.

Document captures cannot exist without an attempt and reference document.

---

# 34. Indexing

Recommended indexes:

```text
kyc_cases.status

documents.case_id

video_sessions.case_id
video_sessions.status

attempts.session_id
attempts.status
attempts.current_step

recordings.attempt_id

face_results.attempt_id

liveness_results.attempt_id

attempt_questions.attempt_id

answers.attempt_question_id

document_captures.attempt_id
document_captures.document_id

evidence_packages.attempt_id

reviews.status
reviews.attempt_id

audit_events.case_id
audit_events.session_id
audit_events.attempt_id
audit_events.created_at
```

---

# 35. Sensitive Data

Potentially sensitive information includes:

```text
Video
Audio
Transcripts
Documents
Face/liveness information
KYC information
Reviewer notes
```

Do not unnecessarily duplicate sensitive information across tables.

Use storage references wherever possible.

---

# 36. Storage Boundary

Database:

```text
Metadata
Relationships
Statuses
Results
Audit information
```

Filesystem:

```text
Original documents
Video recordings
Audio files
Document captures
Generated evidence files
```

---

# 37. V1 Database Principle

The database should answer:

```text
What KYC case is this?
What documents belong to it?
What session is active?
What attempt is active?
What step is the attempt on?
What happened during the attempt?
What evidence was created?
What did the reviewer decide?
```

The filesystem should answer:

```text
Where is the actual media?
```