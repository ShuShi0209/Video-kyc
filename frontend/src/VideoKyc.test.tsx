import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VideoKyc } from './VideoKyc';
import { ApiError, api, type SessionData, type SessionState, type StepResponse } from './api';
import type { LivenessProvider } from './providers/LivenessProvider';

// Keep the real ApiError, replace only the network calls.
vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>();
  return {
    ...actual,
    api: {
      startSession: vi.fn(),
      getSession: vi.fn(),
      startRecording: vi.fn(),
      uploadRecording: vi.fn(),
      stopRecording: vi.fn(),
      faceDetection: vi.fn(),
      liveness: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);

// Real delays are 1-2 s per step; tests run the same logic with (almost) no waiting.
const TIMINGS = { faceWarmupMs: 0, retryDelayMs: 0, stepDelayMs: 0, livenessWindowMs: 25, livenessPollMs: 1 };

const READY = 'Permissions Granted. Ready to record.';
const COMPLETE = 'Upload Complete! Phase 4 Finished.';

const SESSION: SessionData = {
  session_id: 's-1',
  attempt_id: 'a-1',
  status: 'IN_PROGRESS',
  current_step: 'STARTED',
  attempt_number: 1,
};

const sessionState = (step: string): SessionState => ({
  session_id: 's-1',
  attempt_id: 'a-1',
  status: 'IN_PROGRESS',
  current_step: step,
  attempt_number: 1,
  recording: { status: 'RECORDING' },
});

const pass = (nextStep: string): StepResponse => ({
  attempt_id: 'a-1',
  step: 'X',
  result: 'PASS',
  next_step: nextStep,
  retry: { allowed: false, retry_count: 0, max_retries: 3 },
});

const fail = (message: string, allowed: boolean, step = 'FACE'): StepResponse => ({
  attempt_id: 'a-1',
  step,
  result: 'FAIL',
  next_step: step,
  retry: { allowed, retry_count: 1, max_retries: 3 },
  message,
});

const networkError = () => new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server.');

class FakeMediaRecorder {
  static isTypeSupported = vi.fn();
  static instances: FakeMediaRecorder[] = [];
  state: 'inactive' | 'recording' = 'inactive';
  mimeType: string;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  start = vi.fn(() => {
    this.state = 'recording';
  });
  stop = vi.fn(() => {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob(['video-bytes'], { type: this.mimeType }) });
    this.onstop?.();
  });

  constructor(_stream: MediaStream, options: { mimeType: string }) {
    this.mimeType = options.mimeType;
    FakeMediaRecorder.instances.push(this);
  }
}

const getUserMedia = vi.fn();
let track: { stop: ReturnType<typeof vi.fn>; onended: (() => void) | null };

