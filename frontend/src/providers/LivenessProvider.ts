export interface LivenessChallenge {
  type: 'TURN_LEFT' | 'TURN_RIGHT' | 'BLINK' | 'SMILE';
  prompt: string;
}

export interface FaceResult {
  detected: boolean;
  faceCount: number;
  quality: number;
}

export interface LivenessResult {
  status: 'PASS' | 'FAIL';
  score: number;
}

export interface LivenessProvider {
  /** Short identifier stored with the liveness result (e.g. "browser-face-api"). */
  readonly id: string;
  /** Loads models. Must be safe to call repeatedly; rejects when the provider cannot work. */
  initialize(): Promise<void>;
  /** Rejects when detection itself is impossible (a provider failure, not a "no face" result). */
  detectFace(video: HTMLVideoElement): Promise<FaceResult>;
  startLivenessChallenge(): LivenessChallenge;
  evaluateChallenge(video: HTMLVideoElement, challenge: LivenessChallenge): Promise<boolean>;
}
