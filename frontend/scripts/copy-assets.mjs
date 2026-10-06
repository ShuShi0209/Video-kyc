// Copies the face-detection model weights and the TensorFlow.js WASM binaries out of node_modules
// into public/, so Vite serves them at /models/ and /wasm/. Runs on install, dev and build.
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const modules = join(root, 'node_modules');

const MODEL_PREFIXES = ['tiny_face_detector_model', 'face_landmark_68_model', 'face_expression_model'];

function copyMatching(fromDir, toDir, accept) {
  if (!existsSync(fromDir)) {
    console.error(`[assets] ${fromDir} not found. Run "npm install" first.`);
    process.exit(1);
  }
  mkdirSync(toDir, { recursive: true });
  let copied = 0;
  for (const name of readdirSync(fromDir).filter(accept)) {
    const from = join(fromDir, name);
    const to = join(toDir, name);
    if (existsSync(to) && statSync(to).size === statSync(from).size) continue;
    copyFileSync(from, to);
    copied += 1;
  }
  return copied;
}

const models = copyMatching(
  join(modules, '@vladmandic', 'face-api', 'model'),
  join(root, 'public', 'models'),
  (name) => MODEL_PREFIXES.some((prefix) => name.startsWith(prefix)),
);
const wasm = copyMatching(
  join(modules, '@tensorflow', 'tfjs-backend-wasm', 'dist'),
  join(root, 'public', 'wasm'),
  (name) => name.endsWith('.wasm'),
);
console.log(`[assets] public/models: ${models} file(s) copied, public/wasm: ${wasm} file(s) copied`);