function makeProvider(overrides: Partial<LivenessProvider> = {}): LivenessProvider {
  return {
    id: 'test-provider',
    initialize: vi.fn().mockResolvedValue(undefined),
    detectFace: vi.fn().mockResolvedValue({ detected: true, faceCount: 1, quality: 0.9 }),
    startLivenessChallenge: vi.fn().mockReturnValue({ type: 'SMILE', prompt: 'Please smile' }),
    evaluateChallenge: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
}

function renderKyc(options: { provider?: LivenessProvider; timings?: Partial<typeof TIMINGS> } = {}) {
  const provider = options.provider ?? makeProvider();
  const view = render(<VideoKyc caseId="case-1" provider={provider} timings={{ ...TIMINGS, ...options.timings }} />);
  return { provider, ...view };
}

async function startFlow() {
  await screen.findByText(READY);
  fireEvent.click(screen.getByRole('button', { name: 'Start Video KYC' }));
}

const findStopButton = () => screen.findByRole('button', { name: /Stop Recording/ });

beforeEach(() => {
  vi.resetAllMocks();
  FakeMediaRecorder.instances = [];
  FakeMediaRecorder.isTypeSupported.mockReturnValue(true);
  track = { stop: vi.fn(), onended: null };
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] } as unknown as MediaStream;
  getUserMedia.mockResolvedValue(stream);
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder);

  mockedApi.startSession.mockResolvedValue(SESSION);
  mockedApi.getSession.mockResolvedValue(sessionState('FACE'));
  mockedApi.startRecording.mockResolvedValue({ attempt_id: 'a-1', recording_id: 'r-1', status: 'RECORDING', started_at: '' });
  mockedApi.uploadRecording.mockResolvedValue({ recording_id: 'r-1', status: 'COMPLETED', mime_type: 'video/webm', size: 11 });
  mockedApi.stopRecording.mockResolvedValue({ recording_id: 'r-1', status: 'COMPLETED', ended_at: '', next_step: 'FACE' });
  mockedApi.faceDetection.mockResolvedValue(pass('LIVENESS'));
  mockedApi.liveness.mockResolvedValue(pass('GENERAL_QUESTIONS'));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('starting a session', () => {
  it('loads the models, starts the session and gets the camera ready', async () => {
    const { provider } = renderKyc();
    await screen.findByText(READY);
    expect(provider.initialize).toHaveBeenCalled();
    expect(mockedApi.startSession).toHaveBeenCalledWith('case-1');
    expect(getUserMedia).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Start Video KYC' })).toBeTruthy();
  });

  it('explains when camera permission is denied', async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error('denied'), { name: 'NotAllowedError' }));
    renderKyc();
    expect(await screen.findByText(/permissions were denied/i)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Start Video KYC' })).toBeNull();
  });

  it('explains when there is no camera', async () => {
    getUserMedia.mockRejectedValue(Object.assign(new Error('none'), { name: 'NotFoundError' }));
    renderKyc();
    expect(await screen.findByText(/No camera or microphone found/i)).toBeTruthy();
  });

  it('explains that the camera needs a secure connection when mediaDevices is missing', async () => {
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: undefined });
    renderKyc();
    expect(await screen.findByText(/secure connection/i)).toBeTruthy();
  });

  it('reports a model loading failure and never asks for the camera', async () => {
    renderKyc({ provider: makeProvider({ initialize: vi.fn().mockRejectedValue(new Error('404 /models/')) }) });
    expect(await screen.findByText(/Failed to load AI models.*404 \/models\//)).toBeTruthy();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it('shows why the session could not be started', async () => {
    mockedApi.startSession.mockRejectedValue(networkError());
    renderKyc();
    expect(await screen.findByText(/Failed to initialize session\. Cannot reach the server\./)).toBeTruthy();
  });

  it('releases the camera when no recording format is supported', async () => {
    FakeMediaRecorder.isTypeSupported.mockReturnValue(false);
    renderKyc();
    expect(await screen.findByText(/No supported video format/)).toBeTruthy();
    expect(track.stop).toHaveBeenCalled();
  });
});

describe('the recording flow', () => {
  it('records, verifies face and liveness, then uploads and closes the recording', async () => {
    renderKyc();
    await startFlow();
    await screen.findByText('Ready for Questions');

    expect(mockedApi.startRecording).toHaveBeenCalledWith('s-1', 'a-1', expect.any(Date));
    expect(mockedApi.faceDetection).toHaveBeenCalledWith('s-1', 'a-1', {
      detected: true,
      face_count: 1,
      quality: 0.9,
      timestamp: expect.any(String),
    });
    expect(mockedApi.liveness).toHaveBeenCalledWith('s-1', 'a-1', {
      status: 'PASS',
      score: 1,
      timestamp: expect.any(String),
      provider: 'test-provider',
    });
    expect(FakeMediaRecorder.instances[0].start).toHaveBeenCalledWith(1000);

    fireEvent.click(await findStopButton());
    await screen.findByText(COMPLETE);

    const [, , blob] = mockedApi.uploadRecording.mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBeGreaterThan(0);
    expect(mockedApi.stopRecording).toHaveBeenCalledWith('s-1', 'a-1');
    expect(mockedApi.uploadRecording.mock.invocationCallOrder[0]).toBeLessThan(mockedApi.stopRecording.mock.invocationCallOrder[0]);
    expect(track.stop).toHaveBeenCalled();
  });

  it('only starts the recording once, however often the button is clicked', async () => {
    renderKyc();
    await screen.findByText(READY);
    const button = screen.getByRole('button', { name: 'Start Video KYC' });
    fireEvent.click(button);
    fireEvent.click(button);
    await screen.findByText('Ready for Questions');
    expect(mockedApi.startRecording).toHaveBeenCalledTimes(1);
  });

  it('takes the next step from the backend, not from its own assumptions', async () => {
    mockedApi.getSession.mockResolvedValue(sessionState('LIVENESS'));
    const { provider } = renderKyc();
    await startFlow();
    await screen.findByText('Ready for Questions');
    expect(provider.detectFace).not.toHaveBeenCalled();
    expect(mockedApi.faceDetection).not.toHaveBeenCalled();
    expect(mockedApi.liveness).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['GENERAL_QUESTIONS', 'Ready for Questions'],
    ['DOCUMENT_PRESENTATION', 'Resumed session at: DOCUMENT_PRESENTATION'],
  ])('shows where the session is when the backend says it is at %s', async (step, expected) => {
    mockedApi.getSession.mockResolvedValue(sessionState(step));
    renderKyc();
    await startFlow();
    await screen.findByText(expected);
    expect(mockedApi.faceDetection).not.toHaveBeenCalled();
    expect(mockedApi.liveness).not.toHaveBeenCalled();
  });

  it('discards the local recording when the server refuses to start one', async () => {
    mockedApi.startRecording.mockRejectedValue(new ApiError(409, 'INVALID_STATE', 'A recording already exists.'));
    renderKyc();
    await startFlow();
    expect(await screen.findByText(/Failed to start recording on the server\. A recording already exists\./)).toBeTruthy();
    expect(FakeMediaRecorder.instances[0].stop).toHaveBeenCalled();
    expect(track.stop).toHaveBeenCalled();
    expect(mockedApi.uploadRecording).not.toHaveBeenCalled();
  });
});

