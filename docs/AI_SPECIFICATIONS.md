# AI Specification

## AI-Assisted Video KYC System

**Version:** 1.0  
**Status:** V1 AI Specification  
**Providers:** Groq + Deepgram  
**Environment:** Local + Docker

---

# 1. Purpose

This document defines the AI-related behavior of the V1 Video KYC system.

V1 uses AI for:

```text
Speech-to-Text
Answer Understanding
AI Question Flow
Text-to-Speech
```

V1 does not use AI for:

```text
Final KYC approval
Face identity matching
Advanced document authenticity
Autonomous KYC decision
```

The final KYC decision is made by a human reviewer.

---

# 2. AI Architecture

```text
                         VIDEO KYC
                             │
                             ▼
                     Conversation Service
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
             ASR            LLM            TTS
              │              │              │
              ▼              ▼              ▼
         Deepgram          Groq        TTS Provider
```

The frontend communicates with the application's backend.

It does not communicate directly with Groq or Deepgram.

---

# 3. AI Conversation Flow

```text
AI asks question
       ↓
TTS
       ↓
User hears question
       ↓
User speaks
       ↓
Audio captured
       ↓
ASR
       ↓
Transcript
       ↓
LLM
       ↓
Answer evaluation
       ↓
Next question
       ↓
TTS
```

---

# 4. AI Responsibilities

## ASR

Responsible for:

```text
Audio → Text
```

Provider:

```text
Deepgram
```

---

## LLM

Responsible for:

```text
Understand transcript
Evaluate answer
Determine whether answer is relevant
Return structured result
Support conversation flow
```

Provider:

```text
Groq
```

---

## TTS

Responsible for:

```text
Text → Speech
```

The provider should remain abstracted behind a backend TTS service.

---

# 5. AI Provider Abstraction

The application should not tightly couple business logic to provider SDKs.

Recommended:

```text
backend/
└── services/
    └── ai/
        ├── asr/
        │   ├── interface.py
        │   └── deepgram.py
        │
        ├── llm/
        │   ├── interface.py
        │   └── groq.py
        │
        └── tts/
            ├── interface.py
            └── provider.py
```

The exact directory structure may follow the implementation architecture, but provider abstraction is required.

---

# 6. ASR Contract

## Input

```text
Audio file
```

Example:

```text
audio/webm
```

## Output

Application-level result:

```json
{
  "transcript": "My name is Rahul Sharma",
  "duration_ms": 3200
}
```

The frontend should receive the normalized result rather than a raw Deepgram response.

---

# 7. ASR Responsibilities

The ASR service should:

- Validate audio
- Send audio to Deepgram
- Receive transcription
- Normalize transcription
- Return transcript
- Return duration when available
- Handle provider errors
- Handle timeout
- Avoid exposing provider internals

---

# 8. ASR Failure

If Deepgram fails:

```text
Audio
  ↓
Deepgram
  ↓
ERROR
```

The backend returns:

```json
{
  "error": {
    "code": "PROVIDER_ERROR",
    "message": "The speech recognition service is temporarily unavailable.",
    "details": {
      "service": "asr"
    }
  }
}
```

The raw provider error must not be exposed.

---

# 9. Transcript Storage

The transcript should be stored against the answer.

Example:

```text
attempt
   ↓
attempt_question
   ↓
answer
   ↓
transcript
```

This allows the reviewer to inspect what the user said.

---

# 10. LLM Responsibilities

The LLM evaluates the user's response.

Input:

```text
Question
+
User transcript
```

Output:

```text
Structured answer evaluation
```

---

# 11. LLM Input

Conceptual input:

```json
{
  "question": "What is your full name?",
  "transcript": "My name is Rahul Sharma"
}
```

---

# 12. LLM Output

The application should require structured output.

Example:

```json
{
  "understood": true,
  "relevant": true,
  "reason": "The user provided a name in response to the question."
}
```

The backend should validate this output before using it.

---

# 13. LLM Output Schema

Minimum V1:

```text
understood: boolean
relevant: boolean
reason: string
```

Optional future fields:

```text
confidence
normalized_answer
risk_flags
```

These are not required for V1.

---

# 14. LLM Prompt Principle

The LLM should be instructed to:

- Evaluate only the supplied question and transcript
- Return structured JSON
- Avoid inventing information
- Avoid making final KYC decisions
- Avoid identity verification
- Avoid unsupported assumptions
- Follow the application's output schema

---

# 15. Example LLM Prompt

Conceptual prompt:

```text
You are an answer evaluation component in a Video KYC system.

Evaluate whether the user's response answers the provided question.

Question:
{{question}}

User response:
{{transcript}}

Return JSON only:

{
  "understood": true | false,
  "relevant": true | false,
  "reason": "short explanation"
}

Do not make a KYC approval decision.
Do not infer information that is not present in the user's response.
```

