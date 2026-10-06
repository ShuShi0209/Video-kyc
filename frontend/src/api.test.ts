import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from './api';

const fetchMock = vi.fn();

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('starts a session and escapes the case id it was given', async () => {
    fetchMock.mockResolvedValue(json(201, { session_id: 's-1', attempt_id: 'a-1' }));
    const session = await api.startSession('case/1 ?x');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/kyc-cases/case%2F1%20%3Fx/video-sessions', { method: 'POST' });
    expect(session.session_id).toBe('s-1');
  });

  it('turns the backend error format into an ApiError', async () => {
    fetchMock.mockResolvedValue(
      json(409, { error: { code: 'INVALID_STATE', message: 'Wrong step.', details: { current_step: 'FACE' } } }),
    );
    const err = await api.getSession('s-1').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: 'INVALID_STATE', message: 'Wrong step.', details: { current_step: 'FACE' } });
  });

  it('copes with error responses that are not JSON', async () => {
    fetchMock.mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502, statusText: 'Bad Gateway' }));
    const err = await api.getSession('s-1').catch((e: unknown) => e);
    expect(err).toMatchObject({ status: 502, code: 'HTTP_ERROR', message: 'Request failed (502 Bad Gateway)' });
  });

  it('reports an unreachable server as a network error', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const err = await api.getSession('s-1').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, code: 'NETWORK_ERROR' });
  });

  it.each([
    ['video/webm;codecs=vp9,opus', 'recording.webm'],
    ['video/mp4', 'recording.mp4'],
  ])('uploads a %s recording as multipart form data named %s', async (type, filename) => {
    fetchMock.mockImplementation(async () => json(200, {}));
    await api.uploadRecording('s-1', 'a-1', new Blob(['x'], { type }));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/video-sessions/s-1/attempts/a-1/recording');
    expect(init.method).toBe('POST');
    const file = (init.body as FormData).get('file') as File;
    expect(file.name).toBe(filename);
    expect(file.size).toBe(1);
  });

  it('sends the recording start and stop times as ISO timestamps', async () => {
    fetchMock.mockImplementation(async () => json(200, {}));
    await api.startRecording('s-1', 'a-1', new Date('2026-10-01T12:00:00Z'));
    await api.stopRecording('s-1', 'a-1', new Date('2026-10-01T12:05:00Z'));
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/video-sessions/s-1/attempts/a-1/recording/start');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ started_at: '2026-10-01T12:00:00.000Z' });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/video-sessions/s-1/attempts/a-1/recording/stop');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ ended_at: '2026-10-01T12:05:00.000Z' });
  });

  it('posts face and liveness results as JSON', async () => {
    fetchMock.mockImplementation(async () => json(200, {}));
    const face = { detected: true, face_count: 1, quality: 0.9, timestamp: '2026-10-01T12:00:00Z' };
    const liveness = { status: 'PASS' as const, score: 1, timestamp: '2026-10-01T12:01:00Z', provider: 'browser-face-api' };
    await api.faceDetection('s-1', 'a-1', face);
    await api.liveness('s-1', 'a-1', liveness);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/video-sessions/s-1/attempts/a-1/face');
    expect(fetchMock.mock.calls[0][1].headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(face);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/video-sessions/s-1/attempts/a-1/liveness');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(liveness);
  });
});