describe('face detection', () => {
  it('shows the reason and tries again, then carries on once the face is accepted', async () => {
    mockedApi.faceDetection
      .mockResolvedValueOnce(fail('No face detected. Please position your face inside the camera view.', true))
      .mockResolvedValueOnce(pass('LIVENESS'));
    renderKyc({ timings: { retryDelayMs: 300 } });
    await startFlow();
    expect(await screen.findByText(/No face detected/)).toBeTruthy();
    await screen.findByText('Ready for Questions');
    expect(mockedApi.faceDetection).toHaveBeenCalledTimes(2);
  });

  it('stops, keeps the recording and explains when the retry limit is reached', async () => {
    mockedApi.faceDetection.mockResolvedValue(
      fail('We could not verify your face after several attempts. Please start a new session.', false),
    );
    renderKyc();
    await startFlow();
    expect(await screen.findByText(/Face detection failed: We could not verify your face/)).toBeTruthy();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
    expect(mockedApi.uploadRecording).toHaveBeenCalled();
    expect(track.stop).toHaveBeenCalled();
    expect(mockedApi.liveness).not.toHaveBeenCalled();
  });

  it('does not use up a try when the detector itself breaks', async () => {
    renderKyc({ provider: makeProvider({ detectFace: vi.fn().mockRejectedValue(new Error('wasm crashed')) }) });
    await startFlow();
    expect(await screen.findByText(/Face detection is not available/)).toBeTruthy();
    expect(mockedApi.faceDetection).not.toHaveBeenCalled();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
  });

  it('retries after a network error without counting it as a failed face check', async () => {
    mockedApi.faceDetection.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(pass('LIVENESS'));
    renderKyc();
    await startFlow();
    await screen.findByText('Ready for Questions');
    expect(mockedApi.faceDetection).toHaveBeenCalledTimes(2);
  });

  it('gives up after repeated network errors', async () => {
    mockedApi.faceDetection.mockRejectedValue(networkError());
    renderKyc();
    await startFlow();
    expect(await screen.findByText(/Face detection failed: Cannot reach the server\./)).toBeTruthy();
    expect(mockedApi.faceDetection).toHaveBeenCalledTimes(4);
  });

  it('asks the backend where the attempt is when a request is rejected as out of sync', async () => {
    mockedApi.faceDetection.mockRejectedValueOnce(new ApiError(409, 'INVALID_STATE', 'FACE cannot be submitted during the current KYC step.'));
    mockedApi.getSession.mockResolvedValueOnce(sessionState('FACE')).mockResolvedValueOnce(sessionState('LIVENESS'));
    renderKyc();
    await startFlow();
    await screen.findByText('Ready for Questions');
    expect(mockedApi.faceDetection).toHaveBeenCalledTimes(1);
    expect(mockedApi.liveness).toHaveBeenCalledTimes(1);
  });

  it('fails clearly when the backend rejects the step and is not ahead of us', async () => {
    mockedApi.faceDetection.mockRejectedValue(new ApiError(409, 'RETRY_LIMIT_REACHED', 'Maximum face retries reached.'));
    renderKyc();
    await startFlow();
    expect(await screen.findByText(/Face detection failed: Maximum face retries reached\./)).toBeTruthy();
  });
});

