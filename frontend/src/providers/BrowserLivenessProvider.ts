import * as faceapi from '@vladmandic/face-api';
import type { FaceResult, LivenessChallenge, LivenessProvider } from './LivenessProvider';

// face-api bundles its own TensorFlow.js, including the WASM backend, and that is the instance that runs the
// models. Configure *that* one: importing a second copy of tfjs-core / tfjs-backend-wasm registers every kernel
// twice, and the WASM paths set on the extra copy never reach the backend that actually loads the .wasm files.
interface TensorFlowRuntime {
  setBackend(name: string): Promise<boolean>;
  ready(): Promise<void>;
  getBackend(): string;
  setWasmPaths?(prefix: string): void;
}
const tf = (faceapi as unknown as { tf?: TensorFlowRuntime }).tf;

const BASE = import.meta.env.BASE_URL; // "/" unless the app is deployed under a sub-path
const VIDEO_READY_TIMEOUT_MS = 3000;
const SMILE_THRESHOLD = 0.5;
const TURN_RATIO = 0.8;

const CHALLENGES: LivenessChallenge[] = [
  { type: 'TURN_LEFT', prompt: 'Please turn your head to the left' },
  { type: 'TURN_RIGHT', prompt: 'Please turn your head to the right' },
  { type: 'SMILE', prompt: 'Please smile' },
];

export class BrowserLivenessProvider implements LivenessProvider {
  readonly id = 'browser-face-api';
  private initPromise: Promise<void> | null = null;
  private ready = false;

  initialize(): Promise<void> {
    // One shared promise, so concurrent callers do not load the models twice; a failure can be retried.
    this.initPromise ??= this.load().catch((err) => {
      this.initPromise = null;
      throw err;
    });
    return this.initPromise;
  }

  private async load(): Promise<void> {
    await this.selectBackend();
    const modelPath = `${BASE}models/`;
    await Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(modelPath),
      faceapi.nets.faceLandmark68Net.loadFromUri(modelPath),
      faceapi.nets.faceExpressionNet.loadFromUri(modelPath),
    ]);
    this.ready = true;
  }

  private async selectBackend(): Promise<void> {
    if (!tf) {
      console.warn('[Liveness] face-api does not expose its TensorFlow.js runtime; using its default backend');
      return;
    }
    tf.setWasmPaths?.(`${BASE}wasm/`);
    // WASM needs no GPU, so it is the most predictable backend; fall back to whatever else is available.
    for (const name of ['wasm', 'webgl', 'cpu']) {
      try {
        if (await tf.setBackend(name)) {
          await tf.ready();
          console.info(`[Liveness] TensorFlow.js backend: ${tf.getBackend()}`);
          return;
        }
      } catch (err) {
        console.warn(`[Liveness] TensorFlow.js backend "${name}" is not available`, err);
      }
    }
    console.warn('[Liveness] Falling back to the default face-api backend');
  }

  private assertReady(): void {
    if (!this.ready) throw new Error('Face detection models are not loaded');
  }

  private async waitForVideo(video: HTMLVideoElement): Promise<void> {
    const deadline = performance.now() + VIDEO_READY_TIMEOUT_MS;
    while (video.readyState < 2 || video.videoWidth === 0) {
      if (performance.now() > deadline) throw new Error('The camera image is not available');
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  async detectFace(video: HTMLVideoElement): Promise<FaceResult> {
    this.assertReady();
    await this.waitForVideo(video);
    const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
    return {
      detected: detections.length > 0,
      faceCount: detections.length,
      quality: detections.reduce((best, detection) => Math.max(best, detection.score), 0),
    };
  }

  startLivenessChallenge(): LivenessChallenge {
    return CHALLENGES[Math.floor(Math.random() * CHALLENGES.length)];
  }

  async evaluateChallenge(video: HTMLVideoElement, challenge: LivenessChallenge): Promise<boolean> {
    this.assertReady();
    await this.waitForVideo(video);
    const options = new faceapi.TinyFaceDetectorOptions();

    if (challenge.type === 'SMILE') {
      const detection = await faceapi.detectSingleFace(video, options).withFaceExpressions();
      if (!detection) return false;
      console.debug(`[Liveness] smile score ${detection.expressions.happy.toFixed(3)} (needs > ${SMILE_THRESHOLD})`);
      return detection.expressions.happy > SMILE_THRESHOLD;
    }

    if (challenge.type === 'TURN_LEFT' || challenge.type === 'TURN_RIGHT') {
      const detection = await faceapi.detectSingleFace(video, options).withFaceLandmarks();
      if (!detection) return false;
      // Rough head pose from the landmarks (raw, un-mirrored frame): how far the nose bridge sits from each outer eye corner.
      const noseX = detection.landmarks.getNose()[0].x;
      const leftDist = noseX - detection.landmarks.getLeftEye()[0].x;
      const rightDist = detection.landmarks.getRightEye()[3].x - noseX;
      console.debug(`[Liveness] turn distances left ${leftDist.toFixed(1)} / right ${rightDist.toFixed(1)}`);
      // The user's left is on the right-hand side of the raw frame, so turning left shrinks rightDist.
      return challenge.type === 'TURN_LEFT' ? rightDist < leftDist * TURN_RATIO : leftDist < rightDist * TURN_RATIO;
    }

    return false;
  }
}
