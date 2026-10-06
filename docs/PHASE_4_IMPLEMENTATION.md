# Phase 4 Implementation Report: Fixes and Hardening

Scope: session start, continuous recording, face detection, liveness and automatic retries, up to the point
where the flow reaches `GENERAL_QUESTIONS`. Questions, documents, evidence and review are still the earlier
stubs and were only touched to keep them working.

## A note on phase numbers

`ROADMAP.md` calls Phase 4 "Continuous Recording" and Phases 5 and 6 "Face Detection" and "Liveness".
The implementation reports merged roadmap Phases 2 and 3 and therefore called recording "Phase 3", and the
frontend tests call face detection plus liveness "Phase 4 Flow". This report uses the second meaning
(recording + face + liveness + retries). If you want the numbering aligned with the roadmap, that is a
documentation-only change.

## What was broken, and what changed

### Backend

| Problem (reproduced) | Fix |
|---|---|
| `requirements.txt` lacked `python-multipart`; a fresh install crashed on import | Added |
| Errors came back as `{"detail": {"error": ...}}`, validation errors and 404s in FastAPI's own shape | One handler layer (`core/errors.py`) returns `{"error": {code, message, details}}` everywhere; 422 -> `VALIDATION_ERROR` with `details.fields` |
| `POST .../recording/stop` set the attempt to `EVIDENCE_PACKAGE_CREATED` no matter what, so stopping early (which the frontend does on a failed retry limit) bricked the attempt | Stop only closes the recording. The attempt advances to `EVIDENCE_PACKAGE_CREATED` only from `RECORDING_COMPLETE` once the file is uploaded. The route moved from `api_documents.py` to `api.py` |
| Upload accepted any bytes, any session id in the URL, and silently overwrote an earlier upload | Ownership check, container detected from the file's magic bytes (WebM / MP4), size cap (`MAX_UPLOAD_BYTES`), empty-file check, atomic write (temp file, then rename), second upload -> 409 |
| Files went to a CWD-relative `storage/recordings/...` and the DB held that physical path | Stored under `STORAGE_DIR` (default: project-root `storage/`) with a logical key `recordings/<attempt_id>/recording.<ext>` |
| Second session start marked the old one `"FAILED"` (not a valid status) and set a column that does not exist | Old sessions become `CANCELLED`, their attempts `FAILED`, their open recordings `FAILED`, with a `SESSION_ABANDONED` audit event. An untouched session is handed out again (200) so duplicate requests and React StrictMode are harmless. A session that is past live capture (waiting for review) is never abandoned (409) |
| `recording/start` did not move `STARTED` -> `FACE` (state-machine table), so `/face` worked with no recording and jumped over `FACE` | `recording/start` moves to `FACE`; `/face` and `/liveness` require exactly their own step |
| Face/liveness: no `FACE_FAILED` / `LIVENESS_FAILED` audit events, no quality threshold, any liveness status string silently counted as FAIL, exhausted retries left the attempt `IN_PROGRESS` forever, one global retry limit | Audit events for every failure, `FACE_MIN_QUALITY` / `LIVENESS_MIN_SCORE`, reason-specific messages (no face / several faces / low quality), `status` must be `PASS` or `FAIL` (else 422), per-step `FACE_MAX_RETRIES` / `LIVENESS_MAX_RETRIES` (default `MAX_RETRIES`), exhausted -> attempt `FAILED` + `RETRY_LIMIT_REACHED` afterwards |
| `seed.py` crashed on a clean DB (`file_size` is not a column of `Document`) | Rewritten; `python seed.py --new` always creates a case |
| Tests wrote into the dev database and never cleaned up (and `seed.py` then reported that fake case) | Every test runs inside a rolled-back transaction and uses a temp storage dir; settings no longer depend on your `.env` |
| `.env` was looked up relative to the working directory | Anchored to the project root |
| No CORS (only worked through the Vite proxy) | `CORS_ORIGINS` (default: the Vite dev origins) |

### Frontend