describe('liveness', () => {
  it('shows the challenge, retries after a failed one and then continues', async () => {
    mockedApi.liveness
      .mockResolvedValueOnce(fail('Liveness check failed. Please follow the on-screen instruction and try again.', true, 'LIVENESS'))
      .mockResolvedValueOnce(pass('GENERAL_QUESTIONS'));
    // The first challenge is never completed in time; the second one is.
    const provider = makeProvider({ evaluateChallenge: vi.fn(async () => mockedApi.liveness.mock.calls.length > 0) });
    renderKyc({ provider, timings: { livenessWindowMs: 5, retryDelayMs: 300 } });
    await startFlow();
    expect(await screen.findByText(/Liveness check failed/)).toBeTruthy();
    await screen.findByText('Ready for Questions');
    expect(mockedApi.liveness).toHaveBeenCalledTimes(2);
    expect(mockedApi.liveness.mock.calls[0][2]).toMatchObject({ status: 'FAIL', score: 0 });
    expect(mockedApi.liveness.mock.calls[1][2]).toMatchObject({ status: 'PASS', score: 1 });
  });

  it('stops and keeps the recording when the retry limit is reached', async () => {
    mockedApi.liveness.mockResolvedValue(fail('We could not complete the liveness check after several attempts.', false, 'LIVENESS'));
    renderKyc();
    await startFlow();
    expect(await screen.findByText(/Liveness failed: We could not complete the liveness check/)).toBeTruthy();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
    expect(mockedApi.uploadRecording).toHaveBeenCalled();
  });

  it('does not report a result when the liveness provider itself breaks', async () => {
    renderKyc({ provider: makeProvider({ evaluateChallenge: vi.fn().mockRejectedValue(new Error('landmarks failed')) }) });
    await startFlow();
    expect(await screen.findByText(/liveness check is not available/)).toBeTruthy();
    expect(mockedApi.liveness).not.toHaveBeenCalled();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
  });
});

describe('uploading', () => {
  it('lets the user retry a failed upload without recording again', async () => {
    mockedApi.uploadRecording.mockRejectedValueOnce(networkError());
    renderKyc();
    await startFlow();
    fireEvent.click(await findStopButton());
    expect(await screen.findByText(/Failed to upload recording/)).toBeTruthy();
    expect(mockedApi.stopRecording).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Retry upload' }));
    await screen.findByText(COMPLETE);
    expect(mockedApi.uploadRecording).toHaveBeenCalledTimes(2);
    expect(mockedApi.stopRecording).toHaveBeenCalledTimes(1);
  });

  it('does not upload twice when only closing the recording failed', async () => {
    mockedApi.stopRecording.mockRejectedValueOnce(networkError());
    renderKyc();
    await startFlow();
    fireEvent.click(await findStopButton());
    await screen.findByText(/Failed to upload recording/);
    fireEvent.click(screen.getByRole('button', { name: 'Retry upload' }));
    await screen.findByText(COMPLETE);
    expect(mockedApi.uploadRecording).toHaveBeenCalledTimes(1);
    expect(mockedApi.stopRecording).toHaveBeenCalledTimes(2);
  });

  it('treats a recording the server already stored as uploaded', async () => {
    mockedApi.uploadRecording.mockRejectedValueOnce(
      new ApiError(409, 'INVALID_STATE', 'Cannot accept an upload.', { recording_status: 'COMPLETED' }),
    );
    renderKyc();
    await startFlow();
    fireEvent.click(await findStopButton());
    await screen.findByText(COMPLETE);
    expect(mockedApi.stopRecording).toHaveBeenCalledTimes(1);
  });
});

describe('when things go wrong mid-session', () => {
  it('keeps what was recorded if the recorder reports an error', async () => {
    mockedApi.faceDetection.mockImplementation(() => new Promise(() => undefined));
    renderKyc();
    await startFlow();
    await waitFor(() => expect(mockedApi.faceDetection).toHaveBeenCalled());
    FakeMediaRecorder.instances[0].onerror?.();
    expect(await screen.findByText(/Recording failed/)).toBeTruthy();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
    expect(mockedApi.uploadRecording).toHaveBeenCalled();
  });

  it('keeps what was recorded if the camera is unplugged', async () => {
    mockedApi.faceDetection.mockImplementation(() => new Promise(() => undefined));
    renderKyc();
    await startFlow();
    await waitFor(() => expect(mockedApi.faceDetection).toHaveBeenCalled());
    track.onended?.();
    expect(await screen.findByText(/camera was disconnected/)).toBeTruthy();
    await waitFor(() => expect(mockedApi.stopRecording).toHaveBeenCalled());
  });

  it('releases the camera and the recorder when the page is left mid-session', async () => {
    mockedApi.faceDetection.mockImplementation(() => new Promise(() => undefined));
    const { unmount } = renderKyc();
    await startFlow();
    await waitFor(() => expect(mockedApi.faceDetection).toHaveBeenCalled());
    unmount();
    expect(track.stop).toHaveBeenCalled();
    expect(FakeMediaRecorder.instances[0].stop).toHaveBeenCalled();
    expect(mockedApi.uploadRecording).not.toHaveBeenCalled();
  });
});
