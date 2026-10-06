import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type SessionData, type StepResponse } from './api';
import './VideoKyc.css';
import type { LivenessChallenge, LivenessProvider } from './providers/LivenessProvider';

export interface Timings {
  /** Let the camera settle before every face check. */
  faceWarmupMs: number;
  /** Pause before checking again after a failed attempt. */
  retryDelayMs: number;
  /** Short pause so the user can read "Face detected" before the next step starts. */
  stepDelayMs: number;
  /** How long the user has to perform a liveness challenge. */
  livenessWindowMs: number;
  livenessPollMs: number;
}

const DEFAULT_TIMINGS: Timings = {
  faceWarmupMs: 1500,
  retryDelayMs: 2000,
  stepDelayMs: 1000,
  livenessWindowMs: 5000,
  livenessPollMs: 200,
};

interface VideoKycProps {
  caseId: string;
  /** Replaces the browser face/liveness provider (used by tests). */
  provider?: LivenessProvider;
  timings?: Partial<Timings>;
  /** Called when the user leaves after a failure or after a finished session. */
  onExit?: () => void;
}

type Phase = 'loading' | 'ready' | 'recording' | 'finishing' | 'done' | 'error';

const MAX_NETWORK_RETRIES = 3;
const RECORDER_TIMESLICE_MS = 1000;
const RECORDER_MIME_TYPES = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'];
const COMPLETE_MESSAGE = 'Upload Complete! Phase 4 Finished.';

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
const clock = () => Date.now();
const now = () => new Date();

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : 'Unknown error';
}

function mediaErrorMessage(err: unknown): string {
  const name = (err as { name?: string } | null)?.name ?? '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Camera and Microphone permissions were denied. Please allow access to proceed.';
  }
  if (name === 'NotFoundError') return 'No camera or microphone found on this device.';
  return 'Failed to access media devices: ' + describeError(err);
}

