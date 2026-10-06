const API_BASE = '/api/v1';

export interface DocumentInfo {
  id: string;
  document_type: string;
  filename: string;
}

export interface SessionData {
  session_id: string;
  attempt_id: string;
  status: string;
  current_step: string;
  attempt_number: number;
  recording?: { status: string };
  documents?: DocumentInfo[];
}

export interface SessionState {
  session_id: string;
  attempt_id: string;
  status: string;
  current_step: string;
  attempt_number: number;
  recording: { status: string };
}

export interface RetryInfo {
  allowed: boolean;
  retry_count: number;
  max_retries: number;
}

export interface StepResponse {
  attempt_id: string;
  step: string;
  result: 'PASS' | 'FAIL';
  next_step: string;
  retry: RetryInfo;
  message?: string | null;
}

export interface FacePayload {
  detected: boolean;
  face_count: number;
  quality: number;
  timestamp: string;
}

export interface LivenessPayload {
  status: 'PASS' | 'FAIL';
  score: number;
  timestamp: string;
  provider?: string;
}

export interface RecordingStartResponse {
  attempt_id: string;
  recording_id: string;
  status: string;
  started_at: string;
}

export interface RecordingUploadResponse {
  recording_id: string;
  status: string;
  mime_type: string;
  size: number;
}

export interface RecordingStopResponse {
  recording_id: string;
  status: string;
  ended_at: string;
  next_step: string;
}

/** Error returned by the backend ({"error": {code, message, details}}) or raised for a network failure. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const error = body?.error;
    if (error && typeof error.code === 'string') {
      return new ApiError(res.status, error.code, error.message ?? res.statusText, error.details ?? {});
    }
  } catch {
    // The body was not JSON; fall through to the generic error.
  }
  return new ApiError(res.status, 'HTTP_ERROR', `Request failed (${res.status}${res.statusText ? ' ' + res.statusText : ''})`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and that the backend is running.');
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

function attemptPath(sessionId: string, attemptId: string): string {
  return `/video-sessions/${encodeURIComponent(sessionId)}/attempts/${encodeURIComponent(attemptId)}`;
}

function postJson(body: unknown): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

function extensionFor(mimeType: string): string {
  return mimeType.toLowerCase().startsWith('video/mp4') ? 'mp4' : 'webm';
}

export const api = {
  startSession: (caseId: string) =>
    request<SessionData>(`/kyc-cases/${encodeURIComponent(caseId)}/video-sessions`, { method: 'POST' }),

  getSession: (sessionId: string) => request<SessionState>(`/video-sessions/${encodeURIComponent(sessionId)}`),

  startRecording: (sessionId: string, attemptId: string, startedAt: Date = new Date()) =>
    request<RecordingStartResponse>(
      `${attemptPath(sessionId, attemptId)}/recording/start`,
      postJson({ started_at: startedAt.toISOString() }),
    ),

  uploadRecording: (sessionId: string, attemptId: string, blob: Blob) => {
    const form = new FormData();
    form.append('file', blob, `recording.${extensionFor(blob.type)}`);
    return request<RecordingUploadResponse>(`${attemptPath(sessionId, attemptId)}/recording`, { method: 'POST', body: form });
  },

  stopRecording: (sessionId: string, attemptId: string, endedAt: Date = new Date()) =>
    request<RecordingStopResponse>(
      `${attemptPath(sessionId, attemptId)}/recording/stop`,
      postJson({ ended_at: endedAt.toISOString() }),
    ),

  faceDetection: (sessionId: string, attemptId: string, payload: FacePayload) =>
    request<StepResponse>(`${attemptPath(sessionId, attemptId)}/face`, postJson(payload)),

  liveness: (sessionId: string, attemptId: string, payload: LivenessPayload) =>
    request<StepResponse>(`${attemptPath(sessionId, attemptId)}/liveness`, postJson(payload)),
};