The production prompt should be version-controlled.

---

# 16. LLM Validation

The backend must validate the model output.

If the model returns:

```text
invalid JSON
```

or:

```text
missing fields
```

the backend should not silently accept it.

Return:

```text
CONVERSATION_ERROR
```

or handle the provider failure according to the conversation service policy.

---

# 17. LLM Failure

Potential failures:

```text
Timeout
Provider unavailable
Invalid response
Malformed JSON
Unexpected schema
Rate limit
```

These should be normalized into application-level errors.

---

# 18. TTS Responsibilities

TTS converts AI-generated questions into speech.

Example:

```text
"What is your full name?"
        ↓
       TTS
        ↓
Audio
```

The frontend plays the resulting audio.

---

# 19. TTS Contract

Input:

```json
{
  "text": "What is your full name?"
}
```

Output:

```json
{
  "audio_url": "/api/v1/conversation/audio/tts_001",
  "content_type": "audio/mpeg"
}
```

The exact provider is hidden from the frontend.

---

# 20. AI Conversation Controller

The backend should have a conversation orchestration layer.

Conceptually:

```text
Conversation Controller
        │
        ├── Question Manager
        │
        ├── TTS Service
        │
        ├── ASR Service
        │
        └── LLM Service
```

The controller manages the flow.

---

# 21. Conversation State

The conversation service should know:

```text
Current attempt
Current question
Question sequence
Total questions
Answer submitted
Next question
```

The authoritative KYC workflow state remains in the main backend state machine.

---

# 22. Question Selection

The administrator defines:

```text
Question Pool
N
Random Selection
```

Example:

```text
Pool:
Q1
Q2
Q3
Q4
Q5
Q6

N = 3
```

System selects:

```text
Q4
Q1
Q6
```

The selected questions must be persisted.

---

# 23. Random Selection

Random selection happens when the question session starts.

It should not randomly change every time the frontend refreshes.

Example:

```text
Attempt 1
    ↓
Question selection
    ↓
Q4 → Q1 → Q6
```

After refresh:

```text
Q4 → Q1 → Q6
```

not:

```text
Q2 → Q5 → Q3
```

---

# 24. Question Sequence

Each selected question receives:

```text
sequence_number
```

Example:

```text
Question 1
Question 2
Question 3
```

This sequence must be stored against the attempt.

---

# 25. Conversation Example

```text
Backend selects:

Q1:
"What is your full name?"

       ↓

TTS

       ↓

User hears question

       ↓

User speaks:
"My name is Rahul Sharma."

       ↓

Deepgram

       ↓

Transcript:
"My name is Rahul Sharma."

       ↓

Groq

       ↓

{
  "understood": true,
  "relevant": true
}

       ↓

Next Question

"What is your date of birth?"
```

---

# 26. Question Completion

When all configured questions are answered:

```text
GENERAL_QUESTIONS
       ↓
Questions complete
       ↓
DOCUMENT_PRESENTATION
```

The AI conversation service should notify the workflow service that the question stage is complete.

---

# 27. Answer Quality

V1 should distinguish:

```text
ASR failure
```

from:

```text
User answer quality
```

Example:

### ASR failure

```text
Audio could not be transcribed.
```

This is a technical failure.

### Poor answer

```text
Question:
"What is your date of birth?"

Answer:
"I like cricket."
```

The ASR may work correctly, while the LLM determines:

```json
{
  "understood": true,
  "relevant": false
}
```

The application must define how such an answer is handled without confusing it with an infrastructure failure.

---

# 28. AI Does Not Make Final KYC Decision

The AI must not return:

```text
APPROVE KYC
```

or:

```text
REJECT KYC
```

as the final business decision.

The final V1 decision is:

```text
Human Reviewer
      ↓
APPROVE / RETRY
```

---

# 29. Face AI Boundary

V1 face functionality:

```text
Detect face
Count faces
Basic quality checks
```

V1 does not perform:

```text
Face identity matching
```

Therefore:

```text
Uploaded document face
        ≠
Live camera face matching
```

for V1.

This can be introduced in a future version.

---

# 30. Liveness Boundary

Liveness is responsible for:

```text
Live person / spoof detection
```

It is separate from identity matching.

Therefore:

```text
Liveness PASS
```

does not mean:

```text
Identity MATCH
```

---

# 31. AI Security

API keys must exist only on the backend.

Never expose:

```text
GROQ_API_KEY
DEEPGRAM_API_KEY
TTS_API_KEY
```

to the browser.

---

# 32. AI Provider Configuration

Use environment variables.

Example:

```text
GROQ_API_KEY=
DEEPGRAM_API_KEY=
TTS_API_KEY=
```

Provider configuration should not be hard-coded.

---

# 33. Provider Abstraction Principle

Business logic should call:

```text
ASRService
LLMService
TTSService
```

rather than:

```text
DeepgramClient
GroqClient
SpecificTTSClient
```

directly.

---

# 34. AI Observability

The backend should log safe metadata such as:

```text
request type
service
latency
success/failure
provider
model identifier
```

Do not log unnecessary sensitive information.

Avoid logging:

```text
API keys
full documents
full recordings
unnecessary personal data
```

---

# 35. AI Timeouts

Every external AI call should have a timeout.

Conceptually:

```text
Frontend
   ↓
Backend
   ↓
AI Provider
   ↓
Timeout
   ↓
Controlled Error
```

The application must not wait indefinitely for an external provider.

---

# 36. Provider Failure Strategy

The application should distinguish:

```text
User error
```

from:

```text
System/provider error
```

Examples:

```text
No face detected
    → user-facing retry

Deepgram unavailable
    → provider/system error

LLM timeout
    → conversation service error

TTS unavailable
    → conversation service error
```

---

# 37. AI Data Flow

```text
                   USER
                     │
                     ▼
                Microphone
                     │
                     ▼
              Audio Capture
                     │
                     ▼
                 Backend
                     │
                     ▼
                Deepgram
                     │
                     ▼
                 Transcript
                     │
                     ▼
                   Groq
                     │
                     ▼
              Answer Evaluation
                     │
                     ▼
             Conversation Service
                     │
                     ▼
                  Next Text
                     │
                     ▼
                    TTS
                     │
                     ▼
                  Browser
                     │
                     ▼
                   USER
```

---

# 38. AI and Evidence

AI-related evidence that should be retained:

```text
Question
Transcript
Answer evaluation
Question sequence
Relevant timestamps
```

This allows a human reviewer to understand the conversation.

---

# 39. Evidence Example

```json
{
  "question": "What is your full name?",
  "transcript": "My name is Rahul Sharma",
  "evaluation": {
    "understood": true,
    "relevant": true
  }
}
```

---

# 40. Prompt Versioning

Prompts should be version-controlled.

Example:

```text
answer_evaluation_v1
```

When the prompt changes substantially:

```text
answer_evaluation_v2
```

The version should be stored with AI evaluation metadata where useful.

---

# 41. Model Versioning

Where possible, record the model identifier used for an AI operation.

Example:

```json
{
  "provider": "groq",
  "model": "configured-model",
  "prompt_version": "answer_evaluation_v1"
}
```

Do not hard-code provider-specific model details into frontend code.

---

# 42. AI Service Interfaces

Conceptual interfaces:

```python
class ASRService:
    def transcribe(self, audio):
        pass
```

```python
class LLMService:
    def evaluate_answer(self, question, transcript):
        pass
```

```python
class TTSService:
    def synthesize(self, text):
        pass
```

Concrete providers implement these interfaces.

---

# 43. AI Orchestration

The conversation controller should orchestrate:

```text
Question
   ↓
TTS
   ↓
User Audio
   ↓
ASR
   ↓
Transcript
   ↓
LLM
   ↓
Evaluation
   ↓
Next Question
```

It should not own unrelated KYC workflow responsibilities.

---

# 44. Separation of Concerns

### State Machine

Owns:

```text
KYC workflow
```

### Conversation Service

Owns:

```text
Question conversation
```

### ASR Service

Owns:

```text
Audio → text
```

### LLM Service

Owns:

```text
Answer understanding
```

### TTS Service

Owns:

```text
Text → audio
```

### Evidence Service

Owns:

```text
Evidence aggregation
```

---

# 45. V1 AI Limitations

V1 intentionally does not attempt to solve:

```text
Deep identity verification
Advanced fraud detection
Full document understanding
Autonomous KYC decisions
Complex natural-language interviews
```

The AI should remain narrowly scoped and auditable.

---

# 46. V1 AI Success Criteria

The AI layer is considered complete when:

- [ ] Admin can configure questions
- [ ] System selects N random questions
- [ ] Question sequence is persisted
- [ ] TTS can ask a question
- [ ] User audio can be captured
- [ ] Deepgram returns transcript
- [ ] Transcript is persisted
- [ ] Groq evaluates answer
- [ ] Structured LLM output is validated
- [ ] Next question is selected
- [ ] Conversation completes
- [ ] Provider failures are handled
- [ ] AI evidence is available to reviewer
- [ ] Provider API keys remain backend-only

---

# 47. Final AI Principle

The V1 AI system should follow:

```text
AI assists the KYC process.
AI does not make the final KYC decision.
```

The architecture is:

```text
ASR
 ↓
LLM
 ↓
TTS
 ↓
Conversation

while

Backend State Machine
 ↓
Workflow Control

and

Human Reviewer
 ↓
Final Decision
```

This separation keeps the V1 system predictable, testable, and auditable.