| Problem (reproduced) | Fix |
|---|---|
| There was no `public/` folder: `/models/*`, `/wasm/*` and `/favicon.svg` returned `index.html`, so the face models could never load | `scripts/copy-assets.mjs` copies the model weights and WASM binaries out of `node_modules` into `public/` on `npm install`, `npm run dev` and `npm run build` (generated, git-ignored) |
| `BrowserLivenessProvider` imported a second copy of tfjs-core / tfjs-backend-wasm next to the one face-api bundles: every kernel registered twice, and `setWasmPaths` reached the wrong copy, so WASM never started | It now configures face-api's own TensorFlow.js; WASM starts from `/wasm/` and falls back to WebGL / CPU |
| Camera not released on unmount or after an error (the cleanup read the `<video>` ref, which is already `null`) | Stream, recorder and chunks live in refs and are released on every exit path |
| A throwing detector or liveness provider was swallowed (UI stuck on "Detecting face...") | Reported as an error; it is never sent to the backend, so it cannot use up the user's tries |
| Timers kept running after stop/unmount | Every loop is cancellable |
| Next step was assumed locally | After `recording/start` the step comes from `GET /video-sessions/{id}`; `INVALID_STATE` re-syncs from the backend; network errors are retried a few times without counting as a failed check |
| Upload failure was a dead end | "Retry upload" keeps the recorded video; an upload the server already stored counts as done |
| No handling of recorder errors / camera unplugged | Both end the session as an error and keep what was recorded |
| `api.ts` threw `Error('Failed to ...')` and typed everything `any` | Typed client with `ApiError {status, code, message, details}` |
| Models were downloaded with the main bundle and loaded before the session started | The 1.5 MB provider is a lazy chunk and loads in parallel with the session |
| `new BrowserLivenessProvider()` on every render, UTF-16 `VideoKyc.bak.tsx` inside `src/`, no `test` script, 1 lint error + 9 warnings | Fixed; backup removed (it was the pre-face-detection version); `npm test`, `npm run typecheck` added; lint is clean |
| Vite proxy pointed at `localhost` (resolves to `::1` on some Node/Windows setups; uvicorn listens on IPv4) | Points at `127.0.0.1` |

## Behaviour and contract notes

- `POST /kyc-cases/{id}/video-sessions` returns 201 for a new session and 200 when it hands back an untouched one.
- `POST .../recording/stop` returns `status` `COMPLETED` (file uploaded) or `STOPPING` (not uploaded yet) and `next_step` is the attempt's current step unless it advanced.
- Upload errors use `MEDIA_UPLOAD_FAILED` with `details.reason`: `UNSUPPORTED_MEDIA_TYPE` (415), `UNREADABLE_MEDIA` / `EMPTY_FILE` (422), `FILE_TOO_LARGE` (413).
- The liveness request accepts an optional `provider` string (stored with the result; default `BROWSER`).
- Stored `retry_count` on face/liveness rows is now the number of retries that preceded the result (0 on the first try).
- Terminal policy when retries run out is provisional until Phase 7: attempt `FAILED`, step unchanged, user starts a new session.

## Running it

```
# backend (from backend/)
pip install -r requirements.txt
alembic upgrade head
python seed.py              # prints a case id
uvicorn main:app --reload
python -m pytest            # needs the Postgres from docker-compose

# frontend (from frontend/)
npm install                 # also copies models + wasm into public/
npm run dev
npm test && npm run typecheck && npm run lint && npm run build
```

## Verification done

- Backend: 57 tests pass; `alembic check` reports no drift; the suite leaves no rows or files behind.
- Frontend: 37 tests pass (about 2 s), `tsc -b` clean, `oxlint` 0 warnings / 0 errors, production build OK.
- Real headless Chromium with a fake camera against the real backend and Postgres:
  - no face in view: two failed face checks, error shown, partial recording uploaded and closed, attempt `FAILED`, audit trail complete;
  - one smiling face in view: face pass, liveness pass, `Ready for Questions`, stop, a real 0.6-2.9 MB WebM stored and accepted, attempt left at `GENERAL_QUESTIONS`;
  - models and WASM served from `/models` and `/wasm`, TensorFlow.js backend `wasm`.

## Not covered / worth knowing

- Head-turn challenges were not exercised in a browser (a static test image cannot turn its head); smile and the failure paths were.
- The MP4 (Safari) recording path is unit-tested on the backend but was not run in a real Safari.
- A browser refresh mid-session starts a new session; the old one is abandoned (continuing a half-recorded session is Phase 20).
- Face and liveness verdicts are still computed in the browser, as designed for V1; the server only enforces thresholds and state.
- Your `.env` has `MAX_RETRIES=10` while the docs say 3. It was left as is (and is not in the zip).