function formatTime(secs: number): string {
  const m = Math.floor(secs / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// The browser provider (face-api + TensorFlow.js, ~1.5 MB) is only downloaded once a session is opened.
let defaultProvider: Promise<LivenessProvider> | null = null;
function loadDefaultProvider(): Promise<LivenessProvider> {
  defaultProvider ??= import('./providers/BrowserLivenessProvider')
    .then((module) => new module.BrowserLivenessProvider())
    .catch((err) => {
      defaultProvider = null;
      throw err;
    });
  return defaultProvider;
}

export function VideoKyc({ caseId, provider: providerProp, timings: timingOverrides, onExit }: VideoKycProps) {
  const [timings] = useState<Timings>(() => ({ ...DEFAULT_TIMINGS, ...timingOverrides }));
  const [phase, setPhase] = useState<Phase>('loading');
  const [status, setStatus] = useState('Initializing Models...');
  const [error, setError] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [retryingUpload, setRetryingUpload] = useState(false);
  const [kycStep, setKycStep] = useState('INIT');
  const [faceMessage, setFaceMessage] = useState('');
  const [challenge, setChallenge] = useState<LivenessChallenge | null>(null);
  const [timer, setTimer] = useState(0);

  const videoRef = useRef<HTMLVideoElement>(null);
  const providerRef = useRef<LivenessProvider | null>(null);
  const sessionRef = useRef<SessionData | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const mimeRef = useRef('video/webm');
  const blobRef = useRef<Blob | null>(null);
  const uploadedRef = useRef(false);
  const phaseRef = useRef<Phase>('loading');
  const runIdRef = useRef(0); // bumping this cancels any running face/liveness loop

  const changePhase = (next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
  };

  const isStale = (runId: number) => runId !== runIdRef.current;

  // ---- camera + recorder -------------------------------------------------------------------

  const releaseMedia = () => {
    // The stream lives in a ref: the <video> element may already be gone (error panel, unmount).
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const discardRecording = () => {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      try {
        if (recorder.state !== 'inactive') recorder.stop();
      } catch {
        // already stopped
      }
    }
    chunksRef.current = [];
    releaseMedia();
  };

  const stopRecorder = (): Promise<Blob | null> => {
    const recorder = recorderRef.current;
    if (!recorder) return Promise.resolve(blobRef.current); // already stopped earlier
    recorderRef.current = null;
    return new Promise((resolve) => {
      const finish = () => {
        const blob = chunksRef.current.length > 0 ? new Blob(chunksRef.current, { type: mimeRef.current }) : null;
        chunksRef.current = [];
        resolve(blob);
      };
      if (recorder.state === 'inactive') {
        finish();
        return;
      }
      recorder.onstop = finish;
      try {
        recorder.stop();
      } catch {
        finish();
      }
    });
  };

  const setupRecorder = (stream: MediaStream): boolean => {
    const mimeType = RECORDER_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
    if (!mimeType) return false;
    const recorder = new MediaRecorder(stream, { mimeType });
    mimeRef.current = mimeType;
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onerror = () => {
      if (recorderRef.current === recorder) fail('Recording failed. The video could not be captured.', { upload: true });
    };
    recorderRef.current = recorder;
    stream.getVideoTracks()[0].onended = () => {
      if (phaseRef.current === 'recording') fail('The camera was disconnected during the session.', { upload: true });
    };
    return true;
  };

  // ---- upload ------------------------------------------------------------------------------

  /** Uploads the finished recording, then closes it on the server. Safe to call again after a failure. */
  const uploadAndClose = async (): Promise<boolean> => {
    const sess = sessionRef.current;
    if (!sess) return false;
    setUploadError('');
    try {
      if (blobRef.current && !uploadedRef.current) {
        try {
          await api.uploadRecording(sess.session_id, sess.attempt_id, blobRef.current);
        } catch (err) {
          // A retry may find the file already stored (the first response was lost): that is fine.
          const alreadyStored =
            err instanceof ApiError && err.code === 'INVALID_STATE' && err.details.recording_status === 'COMPLETED';
          if (!alreadyStored) throw err;
        }
        uploadedRef.current = true;
      }
      await api.stopRecording(sess.session_id, sess.attempt_id);
      return true;
    } catch (err) {
      console.error(err);
      setUploadError('Failed to upload recording.');
      return false;
    }
  };

  const closeRecording = async (): Promise<boolean> => {
    blobRef.current = await stopRecorder();
    releaseMedia();
    return uploadAndClose();
  };

  // ---- failure handling --------------------------------------------------------------------

  /** Fatal error. With `upload`, what was recorded so far is kept as evidence of the failed attempt. */
  const fail = (message: string, options: { upload?: boolean } = {}) => {
    if (phaseRef.current === 'error') return;
    runIdRef.current += 1; // cancels running loops
    setChallenge(null);
    setError(message);
    setStatus('Error');
    changePhase('error');
    if (options.upload) void closeRecording();
    else discardRecording();
  };

  /** The backend is the source of truth for the workflow step; the frontend never guesses it. */
  const fetchCurrentStep = async (runId: number): Promise<string | null> => {
    const sess = sessionRef.current;
    if (!sess) return null;
    for (let attempt = 0; ; attempt += 1) {
      try {
        return (await api.getSession(sess.session_id)).current_step;
      } catch (err) {
        if (isStale(runId)) return null;
        const retryable = err instanceof ApiError && err.code === 'NETWORK_ERROR' && attempt < MAX_NETWORK_RETRIES;
        if (!retryable) {
          fail(`Could not read the session state. ${describeError(err)}`, { upload: true });
          return null;
        }
        await sleep(timings.retryDelayMs);
      }
    }
  };

  /** After a face/liveness request failed: returns true when the same step should simply be tried again. */
  const shouldRetryAfter = async (
    err: unknown,
    runId: number,
    label: string,
    currentStep: string,
    network: { failures: number },
  ): Promise<boolean> => {
    if (isStale(runId)) return false;
    if (err instanceof ApiError && err.code === 'NETWORK_ERROR' && network.failures < MAX_NETWORK_RETRIES) {
      network.failures += 1; // never reached the backend, so it did not use up one of the user's tries
      setStatus('Connection problem. Retrying...');
      await sleep(timings.retryDelayMs);
      return !isStale(runId);
    }
    if (err instanceof ApiError && err.code === 'INVALID_STATE') {
      const step = await fetchCurrentStep(runId);
      if (step === null) return false;
      if (step !== currentStep) {
        await advance(step, runId);
        return false;
      }
    }
    fail(`${label} failed: ${describeError(err)}`, { upload: true });
    return false;
  };

  // ---- workflow steps ----------------------------------------------------------------------

  const advance = async (step: string, runId: number) => {
    if (isStale(runId)) return;
    switch (step) {
      case 'STARTED':
      case 'FACE':
        await runFaceStep(runId);
        break;
      case 'LIVENESS':
        await runLivenessStep(runId);
        break;
      case 'GENERAL_QUESTIONS':
        setKycStep(step);
        setChallenge(null);
        setStatus('Ready for Questions');
        break;
      default:
        setKycStep(step);
        setStatus('Resumed session at: ' + step);
    }
  };

  const runFaceStep = async (runId: number) => {
    const sess = sessionRef.current;
    const provider = providerRef.current;
    if (!sess || !provider) return;
    setKycStep('FACE');
    setFaceMessage('Look directly at the camera');
    setStatus('Detecting face...');
    const network = { failures: 0 };

    while (!isStale(runId)) {
      await sleep(timings.faceWarmupMs);
      const video = videoRef.current;
      if (isStale(runId) || !video) return;

      let detection;
      try {
        detection = await provider.detectFace(video);
      } catch (err) {
        // A broken detector says nothing about the user's face, so it must not use up one of their tries.
        console.error(err);
        if (!isStale(runId)) fail('Face detection is not available right now. Please reload the page and try again.', { upload: true });
        return;
      }
      if (isStale(runId)) return;

      let response: StepResponse;
      try {
        response = await api.faceDetection(sess.session_id, sess.attempt_id, {
          detected: detection.detected,
          face_count: detection.faceCount,
          quality: detection.quality,
          timestamp: now().toISOString(),
        });
      } catch (err) {
        if (await shouldRetryAfter(err, runId, 'Face detection', 'FACE', network)) continue;
        return;
      }
      if (isStale(runId)) return;

      if (response.result === 'PASS') {
        setFaceMessage('Face detected');
        setStatus('Checking liveness...');
        await sleep(timings.stepDelayMs);
        await advance(response.next_step, runId);
        return;
      }
      if (response.retry?.allowed) {
        setFaceMessage(response.message || 'Please position your face clearly in the camera.');
        await sleep(timings.retryDelayMs);
        continue;
      }
      fail('Face detection failed: ' + (response.message || 'Retry limit reached'), { upload: true });
      return;
    }
  };

  const runLivenessStep = async (runId: number) => {
    const sess = sessionRef.current;
    const provider = providerRef.current;
    if (!sess || !provider) return;
    setKycStep('LIVENESS');
    setStatus('Checking liveness...');
    const network = { failures: 0 };

    while (!isStale(runId)) {
      const current = provider.startLivenessChallenge();
      setChallenge(current);

      let passed = false;
      try {
        const deadline = clock() + timings.livenessWindowMs;
        while (!passed && clock() < deadline && !isStale(runId)) {
          const video = videoRef.current;
          if (!video) return;
          passed = await provider.evaluateChallenge(video, current);
          if (!passed) await sleep(timings.livenessPollMs);
        }
      } catch (err) {
        console.error(err);
        setChallenge(null);
        if (!isStale(runId)) fail('The liveness check is not available right now. Please reload the page and try again.', { upload: true });
        return;
      }
      setChallenge(null);
      if (isStale(runId)) return;

      let response: StepResponse;
      try {
        response = await api.liveness(sess.session_id, sess.attempt_id, {
          status: passed ? 'PASS' : 'FAIL',
          score: passed ? 1.0 : 0.0,
          timestamp: now().toISOString(),
          provider: provider.id,
        });
      } catch (err) {
        if (await shouldRetryAfter(err, runId, 'Liveness', 'LIVENESS', network)) continue;
        return;
      }
      if (isStale(runId)) return;

      if (response.result === 'PASS') {
        setStatus('Liveness verified');
        await sleep(timings.stepDelayMs);
        await advance(response.next_step, runId);
        return;
      }
      if (response.retry?.allowed) {
        setStatus(response.message || 'Liveness verification failed. Please try again.');
        await sleep(timings.retryDelayMs);
        continue;
      }
      fail('Liveness failed: ' + (response.message || 'Retry limit reached'), { upload: true });
      return;
    }
  };

  // ---- user actions ------------------------------------------------------------------------

  const handleStartRecording = async () => {
    const sess = sessionRef.current;
    const recorder = recorderRef.current;
    if (!sess || !recorder || phaseRef.current !== 'ready') return;

    const runId = ++runIdRef.current;
    changePhase('recording');
    setTimer(0);
    setStatus('Starting recording...');

    const startedAt = now();
    try {
      recorder.start(RECORDER_TIMESLICE_MS);
    } catch (err) {
      fail('Could not start recording: ' + describeError(err));
      return;
    }
    try {
      await api.startRecording(sess.session_id, sess.attempt_id, startedAt);
    } catch (err) {
      if (!isStale(runId)) fail(`Failed to start recording on the server. ${describeError(err)}`);
      return;
    }
    if (isStale(runId)) return;

    const step = await fetchCurrentStep(runId);
    if (step === null || isStale(runId)) return;
    await advance(step, runId);
  };

  const handleStopRecording = async () => {
    if (phaseRef.current !== 'recording') return;
    runIdRef.current += 1;
    changePhase('finishing');
    setStatus('Recording stopped. Uploading...');
    if (await closeRecording()) {
      changePhase('done');
      setStatus(COMPLETE_MESSAGE);
    } else {
      setStatus('Error');
    }
  };

  const handleRetryUpload = async () => {
    setRetryingUpload(true);
    const ok = await uploadAndClose();
    setRetryingUpload(false);
    if (ok && phaseRef.current === 'finishing') {
      changePhase('done');
      setStatus(COMPLETE_MESSAGE);
    }
  };

  // ---- lifecycle ---------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      changePhase('loading');
      setError('');
      setUploadError('');
      setStatus('Initializing Models...');

      // Models and session load in parallel; a failure of either is reported separately below.
      const modelsReady = (async () => {
        const provider = providerProp ?? (await loadDefaultProvider());
        providerRef.current = provider;
        await provider.initialize();
      })();
      modelsReady.catch(() => undefined);

      setStatus('Starting session...');
      let sess: SessionData;
      try {
        sess = await api.startSession(caseId);
      } catch (err) {
        if (!cancelled) fail(`Failed to initialize session. ${describeError(err)}`);
        return;
      }
      if (cancelled) return;
      sessionRef.current = sess;

      try {
        await modelsReady;
      } catch (err) {
        if (!cancelled) fail('Failed to load AI models. Please ensure your browser supports WebAssembly: ' + describeError(err));
        return;
      }
      if (cancelled) return;

      setStatus('Session Started. Requesting Camera Permissions...');
      if (!navigator.mediaDevices?.getUserMedia) {
        fail('Camera access needs a secure connection (HTTPS or localhost).');
        return;
      }
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720, facingMode: 'user' },
          audio: true,
        });
      } catch (err) {
        if (!cancelled) fail(mediaErrorMessage(err));
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      if (!setupRecorder(stream)) {
        fail('No supported video format found in this browser.');
        return;
      }
      changePhase('ready');
      setStatus('Permissions Granted. Ready to record.');
    };
    void run();

    return () => {
      cancelled = true;
      runIdRef.current += 1;
      discardRecording();
    };
    // The flow is (re)started per case; providerProp only exists as a test seam.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, providerProp]);

  useEffect(() => {
    if (phase !== 'recording') return;
    const id = window.setInterval(() => setTimer((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  useEffect(() => {
    // Reloading or closing the tab mid-recording loses the in-memory video.
    if (phase !== 'recording' && phase !== 'finishing') return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [phase]);

  const recording = phase === 'recording';

  return (
    <div className="video-kyc-container">
      <header className="kyc-header">
        <h1>Video KYC</h1>
        <div className={`status-badge ${recording ? 'recording' : ''}`} role="status">
          {recording ? <span className="pulse"></span> : null}
          {status}
        </div>
      </header>

      <div className="main-content">
        <div className="video-wrapper">
          {error ? (
            <div className="error-state" role="alert">
              <p>{error}</p>
            </div>
          ) : (
            <>
              <video ref={videoRef} autoPlay playsInline muted className="camera-preview" />
              {recording && <div className="timer-overlay">{formatTime(timer)}</div>}
              {recording && kycStep === 'FACE' && <div className="challenge-overlay">{faceMessage}</div>}
              {recording && kycStep === 'LIVENESS' && challenge && (
                <div className="challenge-overlay highlight">{challenge.prompt}</div>
              )}
            </>
          )}
        </div>

        {uploadError && (
          <div className="notice notice-error" role="alert">
            {uploadError}
          </div>
        )}

        <div className="controls">
          {phase === 'ready' && (
            <button className="btn-primary" onClick={handleStartRecording}>
              Start Video KYC
            </button>
          )}
          {recording && kycStep === 'GENERAL_QUESTIONS' && (
            <button className="btn-danger" onClick={handleStopRecording}>
              Stop Recording & Complete
            </button>
          )}
          {uploadError && (
            <button className="btn-primary" onClick={handleRetryUpload} disabled={retryingUpload}>
              Retry upload
            </button>
          )}
          {onExit && (phase === 'error' || phase === 'done') && (
            <button className="btn-secondary" onClick={onExit}>
              {phase === 'error' ? 'Start over' : 'Back to start'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
