/**
 * Build-time shim for the `@mediapipe/pose` package.
 *
 * WHY THIS FILE EXISTS
 *
 * `@tensorflow-models/pose-detection` ships one ES module bundle whose very
 * first statement is a static, unconditional, top-level import:
 *
 *     import { Pose } from "@mediapipe/pose";
 *
 * That symbol is used in exactly one place inside the library: the constructor
 * of `BlazePoseMediaPipeDetector`, which is only ever reached by
 * `createDetector(SupportedModels.BlazePose, { runtime: "mediapipe" })`.
 * Because the import is static rather than lazy, every bundler has to resolve
 * it even for applications that never select that runtime.
 *
 * The real `@mediapipe/pose` package cannot satisfy it. Its `package.json`
 * advertises `"module": "pose.js"`, but `pose.js` is a Closure-compiled global
 * script containing no module syntax of any kind — no `export`, no
 * `module.exports`, no `define.amd`. It publishes `Pose` onto the global object
 * at execution time. So the named export the library asks for does not exist in
 * any module format, and no bundler or browser can synthesise it. Vite 8
 * optimizes dependencies with Rolldown, which treats that as a hard
 * `[MISSING_EXPORT]` error and aborts the dev server on startup.
 *
 * MoveWell only ever calls `createDetector(SupportedModels.MoveNet, ...)` — see
 * `src/assessment/pose/poseEngine.js`. The BlazePose MediaPipe runtime is not
 * used anywhere in this codebase. Pointing the specifier at this module gives
 * the import something real to bind to, leaves the MoveNet code path completely
 * untouched, and keeps roughly 50 MB of `.tflite` and `.wasm` assets out of the
 * module graph.
 *
 * WHAT TO DO IF YOU ACTUALLY WANT BLAZEPOSE + MEDIAPIPE
 *
 * Remove the `@mediapipe/pose` entry from `resolve.alias` in `vite.config.js`
 * and load the MediaPipe solution from its CDN as a classic script before
 * creating the detector, which is how MediaPipe is designed to be consumed. Do
 * not expect the bare `import` to start working on its own.
 *
 * If a future version of `@tensorflow-models/pose-detection` imports additional
 * symbols from `@mediapipe/pose`, the build will fail again naming the specific
 * missing symbol. Add it here the same way.
 */

const GUIDANCE = [
  '@mediapipe/pose is aliased to a build-time shim in vite.config.js because',
  'the published package exposes no ES module exports, which breaks dependency',
  'optimization. MoveWell uses the MoveNet runtime and never constructs a',
  'MediaPipe Pose solution. See src/shims/mediapipe-pose.js for how to opt in',
  'to BlazePose with the MediaPipe runtime if you need it.',
].join(' ')

/**
 * Stand-in for MediaPipe's `Pose` solution class.
 *
 * Constructing it is always a programming error in this codebase, so it throws
 * immediately with an explanation rather than failing later with a confusing
 * message about a missing WASM binary or an undefined method.
 */
export class Pose {
  constructor() {
    throw new Error(`MediaPipe Pose is not available in this build. ${GUIDANCE}`)
  }
}

export default { Pose }
